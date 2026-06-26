"""Detector sub-agents (Concept 2: multi-agent).

Each specialist owns one leak family. It runs the cheap, exact deterministic
detector to FIND candidates, then applies the reconciliation-judgment skill
(Gemini) to JUDGE each one, emitting structured `Finding` objects. This hybrid —
deterministic detection + LLM judgment — keeps dollar math exact and uses the
model only where judgment lives.
"""
from __future__ import annotations

import pandas as pd

import detection
from agents import guardrails, skills
from models import Candidate, Finding, LeakType
from observability import Tracer


def _build_context(candidate: Candidate, contracts: pd.DataFrame) -> dict:
    """Assemble the evidence packet the judge reasons over."""
    ctx: dict = {
        "contract": candidate.evidence.get("contract", {}),
        "evidence": {k: v for k, v in candidate.evidence.items() if k != "contract"},
    }
    if candidate.leak_type in (LeakType.UNDER_BILLING, LeakType.EXPIRED_DISCOUNT):
        affected = candidate.evidence.get("affected_invoices", [])
        if affected:
            ctx["representative_billed_price"] = min(a["billed_price"] for a in affected)
        same = contracts[(contracts["customer_id"] == candidate.customer_id) &
                         (contracts["product"] == candidate.product) &
                         (contracts["contract_id"] != candidate.contract_id)]
        ctx["other_contract_lines"] = [
            {"contract_id": r["contract_id"],
             "contracted_unit_price": float(r["contracted_unit_price"]),
             "term_start": r["term_start"], "notes": str(r.get("notes", ""))[:80]}
            for _, r in same.iterrows()
        ]
    return ctx


class BaseDetectorAgent:
    name: str = "DetectorAgent"
    system_prompt: str = ""

    def detect(self, contracts, invoices, usage) -> list[Candidate]:  # noqa: D401
        raise NotImplementedError

    def run(self, contracts: pd.DataFrame, invoices: pd.DataFrame,
            usage: pd.DataFrame, tracer: Tracer) -> list[Finding]:
        findings: list[Finding] = []
        with tracer.timed(self.name, "detect", detail="deterministic pandas scan"):
            candidates = self.detect(contracts, invoices, usage)
        for cand in candidates:
            sink: list = []
            context = _build_context(cand, contracts)
            verdict = skills.reconciliation_judgment(cand, context, tracer, sink)
            status = guardrails.classify_status(verdict, cand)
            findings.append(Finding(
                signature=cand.signature, leak_type=cand.leak_type,
                customer_id=cand.customer_id, contract_id=cand.contract_id,
                product=cand.product, dollar_impact=cand.dollar_impact,
                confidence=verdict.confidence, status=status,
                explanation=verdict.explanation, suggested_action=verdict.suggested_action,
                evidence=cand.evidence, trace=sink, judged_by=verdict.judged_by,
            ))
        return findings


class BillingIntegrityAgent(BaseDetectorAgent):
    name = "BillingIntegrityAgent"
    system_prompt = ("Detects UNDER_BILLING and EXPIRED_DISCOUNT by reconciling each "
                     "invoice's billed price against the contracted price and discount terms.")

    def detect(self, contracts, invoices, usage):
        return detection.detect_billing(contracts, invoices)


class RenewalAgent(BaseDetectorAgent):
    name = "RenewalAgent"
    system_prompt = ("Detects MISSED_RENEWAL: auto-renew contracts whose term ended but "
                     "whose billing silently stopped, losing recurring revenue.")

    def detect(self, contracts, invoices, usage):
        return detection.detect_missed_renewal(contracts, invoices)


class UsageReconciliationAgent(BaseDetectorAgent):
    name = "UsageReconciliationAgent"
    system_prompt = ("Detects UNDER_USAGE_OVERAGE (usage above commit, never billed) and "
                     "MINIMUM_COMMIT_SHORTFALL (term billed below the contractual minimum).")

    def detect(self, contracts, invoices, usage):
        return (detection.detect_overage(contracts, usage)
                + detection.detect_min_commit(contracts, invoices))
