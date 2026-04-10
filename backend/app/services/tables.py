from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    try:
        return pd.read_csv(path, **kwargs)
    except Exception:
        return None


def load_demand_predictions() -> pd.DataFrame | None:
    df = _read_csv(settings.demand_predictions_path(), parse_dates=["date"])
    return df


def load_sales_fallback() -> pd.DataFrame | None:
    """If analytics missing, use ml_ready with units_sold only (no predictions)."""
    p = settings.ml_ready_path()
    df = _read_csv(p, parse_dates=["date"])
    if df is None:
        return None
    if "predicted_units" not in df.columns:
        df = df.copy()
        df["predicted_units"] = float("nan")
    return df


def load_inventory() -> pd.DataFrame | None:
    return _read_csv(settings.inventory_path())


def load_signals() -> pd.DataFrame | None:
    return _read_csv(settings.signals_path(), parse_dates=["date"])


def load_influencer_sample() -> pd.DataFrame | None:
    return _read_csv(settings.influencer_sample_path())


def load_influencer_metrics() -> dict | None:
    import json

    p = settings.influencer_metrics_path()
    if not p.is_file():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
