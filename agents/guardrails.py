"""Guardrails (Concept 4) — the safety layer most teams skip.

G1 anti-hallucination : every dollar figure must come from compute_dollar_impact.
G2 confidence gate    : low-confidence findings never enter the headline total.
G3 input safety       : sanitize free-text (notes) before it enters any prompt.
"""
from __future__ import annotations

import re

import config
from models import Candidate, FindingStatus, Verdict

# Patterns a hostile "notes" field might use to hijack the LLM (Guardrail 3).
_INJECTION_PATTERNS = [
    r"ignore (all|any|previous|prior).{0,40}instructions?",
    r"disregard.{0,40}(instructions?|above|prior)",
    r"mark .{0,40}(reconciled|resolved|\$?0)",
    r"do not (report|flag|raise)",
    r"system prompt", r"you are now", r"new instructions?",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_text(text: str) -> tuple[str, bool, str]:
    """Neutralize prompt-injection attempts in free text.

    Returns (clean_text, was_sanitized, reason). The cleaned text is safe to embed
    in a prompt: injected directives are redacted and the whole thing is clearly
    framed as untrusted data downstream.
    """
    if not text:
        return "", False, ""
    if _INJECTION_RE.search(text):
        cleaned = _INJECTION_RE.sub("[redacted: possible prompt-injection]", text)
        return cleaned, True, "prompt-injection directive detected in notes field"
    return text, False, ""


# G1: the dollar figure must originate from the deterministic tool.
def dollar_is_tool_computed(candidate: Candidate) -> bool:
    return candidate.dollar_impact is not None and candidate.dollar_impact > 0


# G2: map a verdict + tool-computed dollars to a finding status.
def classify_status(verdict: Verdict, candidate: Candidate,
                    threshold: float = config.CONFIDENCE_THRESHOLD) -> FindingStatus:
    if not dollar_is_tool_computed(candidate):
        return FindingStatus.BLOCKED            # G1: no trustworthy dollar figure
    if not verdict.is_leak:
        return FindingStatus.DISMISSED
    if verdict.confidence < threshold:
        return FindingStatus.NEEDS_REVIEW       # G2: below the headline bar
    return FindingStatus.CONFIRMED
