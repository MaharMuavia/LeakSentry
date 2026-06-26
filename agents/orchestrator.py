"""OrchestratorAgent (Concept 2) — plans the audit, delegates to specialist
detector sub-agents, dedupes findings against case memory (Concept 3), applies
guardrails (Concept 4), ranks by dollar-impact x confidence, has the RecoveryAgent
draft artifacts for confirmed leaks, and emits a prioritized LeakReport.
"""
from __future__ import annotations

from agents import runtime, skills
from agents.detector_agents import (BillingIntegrityAgent, RenewalAgent,
                                     UsageReconciliationAgent)
from models import Finding, FindingStatus, LeakReport
from observability import Tracer
from tools import case_memory, data_loader


class RecoveryAgent:
    """Drafts the human-facing recovery artifact for a confirmed leak (output only)."""
    name = "RecoveryAgent"

    def draft(self, finding: Finding, tracer: Tracer) -> None:
        finding.recovery_draft = skills.recovery_drafting(finding, tracer, finding.trace)


class OrchestratorAgent:
    name = "OrchestratorAgent"

    def __init__(self, tracer: Tracer | None = None):
        self.tracer = tracer or Tracer()
        self.detectors = [BillingIntegrityAgent(), RenewalAgent(), UsageReconciliationAgent()]
        self.recovery = RecoveryAgent()

    def run(self, customer_id: str | None = None) -> LeakReport:
        case_memory.init_db()
        contracts = data_loader.load_contracts(customer_id)
        invoices = data_loader.load_invoices(customer_id)
        usage = data_loader.load_usage(customer_id)
        n_customers = contracts["customer_id"].nunique()

        scope = customer_id or "ALL customers"
        engine = "Gemini" if runtime.available() else "heuristic (no API key)"
        with self.tracer.timed(self.name, "plan",
                               detail=f"Audit {scope}; judgment engine: {engine}; "
                                      f"delegating to {len(self.detectors)} detector agents"):
            pass

        # 1. Delegate to specialist detectors (each finds + judges).
        findings: list[Finding] = []
        for det in self.detectors:
            findings.extend(det.run(contracts, invoices, usage, self.tracer))

        # 2. Dedupe against case memory: suppress leaks a human already resolved.
        for f in findings:
            remembered = case_memory.check_case_memory(f.signature)
            if remembered is not None and remembered.resolved:
                f.status = FindingStatus.RESOLVED
                with self.tracer.timed(self.name, "memory", tool="check_case_memory",
                                       detail=f"{f.signature} already resolved — suppressed",
                                       sink=f.trace):
                    pass
            elif f.status in (FindingStatus.CONFIRMED, FindingStatus.NEEDS_REVIEW):
                case_memory.write_case_memory(
                    signature=f.signature, leak_type=f.leak_type.value,
                    customer_id=f.customer_id, contract_id=f.contract_id,
                    product=f.product, dollar_impact=f.dollar_impact,
                    confidence=f.confidence, status=f.status.value, explanation=f.explanation)

        # 3. Draft recovery artifacts for confirmed leaks (human-approval gate later).
        for f in findings:
            if f.status == FindingStatus.CONFIRMED:
                self.recovery.draft(f, self.tracer)

        # 4. Rank by dollar-impact x confidence (highest priority first).
        findings.sort(key=lambda f: f.dollar_impact * f.confidence, reverse=True)

        with self.tracer.timed(self.name, "report",
                               detail=f"{len(findings)} findings; "
                                      f"{sum(1 for f in findings if f.status == FindingStatus.CONFIRMED)} confirmed"):
            pass
        return LeakReport(customers_audited=int(n_customers), findings=findings)
