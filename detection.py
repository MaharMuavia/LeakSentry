"""Deterministic detectors — cheap, exact pandas analysis that finds CANDIDATE
discrepancies. This is the "find" half of the hybrid design; Gemini does the
"judge" half (see agents/). Every dollar figure routes through
`compute_dollar_impact` (Guardrail 1).

These functions are intentionally LLM-free so we can measure the precision/recall
of the deterministic baseline before adding judgment.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

import config
from models import Candidate, LeakType
from tools.impact import compute_dollar_impact
from tools.pricing import pricing_rule_engine

NOW = config.AUDIT_DATE
THRESHOLD = config.ROUNDING_THRESHOLD


def _d(x) -> date | None:
    try:
        return date.fromisoformat(str(x))
    except (ValueError, TypeError):
        return None


def _months_between(start: date, end: date) -> int:
    return max(0, (end.year * 12 + end.month) - (start.year * 12 + start.month))


# --------------------------------------------------------------------------- #
# Billing integrity: UNDER_BILLING + EXPIRED_DISCOUNT
# --------------------------------------------------------------------------- #
def detect_billing(contracts: pd.DataFrame, invoices: pd.DataFrame) -> list[Candidate]:
    by_id = {r["contract_id"]: r for _, r in contracts.iterrows()}
    # accumulate lines per (contract_id, leak_type)
    buckets: dict[tuple[str, LeakType], list[dict]] = {}

    for _, inv in invoices.iterrows():
        if inv["product"] == "CREDIT" or float(inv["amount"]) <= 0:
            continue
        contract = by_id.get(inv["contract_id"])
        if contract is None:
            continue
        price = pricing_rule_engine(dict(contract), dict(inv))
        delta = price["delta_per_unit"]
        if delta <= 0:
            continue
        # EXPIRED_DISCOUNT only when the discount has lapsed AND the invoice is
        # STILL billing the old discounted price (the discount is wrongly honored).
        # If the billed price is some other lower value, it is plain under-billing.
        still_discounted = (
            price["discount_expired"]
            and abs(price["actual_unit_price"]
                    - round(price["contracted_unit_price"] * (1 - price["discount_pct"]), 2)) <= 0.50
        )
        leak_type = (LeakType.EXPIRED_DISCOUNT if still_discounted
                     else LeakType.UNDER_BILLING)
        line = {
            "expected_price": price["expected_unit_price"],
            "billed_price": price["actual_unit_price"],
            "quantity": int(inv["billed_quantity"]),
            "invoice_id": inv["invoice_id"],
            "invoice_date": inv["invoice_date"],
        }
        buckets.setdefault((inv["contract_id"], leak_type), []).append(line)

    out: list[Candidate] = []
    for (contract_id, leak_type), lines in buckets.items():
        impact = compute_dollar_impact(leak_type, {"lines": lines})
        if impact < THRESHOLD:
            continue
        contract = by_id[contract_id]
        out.append(Candidate(
            leak_type=leak_type, customer_id=contract["customer_id"],
            contract_id=contract_id, product=contract["product"],
            dollar_impact=impact,
            evidence={
                "contract": _contract_evidence(contract),
                "affected_invoices": lines[:8],
                "n_affected": len(lines),
            },
            detector="BillingIntegrityAgent",
        ))
    return out


# --------------------------------------------------------------------------- #
# Renewal: MISSED_RENEWAL
# --------------------------------------------------------------------------- #
def detect_missed_renewal(contracts: pd.DataFrame, invoices: pd.DataFrame) -> list[Candidate]:
    out: list[Candidate] = []
    inv_by_contract = invoices.groupby("contract_id")
    for _, c in contracts.iterrows():
        if not bool(c["auto_renew"]):
            continue
        term_end = _d(c["term_end"])
        if term_end is None or term_end >= NOW:
            continue
        try:
            ci = inv_by_contract.get_group(c["contract_id"])
        except KeyError:
            continue
        last = max((_d(x) for x in ci["invoice_date"]), default=None)
        if last is not None and last > term_end:
            continue   # billing continued past term_end → renewed normally
        missed = _months_between(term_end, NOW)
        monthly = float(c["contracted_unit_price"]) * int(c["committed_quantity"])
        impact = compute_dollar_impact(
            LeakType.MISSED_RENEWAL,
            {"missed_periods": missed, "monthly_amount": monthly},
        )
        if impact < THRESHOLD:
            continue
        out.append(Candidate(
            leak_type=LeakType.MISSED_RENEWAL, customer_id=c["customer_id"],
            contract_id=c["contract_id"], product=c["product"], dollar_impact=impact,
            evidence={
                "contract": _contract_evidence(c),
                "last_invoice_date": last.isoformat() if last else None,
                "missed_periods": missed, "monthly_amount": round(monthly, 2),
            },
            detector="RenewalAgent",
        ))
    return out


# --------------------------------------------------------------------------- #
# Usage: UNDER_USAGE_OVERAGE
# --------------------------------------------------------------------------- #
def detect_overage(contracts: pd.DataFrame, usage: pd.DataFrame) -> list[Candidate]:
    out: list[Candidate] = []
    # choose the most recent contract line per (customer, product)
    cands = (contracts.sort_values("term_start")
             .groupby(["customer_id", "product"]).last().reset_index())
    for _, c in cands.iterrows():
        u = usage[(usage["customer_id"] == c["customer_id"]) &
                  (usage["product"] == c["product"])]
        if u.empty:
            continue
        term_start = _d(c["term_start"])
        committed = int(c["committed_quantity"])
        price = float(c["contracted_unit_price"])
        lines = []
        for _, r in u.iterrows():
            m = _d(r["month"])
            if term_start and m and m < term_start:
                continue
            if int(r["actual_usage_quantity"]) > committed:
                lines.append({"usage": int(r["actual_usage_quantity"]),
                              "committed": committed, "unit_price": price,
                              "month": r["month"]})
        if not lines:
            continue
        impact = compute_dollar_impact(LeakType.UNDER_USAGE_OVERAGE, {"lines": lines})
        if impact < THRESHOLD:
            continue
        out.append(Candidate(
            leak_type=LeakType.UNDER_USAGE_OVERAGE, customer_id=c["customer_id"],
            contract_id=c["contract_id"], product=c["product"], dollar_impact=impact,
            evidence={
                "contract": _contract_evidence(c),
                "overage_months": lines, "committed_per_month": committed,
            },
            detector="UsageReconciliationAgent",
        ))
    return out


# --------------------------------------------------------------------------- #
# Usage: MINIMUM_COMMIT_SHORTFALL
# --------------------------------------------------------------------------- #
def detect_min_commit(contracts: pd.DataFrame, invoices: pd.DataFrame) -> list[Candidate]:
    out: list[Candidate] = []
    for _, c in contracts.iterrows():
        min_commit = float(c["minimum_commit_amount"] or 0)
        term_end = _d(c["term_end"])
        if min_commit <= 0 or term_end is None or term_end > NOW:
            continue   # no commit, or term not yet over → can't assess
        ci = invoices[(invoices["contract_id"] == c["contract_id"]) &
                      (invoices["product"] != "CREDIT")]
        ci = ci[ci["amount"] > 0]
        term_billed = float(ci[ci["invoice_date"].map(lambda x: (_d(x) or NOW) < term_end)]
                            ["amount"].sum())
        if term_billed >= min_commit - THRESHOLD:
            continue
        impact = compute_dollar_impact(
            LeakType.MINIMUM_COMMIT_SHORTFALL,
            {"minimum_commit_amount": min_commit, "total_billed": term_billed},
        )
        if impact < THRESHOLD:
            continue
        out.append(Candidate(
            leak_type=LeakType.MINIMUM_COMMIT_SHORTFALL, customer_id=c["customer_id"],
            contract_id=c["contract_id"], product=c["product"], dollar_impact=impact,
            evidence={
                "contract": _contract_evidence(c),
                "total_billed": round(term_billed, 2),
                "minimum_commit_amount": round(min_commit, 2),
            },
            detector="UsageReconciliationAgent",
        ))
    return out


def _contract_evidence(c) -> dict:
    keys = ["contract_id", "product", "contracted_unit_price", "committed_quantity",
            "discount_pct", "discount_expiry_date", "term_start", "term_end",
            "auto_renew", "minimum_commit_amount", "notes"]
    return {k: (None if pd.isna(c[k]) else c[k]) for k in keys if k in c}


# --------------------------------------------------------------------------- #
# Convenience: run every detector for a scope
# --------------------------------------------------------------------------- #
def detect_all(contracts: pd.DataFrame, invoices: pd.DataFrame,
               usage: pd.DataFrame) -> list[Candidate]:
    return (
        detect_billing(contracts, invoices)
        + detect_missed_renewal(contracts, invoices)
        + detect_overage(contracts, usage)
        + detect_min_commit(contracts, invoices)
    )
