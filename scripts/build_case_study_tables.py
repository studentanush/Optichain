#!/usr/bin/env python3
"""
Build analytics and case-study CSVs for the FastAPI + dashboard pipeline.

Reads:
  - ws_demand_dataset/ml_ready_data.csv
  - ws_model/best_model.pkl + feature_cols.pkl (optional; if missing, uses rolling mean as predicted_units)
  - features_engineered.csv + models/* (optional; writes influencer metrics/sample)

Writes:
  - analytics/demand_with_predictions.csv
  - analytics/sales_timeseries.csv
  - analytics/influencer_metrics.json (optional)
  - analytics/influencer_sample.csv (optional)
  - data/inventory.csv
  - data/signals.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    "lift_6h",
    "lift_24h",
    "lift_48h",
    "lift_72h",
    "lift_96h",
    "peak_lift_pct",
    "decay_lambda",
]


def _load_ml_ready(root: Path) -> pd.DataFrame | None:
    p = root / "ws_demand_dataset" / "ml_ready_data.csv"
    if not p.is_file():
        print(f"[warn] Missing {p}")
        return None
    return pd.read_csv(p, parse_dates=["date"])


def _predict_model1(df: pd.DataFrame, root: Path) -> pd.Series:
    mp = root / "ws_model" / "best_model.pkl"
    fp = root / "ws_model" / "feature_cols.pkl"
    if not mp.is_file() or not fp.is_file():
        print("[warn] MODEL1 pickles missing  using 7-day rolling mean of units_sold as predicted_units.")
        return df.groupby("sku_id")["units_sold"].transform(lambda s: s.rolling(7, min_periods=1).mean())
    model = joblib.load(mp)
    feats = list(joblib.load(fp))
    missing = [c for c in feats if c not in df.columns]
    if missing:
        print(f"[warn] ml_ready_data missing columns {missing[:5]}...  falling back to rolling mean.")
        return df.groupby("sku_id")["units_sold"].transform(lambda s: s.rolling(7, min_periods=1).mean())
    x = df[feats].replace([np.inf, -np.inf], np.nan).fillna(0)
    pred = model.predict(x)
    return pd.Series(pred, index=df.index)


def _write_sales_ts(df: pd.DataFrame, out: Path) -> None:
    slim = df[["date", "sku_id", "units_sold", "category", "brand_id"]].copy()
    slim["store_id"] = "DC1"
    slim.to_csv(out, index=False)


def _build_inventory(df: pd.DataFrame, root: Path) -> pd.DataFrame:
    """Synthetic inventory aligned to SKUs with deliberate stockout/overstock examples."""
    rng = np.random.default_rng(42)
    last = df.sort_values("date").groupby("sku_id").tail(30)
    stats = last.groupby("sku_id").agg(
        mean_u=("units_sold", "mean"),
        mean_p=("predicted_units", "mean"),
        category=("category", "first"),
    ).reset_index()
    stats["run_rate"] = stats[["mean_u", "mean_p"]].max(axis=1).clip(lower=0.5)

    warehouses = ["W1", "W2"]
    rows: list[dict] = []
    sku_list = stats["sku_id"].tolist()
    for sku in sku_list:
        rr = float(stats.loc[stats["sku_id"] == sku, "run_rate"].iloc[0])
        for w in warehouses:
            lead = int(rng.integers(35, 75))  # ~510+ weeks
            # Split stock across warehouses
            base = rr * lead * rng.uniform(0.6, 1.4)
            stock = max(10.0, base * rng.uniform(0.4, 1.2))
            on_order = rng.uniform(0, rr * 14) if rng.random() > 0.3 else 0.0
            rows.append(
                {
                    "sku_id": sku,
                    "warehouse_id": w,
                    "stock_on_hand": round(stock, 1),
                    "on_order": round(on_order, 1),
                    "lead_time_days": lead,
                }
            )

    inv = pd.DataFrame(rows)
    inv = inv.merge(stats[["sku_id", "run_rate"]], on="sku_id", how="left")
    # Force a few dramatic scenarios matching the case study narrative
    if len(inv) > 0:
        fast = stats.nlargest(3, "run_rate")["sku_id"].tolist()
        for sku in fast[:2]:
            m = (inv["sku_id"] == sku) & (inv["warehouse_id"] == "W1")
            inv.loc[m, "stock_on_hand"] = (
                inv.loc[m, "run_rate"] * inv.loc[m, "lead_time_days"] * 0.35
            ).round(1)
            inv.loc[m, "on_order"] = (inv.loc[m, "run_rate"] * 10).round(1)
        slow = stats.nsmallest(4, "run_rate")["sku_id"].tolist()
        for sku in slow[:2]:
            m = (inv["sku_id"] == sku) & (inv["warehouse_id"] == "W2")
            inv.loc[m, "stock_on_hand"] = (inv.loc[m, "run_rate"] * 120).round(1)
            inv.loc[m, "on_order"] = 0.0
    inv = inv.drop(columns=["run_rate"], errors="ignore")
    out = root / "data" / "inventory.csv"
    inv.to_csv(out, index=False)
    print(f"[ok] Wrote {out} ({len(inv)} rows)")
    return inv


def _build_signals(df: pd.DataFrame, root: Path) -> None:
    """Daily social + search style signals per sku (synthetic fusion demo)."""
    rng = np.random.default_rng(7)
    dmin, dmax = df["date"].min(), df["date"].max()
    dates = pd.date_range(dmin, dmax, freq="D")
    skus = df["sku_id"].unique()
    rows: list[dict] = []
    vol_base = df.groupby("sku_id")["units_sold"].mean().to_dict()
    for sku in skus:
        base = max(50.0, float(vol_base.get(sku, 20)) * 800)
        for dt in dates:
            noise = rng.normal(0, 0.15)
            seasonal = 1.0 + 0.35 * np.sin(2 * np.pi * dt.dayofyear / 365)
            social = max(0.0, base * seasonal * (1 + noise) * rng.uniform(0.85, 1.15))
            search = social * rng.uniform(0.4, 0.9)
            rows.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "sku_id": sku,
                    "signal_type": "social",
                    "volume": round(social, 1),
                    "source": rng.choice(["TikTok", "Instagram", "YouTube"]),
                }
            )
            rows.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "sku_id": sku,
                    "signal_type": "search",
                    "volume": round(search, 1),
                    "source": "GoogleTrends",
                }
            )
    sig = pd.DataFrame(rows)
    out = root / "data" / "signals.csv"
    sig.to_csv(out, index=False)
    print(f"[ok] Wrote {out} ({len(sig)} rows)")


def _influencer_block(root: Path) -> None:
    fe_path = root / "features_engineered.csv"
    mdir = root / "models"
    if not fe_path.is_file():
        print("[skip] features_engineered.csv not found")
        return
    df = pd.read_csv(fe_path)
    metrics: dict = {"targets": {}, "best_models": {}}
    sample_cols = [c for c in df.columns if c in TARGETS or c == "ws_flag"]
    for t in TARGETS:
        if t not in df.columns:
            continue
        pkl = mdir / f"{t}_best.pkl"
        jf = mdir / f"{t}_features.json"
        if not pkl.is_file() or not jf.is_file():
            continue
        try:
            model = joblib.load(pkl)
            with open(jf, encoding="utf-8") as f:
                use_cols = json.load(f)
        except Exception as e:
            print(f"[warn] MODEL2 {t}: {e}")
            continue
        miss = [c for c in use_cols if c not in df.columns]
        if miss:
            print(f"[warn] {t}: missing columns, skip")
            continue
        x = df[use_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        pred = model.predict(x)
        y = df[t].values
        metrics["targets"][t] = {
            "rmse": float(np.sqrt(mean_squared_error(y, pred))),
            "mae": float(mean_absolute_error(y, pred)),
            "n": int(len(y)),
        }
        metrics["best_models"][t] = type(model).__name__

    analytics = root / "analytics"
    if metrics["targets"]:
        with open(analytics / "influencer_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(f"[ok] Wrote {analytics / 'influencer_metrics.json'}")

    t = "peak_lift_pct"
    if t in df.columns:
        pkl = mdir / f"{t}_best.pkl"
        jf = mdir / f"{t}_features.json"
        if pkl.is_file() and jf.is_file():
            try:
                model = joblib.load(pkl)
                with open(jf, encoding="utf-8") as f:
                    use_cols = json.load(f)
                if all(c in df.columns for c in use_cols):
                    x = df[use_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
                    pred = model.predict(x)
                    block = df[sample_cols + use_cols].copy()
                    block["peak_lift_pct_pred"] = pred
                    block.head(2000).to_csv(analytics / "influencer_sample.csv", index=False)
                    print(f"[ok] Wrote {analytics / 'influencer_sample.csv'}")
            except Exception as e:
                print(f"[warn] peak_lift_pct sample: {e}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root")
    args = parser.parse_args()
    root: Path = args.root.resolve()
    (root / "analytics").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)

    df = _load_ml_ready(root)
    if df is None:
        print("[error] Cannot proceed without ws_demand_dataset/ml_ready_data.csv")
        return 1

    df = df.sort_values(["sku_id", "date"]).reset_index(drop=True)
    df["predicted_units"] = _predict_model1(df, root)
    df["predicted_units"] = df["predicted_units"].clip(lower=0)

    analytics = root / "analytics"
    demand_out = analytics / "demand_with_predictions.csv"
    df.to_csv(demand_out, index=False)
    print(f"[ok] Wrote {demand_out}")

    _write_sales_ts(df, analytics / "sales_timeseries.csv")
    print(f"[ok] Wrote {analytics / 'sales_timeseries.csv'}")

    _build_inventory(df, root)
    _build_signals(df, root)
    _influencer_block(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
