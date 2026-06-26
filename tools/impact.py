"""compute_dollar_impact — the ONLY source of dollar figures (Guardrail 1).

Every Finding's dollar amount must originate here, from explicit numeric inputs.
The LLM may *explain* a figure but never computes it. Each branch is a pure,
deterministic sum so the math is exact and auditable.
"""
from __future__ import annotations

from models import LeakType


def compute_dollar_impact(leak_type: LeakType, evidence: dict) -> float:
    """Return the recoverable dollar impact for a candidate, from `evidence`.

    Expected `evidence` shape per leak type:
      UNDER_BILLING / EXPIRED_DISCOUNT:
          lines: list of {expected_price, billed_price, quantity}
      MISSED_RENEWAL:
          missed_periods: int, monthly_amount: float
      UNDER_USAGE_OVERAGE:
          lines: list of {usage, committed, unit_price}
      MINIMUM_COMMIT_SHORTFALL:
          minimum_commit_amount: float, total_billed: float
    """
    lt = LeakType(leak_type)

    if lt in (LeakType.UNDER_BILLING, LeakType.EXPIRED_DISCOUNT):
        total = sum(
            max(line["expected_price"] - line["billed_price"], 0.0) * line["quantity"]
            for line in evidence.get("lines", [])
        )
    elif lt is LeakType.MISSED_RENEWAL:
        total = max(int(evidence["missed_periods"]), 0) * float(evidence["monthly_amount"])
    elif lt is LeakType.UNDER_USAGE_OVERAGE:
        total = sum(
            max(line["usage"] - line["committed"], 0.0) * line["unit_price"]
            for line in evidence.get("lines", [])
        )
    elif lt is LeakType.MINIMUM_COMMIT_SHORTFALL:
        total = max(float(evidence["minimum_commit_amount"]) - float(evidence["total_billed"]), 0.0)
    else:  # pragma: no cover - exhaustive above
        raise ValueError(f"Unknown leak type: {leak_type}")

    return round(float(total), 2)
