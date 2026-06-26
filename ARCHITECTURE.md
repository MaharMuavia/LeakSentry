# LeakSentry — Architecture

> Status: skeleton (build step 1). Expanded as modules land.

## Design philosophy

**Deterministic detection + LLM judgment.** Exact pandas math finds candidate
discrepancies and computes every dollar figure; Google Gemini is used only to
*judge* whether a candidate is a real leak or explainable noise. The LLM never
computes a final dollar amount — that is a hard guardrail.

## Components

### Data layer (`data/`)
- `generate_dataset.py` — generates a realistic, internally-inconsistent dataset
  for fictional B2B SaaS "Northwind Cloud" plus a labeled `ground_truth.csv`.
- Outputs: `contracts.csv`, `invoices.csv`, `usage.csv`, `ground_truth.csv`.

### Tools layer (`tools/`) — *Concept 1: Tools & API integration*
| Tool | Determinism | Purpose |
|------|-------------|---------|
| `load_contracts/invoices/usage` | deterministic | data access |
| `pricing_rule_engine` | deterministic | expected vs actual price |
| `compute_dollar_impact` | deterministic | **the only source of dollar figures** |
| `check/write_case_memory` | deterministic (SQLite) | dedupe across runs |
| `draft_recovery_message` | Gemini | recovery artifact text |

### Agent layer (`agents/`) — *Concept 2: Multi-agent*
- `OrchestratorAgent` — plans the audit, delegates, dedupes against case memory,
  ranks by `dollar_impact × confidence`, emits a prioritized `LeakReport`.
- `BillingIntegrityAgent` — UNDER_BILLING, EXPIRED_DISCOUNT.
- `RenewalAgent` — MISSED_RENEWAL.
- `UsageReconciliationAgent` — UNDER_USAGE_OVERAGE, MINIMUM_COMMIT_SHORTFALL.
- `RecoveryAgent` — drafts the recovery artifact (output only; never sends).

Agents pass structured **Pydantic** objects (`Finding`, `LeakReport`), never raw strings.

### Memory & skills — *Concept 3: Context engineering*
- Case memory (SQLite via SQLModel) prevents re-flagging resolved leaks.
- Reusable "skills": a reconciliation skill and a recovery-drafting skill.

### Guardrails & evals — *Concept 4: Quality & guardrails*
- **G1 anti-hallucination:** every Finding's dollar figure must come from
  `compute_dollar_impact`, else it's dropped + logged.
- **G2 confidence threshold:** findings below threshold (default 0.6) → "needs
  human review" bucket, excluded from headline total.
- **G3 input safety:** free-text fields (e.g. customer `notes`) sanitized before
  entering prompts; dataset includes one poisoned row to demonstrate the catch.
- **Eval harness** (`eval/run_eval.py`): precision, recall, F1, dollar-recall,
  false-positive rate vs `ground_truth.csv`.

### Observability
- Every agent step (agent, tool, inputs, outputs, tokens, latency) logged to a
  JSONL trace file and surfaced in the UI as an expandable reasoning trace.

### Backend (`backend/`) + Frontend (`frontend/`)
- FastAPI async app exposes audit + findings + approval endpoints.
- Single-screen Next.js + Tailwind + shadcn/ui dashboard with the human-approval gate.

## Data flow (one audit)

```
contracts/invoices/usage CSV
        ↓ (Orchestrator plans)
detector agents → deterministic candidates → Gemini judgment → Findings (+confidence)
        ↓ (guardrails filter, case-memory dedupe)
ranked LeakReport → RecoveryAgent drafts → Human approval gate → resolved in case memory
```
