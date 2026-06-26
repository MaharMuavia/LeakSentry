"""LeakSentry eval harness (Concept 4).

Runs the pipeline against the synthetic data and reports precision / recall / F1 /
dollar-recall / false-positive rate vs `data/ground_truth.csv`.

Modes:
    --mode deterministic   detectors only, no LLM (the baseline)
    --mode agents          full Orchestrator + Gemini judgment pipeline

    python eval/run_eval.py --mode deterministic
    python eval/run_eval.py --mode agents
"""
from __future__ import annotations

import argparse
import os
import sys

from tabulate import tabulate

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from eval.metrics import EvalResult, score


def _deterministic_findings() -> list[dict]:
    from tools import data_loader
    import detection
    data_loader.clear_cache()
    contracts = data_loader.load_contracts()
    invoices = data_loader.load_invoices()
    usage = data_loader.load_usage()
    cands = detection.detect_all(contracts, invoices, usage)
    return [{"customer_id": c.customer_id, "contract_id": c.contract_id,
             "leak_type": c.leak_type.value, "dollar_impact": c.dollar_impact}
            for c in cands]


def _agent_findings() -> list[dict]:
    from agents.orchestrator import OrchestratorAgent
    report = OrchestratorAgent().run()      # audit all customers
    # Only CONFIRMED findings count toward the headline metrics.
    return [{"customer_id": f.customer_id, "contract_id": f.contract_id,
             "leak_type": f.leak_type.value, "dollar_impact": f.dollar_impact}
            for f in report.confirmed]


def _print(mode: str, res: EvalResult) -> None:
    print(f"\n{'=' * 60}\nLeakSentry eval - mode: {mode}\n{'=' * 60}")
    rows = [
        ["Precision", f"{res.precision:.3f}"],
        ["Recall", f"{res.recall:.3f}"],
        ["F1", f"{res.f1:.3f}"],
        ["Dollar-recall", f"{res.dollar_recall:.1%}"],
        ["False-positive rate", f"{res.fp_rate:.3f}"],
        ["True positives", res.tp],
        ["False positives", res.fp],
        ["False negatives", res.fn],
        ["True leak dollars", f"${res.true_dollars:,.2f}"],
        ["Recovered dollars", f"${res.recovered_dollars:,.2f}"],
    ]
    print(tabulate(rows, headers=["metric", "value"], tablefmt="github"))
    if res.false_positives:
        print(f"\n  False positives ({res.fp}):")
        for k in res.false_positives:
            print(f"    - {k[0]} {k[1]} {k[2]}")
    if res.missed:
        print(f"\n  Missed leaks ({res.fn}):")
        for k in res.missed:
            print(f"    - {k[0]} {k[1]} {k[2]}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["deterministic", "agents"], default="deterministic")
    args = ap.parse_args()

    found = _deterministic_findings() if args.mode == "deterministic" else _agent_findings()
    _print(args.mode, score(found))


if __name__ == "__main__":
    main()
