from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import (
    BriefResponse,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    SimulateRequest,
    SimulateResponse,
    SimulatePoint,
)
from app.services import artifacts, tables
from app.services.brief import build_weekly_brief
from app.services.demand_agent import run_forecast_agent
from app.services.risk_engine import compute_risks, count_signal_spikes

_state: dict[str, Any] = {
    "model1": None,
    "feature_cols": None,
    "model2": {},
    "model2_feats": {},
    "load_messages": [],
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    m, f, msgs = artifacts.try_load_model1()
    _state["model1"] = m
    _state["feature_cols"] = f
    m2, m2f, m2msgs = artifacts.try_load_model2_bundle()
    _state["model2"] = m2
    _state["model2_feats"] = m2f
    _state["load_messages"] = msgs + m2msgs
    yield


app = FastAPI(title="Supply Chain Analytics API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _demand_frame() -> pd.DataFrame | None:
    df = tables.load_demand_predictions()
    if df is not None:
        return df
    return tables.load_sales_fallback()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    msgs = list(_state["load_messages"])
    pred = settings.demand_predictions_path().is_file()
    inv = settings.inventory_path().is_file()
    sig = settings.signals_path().is_file()
    inf = settings.influencer_metrics_path().is_file()
    if not pred:
        msgs.append("Run scripts/build_case_study_tables.py to create analytics/demand_with_predictions.csv")
    m1_ok = _state["model1"] is not None and _state["feature_cols"] is not None
    return HealthResponse(
        ok=pred and inv and sig,
        model1_loaded=m1_ok,
        model2_targets_loaded=len(_state["model2"]),
        demand_predictions_present=pred,
        inventory_present=inv,
        signals_present=sig,
        influencer_metrics_present=inf,
        messages=msgs[:20],
    )


@app.get("/api/meta/skus")
def meta_skus() -> dict[str, Any]:
    df = _demand_frame()
    if df is None:
        raise HTTPException(503, "No demand data. Generate ws_demand_dataset and analytics first.")
    sub = df[["sku_id", "category"]].drop_duplicates().sort_values("sku_id")
    return {"skus": sub.to_dict(orient="records"), "count": len(sub)}


@app.get("/api/demand/timeseries")
def demand_timeseries(
    sku_id: str = Query(..., description="SKU identifier"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
) -> dict[str, Any]:
    df = _demand_frame()
    if df is None:
        raise HTTPException(503, "No demand data available.")
    d = df[df["sku_id"] == sku_id].copy()
    if d.empty:
        raise HTTPException(404, f"Unknown sku_id: {sku_id}")
    d["date"] = pd.to_datetime(d["date"])
    if date_from:
        d = d[d["date"] >= pd.to_datetime(date_from)]
    if date_to:
        d = d[d["date"] <= pd.to_datetime(date_to)]
    d = d.sort_values("date")
    cols = ["date", "units_sold", "predicted_units"]
    use = [c for c in cols if c in d.columns]
    out = d[use].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return {"sku_id": sku_id, "points": out.to_dict(orient="records")}


@app.get("/api/signals/timeseries")
def signals_timeseries(
    sku_id: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
) -> dict[str, Any]:
    df = tables.load_signals()
    if df is None:
        raise HTTPException(503, "No signals.csv — run the ETL script.")
    s = df.copy()
    s["date"] = pd.to_datetime(s["date"])
    if sku_id:
        s = s[s["sku_id"] == sku_id]
    if date_from:
        s = s[s["date"] >= pd.to_datetime(date_from)]
    if date_to:
        s = s[s["date"] <= pd.to_datetime(date_to)]
    s = s.sort_values("date")
    s["date"] = s["date"].dt.strftime("%Y-%m-%d")
    return {"points": s.to_dict(orient="records")}


@app.get("/api/inventory/summary")
def inventory_summary() -> dict[str, Any]:
    df = tables.load_inventory()
    if df is None:
        raise HTTPException(503, "No inventory.csv — run the ETL script.")
    inv = df.copy()
    inv["available"] = inv["stock_on_hand"] + inv["on_order"]
    by_wh = inv.groupby("warehouse_id").agg({"available": "sum", "sku_id": "nunique"}).reset_index()
    by_wh.columns = ["warehouse_id", "total_available_units", "sku_count"]
    return {
        "rows": inv.to_dict(orient="records"),
        "by_warehouse": by_wh.to_dict(orient="records"),
    }


@app.get("/api/risk/skus")
def risk_skus() -> dict[str, Any]:
    demand = _demand_frame()
    inv = tables.load_inventory()
    if demand is None or inv is None:
        raise HTTPException(503, "Need demand predictions and inventory.csv.")
    risks = compute_risks(demand, inv)
    return {"risks": risks, "count": len(risks)}


@app.get("/api/brief/weekly", response_model=BriefResponse)
def brief_weekly() -> BriefResponse:
    demand = _demand_frame()
    inv = tables.load_inventory()
    sig = tables.load_signals()
    if demand is None or inv is None:
        raise HTTPException(503, "Need demand and inventory for brief generation.")
    return build_weekly_brief(demand, inv, sig)


@app.post("/api/simulate", response_model=SimulateResponse)
def simulate(body: SimulateRequest) -> SimulateResponse:
    demand = _demand_frame()
    inv = tables.load_inventory()
    if demand is None or inv is None:
        raise HTTPException(503, "Need demand and inventory.")
    row = inv[(inv["sku_id"] == body.sku_id) & (inv["warehouse_id"] == body.warehouse_id)]
    if row.empty:
        raise HTTPException(404, "SKU / warehouse combination not found.")
    r = row.iloc[0]
    stock = float(r["stock_on_hand"]) + float(r["on_order"]) + float(body.extra_on_order)
    lead = max(1, int(r["lead_time_days"]) + int(body.lead_time_delta_days))

    sku_d = demand[demand["sku_id"] == body.sku_id].sort_values("date")
    if sku_d.empty:
        raise HTTPException(404, "No demand history for SKU.")
    tail = sku_d.tail(28)
    run = float(tail["predicted_units"].fillna(tail["units_sold"]).mean())
    if pd.isna(run) or run <= 0:
        run = float(tail["units_sold"].mean()) or 0.01

    assumptions = [
        f"Mean daily demand rate fixed at {run:.2f} units (from recent predicted/actual blend).",
        f"Lead time baseline {int(r['lead_time_days'])}d adjusted by {body.lead_time_delta_days}d → using {lead}d horizon for burn.",
        "Inventory projection is linear drawdown for illustration — not a stochastic simulation.",
    ]

    points: list[SimulatePoint] = []
    remaining = stock
    horizon = 14
    for day in range(1, horizon + 1):
        remaining = max(0.0, remaining - run)
        points.append(SimulatePoint(day=day, projected_stock=round(remaining, 2)))

    return SimulateResponse(
        sku_id=body.sku_id,
        warehouse_id=body.warehouse_id,
        assumptions=assumptions,
        points=points,
        final_projected_stock=points[-1].projected_stock,
    )


@app.get("/api/influencer/summary")
def influencer_summary() -> dict[str, Any]:
    metrics = tables.load_influencer_metrics()
    sample = tables.load_influencer_sample()
    out: dict[str, Any] = {
        "metrics": metrics,
        "models_loaded": list(_state["model2"].keys()),
        "sample_rows": 0,
        "distribution": None,
    }
    if sample is not None and not sample.empty and "peak_lift_pct" in sample.columns:
        out["sample_rows"] = len(sample)
        pred_col = "peak_lift_pct_pred" if "peak_lift_pct_pred" in sample.columns else None
        if pred_col:
            out["distribution"] = {
                "peak_lift_pct_actual_mean": float(sample["peak_lift_pct"].mean()),
                "peak_lift_pct_pred_mean": float(sample[pred_col].mean()),
            }
    return out


@app.get("/api/kpis/dashboard")
def kpis_dashboard() -> dict[str, Any]:
    demand = _demand_frame()
    inv = tables.load_inventory()
    sig = tables.load_signals()
    risks = []
    if demand is not None and inv is not None:
        risks = compute_risks(demand, inv)
    spikes = count_signal_spikes(sig) if sig is not None else 0
    return {
        "stockout_skus": len([r for r in risks if r["risk_type"] == "stockout"]),
        "overstock_skus": len([r for r in risks if r["risk_type"] == "overstock"]),
        "signal_spikes": spikes,
        "total_inventory_skus": len(inv) if inv is not None else 0,
    }


@app.post("/api/demand/forecast", response_model=ForecastResponse)
def demand_forecast(body: ForecastRequest) -> ForecastResponse:
    """Three-model demand forecasting agent endpoint."""
    result = run_forecast_agent(
        product_id=body.product_id,
        city=body.city,
        date=body.date,
        influencer=body.influencer.model_dump() if body.influencer else None,
        campaign_active=body.campaign_active,
    )
    return ForecastResponse(**result)
