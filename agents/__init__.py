"""LeakSentry agent layer — Orchestrator + specialist sub-agents.

Concept 2: Multi-agent / agent-to-agent. Agents pass structured Pydantic
objects (never raw strings) and each drives a Gemini function-calling loop.

Populated in build steps 4–5:
    OrchestratorAgent, BillingIntegrityAgent, RenewalAgent,
    UsageReconciliationAgent, RecoveryAgent.
"""
