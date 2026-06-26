"""LeakSentry tools layer — functions Gemini can call.

Concept 1: Tools & API integration. All dollar math is deterministic; the LLM
may explain a figure but never computes it (Guardrail 1).

Populated in build steps 3 & 5:
    load_contracts / load_invoices / load_usage,
    pricing_rule_engine, compute_dollar_impact,
    check_case_memory / write_case_memory, draft_recovery_message.
"""
