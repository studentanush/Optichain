from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool
    model1_loaded: bool
    model2_targets_loaded: int
    conti_model_loaded: bool
    demand_predictions_present: bool
    inventory_present: bool
    signals_present: bool
    influencer_metrics_present: bool
    messages: list[str] = Field(default_factory=list)


class SimulateRequest(BaseModel):
    sku_id: str
    warehouse_id: str = "W1"
    extra_on_order: float = 0.0
    lead_time_delta_days: int = 0


class SimulatePoint(BaseModel):
    day: int
    projected_stock: float


class SimulateResponse(BaseModel):
    sku_id: str
    warehouse_id: str
    assumptions: list[str]
    points: list[SimulatePoint]
    final_projected_stock: float


class BriefResponse(BaseModel):
    title: str
    summary: str
    bullets: list[str]
    stockout_count: int
    overstock_count: int
    signal_spikes: int
    generated_at: str


# ── Demand Forecast Agent ──────────────────────────────────────────────────

class InfluencerInput(BaseModel):
    id: str | None = None
    followers: float | None = None
    engagement_rate: float | None = None
    platform: str | None = None


class ForecastRequest(BaseModel):
    product_id: str
    city: str
    date: str
    influencer: InfluencerInput | None = None
    campaign_active: bool = False


class ForecastBreakdown(BaseModel):
    baseline: float
    influencer_lift_units: float
    city_growth_units: float


class ForecastUplift(BaseModel):
    enabled: bool
    peak_lift_pct: float
    lift_curve: list[float]
    decay_lambda: float


class ForecastResponse(BaseModel):
    final_demand: float
    breakdown: ForecastBreakdown
    uplift: ForecastUplift
    insights: list[str]
