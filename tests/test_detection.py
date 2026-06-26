"""The deterministic detectors must recover every injected leak (recall=1.0) and
keep their only false positives confined to the amendment-noise traps."""
import pandas as pd
import pytest

import config
import detection
from eval.metrics import score
from tools import data_loader


@pytest.fixture(scope="module")
def found():
    data_loader.clear_cache()
    cands = detection.detect_all(
        data_loader.load_contracts(), data_loader.load_invoices(), data_loader.load_usage())
    return [{"customer_id": c.customer_id, "contract_id": c.contract_id,
             "leak_type": c.leak_type.value, "dollar_impact": c.dollar_impact}
            for c in cands]


def test_perfect_recall_and_dollar_recall(found):
    res = score(found)
    assert res.recall == 1.0, f"missed leaks: {res.missed}"
    assert res.dollar_recall == pytest.approx(1.0, abs=1e-6)


def test_false_positives_are_only_amendment_noise(found):
    res = score(found)
    contracts = pd.read_csv(config.CONTRACTS_CSV, dtype=str)
    contracts["notes"] = contracts["notes"].fillna("")
    amend = contracts[contracts["notes"].str.startswith("Amendment")]
    for _cust, contract_id, leak_type in res.false_positives:
        row = contracts[contracts.contract_id == contract_id].iloc[0]
        sib = amend[(amend.customer_id == row.customer_id) & (amend["product"] == row["product"])]
        assert len(sib) > 0, f"unexpected non-amendment FP: {contract_id} {leak_type}"


def test_baseline_precision_floor(found):
    # The deterministic baseline should be strong but imperfect — leaving room
    # for the Gemini judgment layer to clear the amendment noise.
    res = score(found)
    assert res.precision >= 0.80
