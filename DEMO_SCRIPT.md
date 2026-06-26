# LeakSentry — 3-Minute Demo Script

> Status: skeleton (build step 1). Finalized in build step 9 once the dashboard exists.

## Setup (before recording)
- [ ] `.env` has a valid `GEMINI_API_KEY`.
- [ ] `python data/generate_dataset.py` has run; CSVs present.
- [ ] `make demo` is up (backend + dashboard).
- [ ] Browser at `http://localhost:3000`, zoomed for readability.

## Beat sheet (target ~3:00)

**0:00–0:30 — The hook (the problem).**
> "Companies lose 1–5% of revenue to leakage they never even see. It hides in the
> gaps between contracts, invoices, and usage — three systems that disagree."
Show the three raw CSVs side by side; point at one row where they conflict.

**0:30–1:00 — The headline (the wow).**
Click **Run Audit**. Land on the headline: *"$X in recoverable revenue leakage
found across N customers"* with the confidence-weighted breakdown chart.

**1:00–2:00 — The agents thinking (the 70%).**
Click a high-impact finding → side panel:
- the conflicting contract vs invoice vs usage rows (the evidence),
- the plain-English explanation,
- the **full agent reasoning trace** — which agents ran, which tools they called,
  with timings. *"This is deterministic detection plus Gemini judgment — the math
  is exact, the LLM only judges."*

**2:00–2:30 — Guardrails (the differentiator).**
Show a flagged candidate that was correctly dismissed as noise, and the poisoned
`notes` row caught by the prompt-injection guardrail. Show the "needs human
review" bucket for low-confidence findings.

**2:30–3:00 — The gate + the evidence.**
Show the drafted recovery message and the **[Approve] / [Reject]** gate; click
Approve → it's marked resolved in case memory (no real send). Close on the eval
results table: *"Precision X, recall Y, dollar-recall Z — measured against labeled
ground truth."*

## One-liners to land
- "Every dollar figure is traceable to deterministic code — never hallucinated."
- "Case memory means it never re-flags a leak you already resolved."
- "Nothing is ever sent. A human approves every recovery action."
