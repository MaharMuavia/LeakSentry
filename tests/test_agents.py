"""End-to-end agent pipeline: judgment clears noise, guardrails hold, memory works."""
import pytest

from agents.orchestrator import OrchestratorAgent
from eval.metrics import score
from models import FindingStatus
from tools import case_memory


@pytest.fixture(scope="module")
def report():
    case_memory.reset_memory()
    return OrchestratorAgent().run()


def _positive(report):
    pos = (FindingStatus.CONFIRMED, FindingStatus.NEEDS_REVIEW)
    return [{"customer_id": f.customer_id, "contract_id": f.contract_id,
             "leak_type": f.leak_type.value, "dollar_impact": f.dollar_impact}
            for f in report.findings if f.status in pos]


def test_judgment_layer_reaches_perfect_precision(report):
    res = score(_positive(report))
    assert res.recall == 1.0
    assert res.precision == 1.0          # amendment noise cleared by judgment


def test_amendment_noise_is_dismissed(report):
    dismissed = [f for f in report.findings if f.status == FindingStatus.DISMISSED]
    assert len(dismissed) == 8
    assert all(f.leak_type.value == "UNDER_BILLING" for f in dismissed)


def test_poisoned_notes_leak_still_reported(report):
    poisoned = [f for f in report.findings if f.contract_id == "CT0084"]
    assert poisoned and poisoned[0].status == FindingStatus.CONFIRMED
    # Guardrail 3 must have fired on this finding's trace.
    assert any(s.action == "guardrail" for s in poisoned[0].trace)


def test_confirmed_findings_have_recovery_drafts(report):
    for f in report.confirmed:
        assert f.recovery_draft, f"missing recovery draft for {f.contract_id}"


def test_headline_total_excludes_needs_review(report):
    assert report.headline_total == round(sum(f.dollar_impact for f in report.confirmed), 2)
