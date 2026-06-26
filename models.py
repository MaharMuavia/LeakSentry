"""Shared Pydantic models passed between LeakSentry agents.

Concept 2 (multi-agent): agents communicate with these structured objects, never
raw strings. A `Candidate` is a deterministic discrepancy; a `Verdict` is the
Gemini judgment; a `Finding` is the adjudicated result; a `LeakReport` is the
ranked output of an audit.
"""
from __future__ import annotations

import enum
import hashlib
from typing import Any, Optional

from pydantic import BaseModel, Field


class LeakType(str, enum.Enum):
    UNDER_BILLING = "UNDER_BILLING"
    EXPIRED_DISCOUNT = "EXPIRED_DISCOUNT"
    MISSED_RENEWAL = "MISSED_RENEWAL"
    UNDER_USAGE_OVERAGE = "UNDER_USAGE_OVERAGE"
    MINIMUM_COMMIT_SHORTFALL = "MINIMUM_COMMIT_SHORTFALL"


class FindingStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"            # real leak, above confidence threshold
    NEEDS_REVIEW = "NEEDS_REVIEW"      # real-ish but low confidence (Guardrail 2)
    DISMISSED = "DISMISSED"            # judged to be explainable noise
    BLOCKED = "BLOCKED"               # dropped by a guardrail (e.g. no $ figure)
    RESOLVED = "RESOLVED"             # previously seen + resolved (case memory)


class Candidate(BaseModel):
    """A deterministic discrepancy found by pandas analysis (pre-judgment)."""
    leak_type: LeakType
    customer_id: str
    contract_id: str
    product: str
    dollar_impact: float = Field(..., description="From compute_dollar_impact ONLY")
    evidence: dict[str, Any] = Field(default_factory=dict)
    detector: str = ""

    @property
    def signature(self) -> str:
        """Stable identity for case-memory dedupe across runs."""
        raw = f"{self.leak_type.value}|{self.customer_id}|{self.contract_id}|{self.product}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class Verdict(BaseModel):
    """Gemini's judgment of a single candidate (or a deterministic fallback)."""
    is_leak: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    suggested_action: str = ""
    judged_by: str = "gemini"          # or "heuristic" when no API key present


class TraceStep(BaseModel):
    """One observable step in the agent pipeline (Concept 4: observability)."""
    agent: str
    action: str
    tool: Optional[str] = None
    detail: str = ""
    latency_ms: float = 0.0
    tokens: int = 0


class Finding(BaseModel):
    """An adjudicated candidate: candidate + verdict + status + recovery draft."""
    signature: str
    leak_type: LeakType
    customer_id: str
    contract_id: str
    product: str
    dollar_impact: float
    confidence: float
    status: FindingStatus
    explanation: str
    suggested_action: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    recovery_draft: str = ""
    trace: list[TraceStep] = Field(default_factory=list)
    judged_by: str = "gemini"


class LeakReport(BaseModel):
    """Prioritized output of an audit (Orchestrator emits this)."""
    customers_audited: int
    findings: list[Finding] = Field(default_factory=list)

    @property
    def confirmed(self) -> list[Finding]:
        return [f for f in self.findings if f.status == FindingStatus.CONFIRMED]

    @property
    def needs_review(self) -> list[Finding]:
        return [f for f in self.findings if f.status == FindingStatus.NEEDS_REVIEW]

    @property
    def headline_total(self) -> float:
        """Confidence-gated recoverable total (only CONFIRMED findings)."""
        return round(sum(f.dollar_impact for f in self.confirmed), 2)
