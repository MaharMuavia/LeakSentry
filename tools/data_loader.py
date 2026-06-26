"""Data-loading tools (Concept 1). Thin, cached pandas readers over the CSVs."""
from __future__ import annotations

import functools

import pandas as pd

import config


@functools.lru_cache(maxsize=1)
def _contracts() -> pd.DataFrame:
    df = pd.read_csv(config.CONTRACTS_CSV, dtype={"customer_id": str, "contract_id": str})
    df["discount_expiry_date"] = df["discount_expiry_date"].fillna("")
    df["notes"] = df["notes"].fillna("")
    return df


@functools.lru_cache(maxsize=1)
def _invoices() -> pd.DataFrame:
    return pd.read_csv(config.INVOICES_CSV, dtype={"customer_id": str, "contract_id": str})


@functools.lru_cache(maxsize=1)
def _usage() -> pd.DataFrame:
    return pd.read_csv(config.USAGE_CSV, dtype={"customer_id": str})


def clear_cache() -> None:
    _contracts.cache_clear()
    _invoices.cache_clear()
    _usage.cache_clear()


def load_contracts(customer_id: str | None = None) -> pd.DataFrame:
    df = _contracts()
    return df[df["customer_id"] == customer_id].copy() if customer_id else df.copy()


def load_invoices(customer_id: str | None = None) -> pd.DataFrame:
    df = _invoices()
    return df[df["customer_id"] == customer_id].copy() if customer_id else df.copy()


def load_usage(customer_id: str | None = None) -> pd.DataFrame:
    df = _usage()
    return df[df["customer_id"] == customer_id].copy() if customer_id else df.copy()


def all_customer_ids() -> list[str]:
    return sorted(_contracts()["customer_id"].unique().tolist())
