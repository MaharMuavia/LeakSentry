"""Case memory (Concept 3: context engineering) — persistent SQLite store.

So the system does not re-flag leaks it already surfaced or that a human already
resolved. Keyed by a stable leak `signature`. Backed by SQLModel/SQLite (no
external DB to set up).
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

import config

_engine = create_engine(config.DB_URL, echo=False)


class CaseRecord(SQLModel, table=True):
    """One remembered leak finding across audit runs."""
    signature: str = Field(primary_key=True)
    leak_type: str
    customer_id: str
    contract_id: str
    product: str
    dollar_impact: float
    confidence: float
    status: str                      # CONFIRMED / NEEDS_REVIEW / RESOLVED / DISMISSED
    explanation: str = ""
    first_seen: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    last_seen: str = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    resolved: bool = False


def init_db() -> None:
    SQLModel.metadata.create_all(_engine)


def check_case_memory(signature: str) -> Optional[CaseRecord]:
    """Return the remembered record for `signature`, or None if unseen."""
    with Session(_engine) as s:
        return s.get(CaseRecord, signature)


def write_case_memory(*, signature: str, leak_type: str, customer_id: str,
                      contract_id: str, product: str, dollar_impact: float,
                      confidence: float, status: str, explanation: str = "") -> CaseRecord:
    """Insert or update a case record (idempotent on signature)."""
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with Session(_engine) as s:
        rec = s.get(CaseRecord, signature)
        if rec is None:
            rec = CaseRecord(
                signature=signature, leak_type=leak_type, customer_id=customer_id,
                contract_id=contract_id, product=product, dollar_impact=dollar_impact,
                confidence=confidence, status=status, explanation=explanation,
                first_seen=now, last_seen=now,
            )
        else:
            rec.last_seen = now
            rec.dollar_impact = dollar_impact
            rec.confidence = confidence
            if not rec.resolved:               # never overwrite a human resolution
                rec.status = status
                rec.explanation = explanation
        s.add(rec)
        s.commit()
        s.refresh(rec)
        return rec


def mark_resolved(signature: str) -> bool:
    """Human-approval gate: mark a finding resolved so it won't re-surface."""
    with Session(_engine) as s:
        rec = s.get(CaseRecord, signature)
        if rec is None:
            return False
        rec.resolved = True
        rec.status = "RESOLVED"
        rec.last_seen = dt.datetime.now(dt.timezone.utc).isoformat()
        s.add(rec)
        s.commit()
        return True


def all_records() -> list[CaseRecord]:
    with Session(_engine) as s:
        return list(s.exec(select(CaseRecord)).all())


def reset_memory() -> None:
    """Drop all remembered cases (used by eval runs for a clean slate)."""
    SQLModel.metadata.drop_all(_engine)
    SQLModel.metadata.create_all(_engine)
