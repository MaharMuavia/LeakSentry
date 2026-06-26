"""pricing_rule_engine — deterministic expected-vs-actual price for an invoice."""
from __future__ import annotations

from datetime import date


def _parse(d) -> date | None:
    if d is None or d == "" or (isinstance(d, float)):
        return None
    try:
        return date.fromisoformat(str(d))
    except ValueError:
        return None


def pricing_rule_engine(contract: dict, invoice: dict) -> dict:
    """Return the expected unit price for `invoice` under `contract`'s terms.

    Applies the contracted discount only while it is valid (on/before its
    expiry). Returns a small dict so callers (and the LLM, read-only) can see
    exactly how the expected price was derived.
    """
    contracted = float(contract["contracted_unit_price"])
    discount_pct = float(contract.get("discount_pct", 0) or 0)
    expiry = _parse(contract.get("discount_expiry_date"))
    inv_date = _parse(invoice["invoice_date"])

    discount_valid = bool(discount_pct > 0 and expiry is not None
                          and inv_date is not None and inv_date <= expiry)
    expected = contracted * (1 - discount_pct) if discount_valid else contracted

    actual = float(invoice["billed_unit_price"])
    return {
        "expected_unit_price": round(expected, 2),
        "actual_unit_price": round(actual, 2),
        "contracted_unit_price": round(contracted, 2),
        "discount_applied": discount_valid,
        "discount_pct": discount_pct,
        "discount_expired": bool(discount_pct > 0 and expiry is not None
                                 and inv_date is not None and inv_date > expiry),
        "delta_per_unit": round(expected - actual, 2),
    }
