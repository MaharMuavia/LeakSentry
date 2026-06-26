"""Case memory (Concept 3): a resolved leak is suppressed on the next audit."""
from agents.orchestrator import OrchestratorAgent
from models import FindingStatus
from tools import case_memory


def test_resolved_leak_is_suppressed_next_run():
    case_memory.reset_memory()

    # First audit: pick a confirmed leak and "approve" it (human-approval gate).
    first = OrchestratorAgent().run()
    target = first.confirmed[0]
    assert case_memory.mark_resolved(target.signature) is True

    # Second audit: the same leak must now come back as RESOLVED, not CONFIRMED,
    # and must drop out of the headline recoverable total.
    second = OrchestratorAgent().run()
    same = [f for f in second.findings if f.signature == target.signature]
    assert same and same[0].status == FindingStatus.RESOLVED
    assert all(f.signature != target.signature for f in second.confirmed)
