"""Guardrail 1: the dollar-impact calculator is deterministic and exact."""
from models import LeakType
from tools.impact import compute_dollar_impact
from tools.pricing import pricing_rule_engine


def test_under_billing_sum():
    ev = {"lines": [
        {"expected_price": 100.0, "billed_price": 90.0, "quantity": 10},   # 100
        {"expected_price": 50.0, "billed_price": 50.0, "quantity": 5},     # 0
    ]}
    assert compute_dollar_impact(LeakType.UNDER_BILLING, ev) == 100.0


def test_missed_renewal_product():
    ev = {"missed_periods": 4, "monthly_amount": 1250.0}
    assert compute_dollar_impact(LeakType.MISSED_RENEWAL, ev) == 5000.0


def test_overage_only_counts_excess():
    ev = {"lines": [
        {"usage": 120, "committed": 100, "unit_price": 10.0},   # 200
        {"usage": 80, "committed": 100, "unit_price": 10.0},    # 0 (under)
    ]}
    assert compute_dollar_impact(LeakType.UNDER_USAGE_OVERAGE, ev) == 200.0


def test_min_commit_shortfall_floored_at_zero():
    assert compute_dollar_impact(
        LeakType.MINIMUM_COMMIT_SHORTFALL,
        {"minimum_commit_amount": 1000.0, "total_billed": 1200.0}) == 0.0
    assert compute_dollar_impact(
        LeakType.MINIMUM_COMMIT_SHORTFALL,
        {"minimum_commit_amount": 1000.0, "total_billed": 600.0}) == 400.0


def test_pricing_engine_honors_then_expires_discount():
    contract = {"contracted_unit_price": 100.0, "discount_pct": 0.2,
                "discount_expiry_date": "2026-01-01"}
    before = pricing_rule_engine(contract, {"invoice_date": "2025-12-01", "billed_unit_price": 80.0})
    after = pricing_rule_engine(contract, {"invoice_date": "2026-02-01", "billed_unit_price": 80.0})
    assert before["expected_unit_price"] == 80.0 and before["discount_applied"]
    assert after["expected_unit_price"] == 100.0 and after["discount_expired"]
