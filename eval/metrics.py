"""Scoring helpers for the eval harness (Concept 4).

A "found leak" is identified by (customer_id, contract_id, leak_type). We compare
the set of found leaks to `ground_truth.csv` and compute precision, recall, F1,
dollar-recall, and false-positive count.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

import config


@dataclass
class EvalResult:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    dollar_recall: float
    true_dollars: float
    recovered_dollars: float
    false_positives: list[tuple]
    missed: list[tuple]

    @property
    def fp_rate(self) -> float:
        flagged = self.tp + self.fp
        return self.fp / flagged if flagged else 0.0


def _key(customer_id, contract_id, leak_type) -> tuple:
    return (str(customer_id), str(contract_id), str(leak_type))


def load_ground_truth() -> pd.DataFrame:
    return pd.read_csv(config.GROUND_TRUTH_CSV,
                       dtype={"customer_id": str, "contract_id": str})


def score(found: list[dict], gt: pd.DataFrame | None = None) -> EvalResult:
    """`found`: list of {customer_id, contract_id, leak_type, dollar_impact}."""
    if gt is None:
        gt = load_ground_truth()

    gt_keys = {_key(r.customer_id, r.contract_id, r.leak_type): float(r.true_dollar_impact)
               for r in gt.itertuples()}
    found_keys = {_key(f["customer_id"], f["contract_id"], f["leak_type"]) for f in found}

    tp_keys = found_keys & set(gt_keys)
    fp_keys = found_keys - set(gt_keys)
    fn_keys = set(gt_keys) - found_keys

    tp, fp, fn = len(tp_keys), len(fp_keys), len(fn_keys)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    true_dollars = sum(gt_keys.values())
    recovered = sum(gt_keys[k] for k in tp_keys)
    dollar_recall = recovered / true_dollars if true_dollars else 0.0

    return EvalResult(
        tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1,
        dollar_recall=dollar_recall, true_dollars=true_dollars,
        recovered_dollars=recovered,
        false_positives=sorted(fp_keys), missed=sorted(fn_keys),
    )
