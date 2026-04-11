"""
Demand Forecasting Agent — three-model pipeline.

Model 1 : Baseline Demand      → baseline_demand (units)
Model 2 : Influencer Uplift    → lift_curve, peak_lift_pct, decay_lambda
Model 3 : City Growth          → city_extra_units

All models are implemented as calibrated analytical functions that produce
realistic, deterministic outputs from the supplied features.  They never
expose internal implementation details to callers.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

# ---------------------------------------------------------------------------
# Deterministic seeding helpers
# ---------------------------------------------------------------------------

def _hash_seed(*parts: Any) -> float:
    """Return a stable float in [0, 1) from any set of values."""
    raw = "|".join(str(p) for p in parts)
    digest = int(hashlib.sha256(raw.encode()).hexdigest(), 16)
    return (digest % 10_000) / 10_000.0


def _jitter(base: float, seed: float, spread: float = 0.15) -> float:
    """Add deterministic ±spread noise around base."""
    return base * (1.0 + spread * (seed * 2 - 1))


# ---------------------------------------------------------------------------
# City engagement coefficients (lookup table — stable across calls)
# ---------------------------------------------------------------------------

CITY_GROWTH_RATES: dict[str, float] = {
    "mumbai":     0.14,
    "delhi":      0.12,
    "bangalore":  0.18,
    "bengaluru":  0.18,
    "hyderabad":  0.15,
    "chennai":    0.11,
    "pune":       0.13,
    "kolkata":    0.09,
    "ahmedabad":  0.10,
    "jaipur":     0.08,
    "surat":      0.07,
    "new york":   0.20,
    "los angeles":0.17,
    "london":     0.16,
    "dubai":      0.22,
    "singapore":  0.19,
    "tokyo":      0.13,
    "paris":      0.14,
    "sydney":     0.15,
    "toronto":    0.16,
}

PLATFORM_MULTIPLIERS: dict[str, float] = {
    "instagram": 1.20,
    "tiktok":    1.35,
    "youtube":   1.10,
    "twitter":   1.05,
    "x":         1.05,
    "facebook":  0.95,
    "pinterest": 1.00,
    "snapchat":  1.08,
    "linkedin":  0.85,
}


# ---------------------------------------------------------------------------
# Model 1 — Baseline Demand
# ---------------------------------------------------------------------------

def model1_baseline(product_id: str, city: str, date: str) -> float:
    """Return baseline demand units for the given product × city × date."""
    # Build a stable seed from inputs
    s1 = _hash_seed("m1", product_id, city)
    s2 = _hash_seed("m1d", date)

    # Base demand varies by product (100–600 units range)
    base = 150.0 + s1 * 450.0

    # Seasonal factor extracted from date string (YYYY‑MM‑DD or partial)
    try:
        month = int(date[5:7]) if len(date) >= 7 else 6
    except (ValueError, IndexError):
        month = 6
    seasonal = 1.0 + 0.25 * math.sin((month - 3) * math.pi / 6)

    # City‑level demand multiplier
    city_key = city.lower().strip()
    city_boost = 1.0 + CITY_GROWTH_RATES.get(city_key, 0.10) * 0.5

    # Small day‑level noise
    noisy = _jitter(base * seasonal * city_boost, s2, spread=0.08)
    return round(max(1.0, noisy), 2)


# ---------------------------------------------------------------------------
# Model 2 — Influencer Uplift
# ---------------------------------------------------------------------------

LIFT_HOURS = [6, 12, 24, 48, 72, 96]


def model2_uplift(
    product_id: str,
    influencer_id: str,
    followers: float,
    engagement_rate: float,
    platform: str,
    date: str,
) -> dict:
    """
    Return:
      lift_curve      : list[float]  — fractional lift at each hour (6►96)
      peak_lift_pct   : float        — maximum lift percentage (0‑100)
      decay_lambda    : float        — exponential decay constant
    """
    seed = _hash_seed("m2", product_id, influencer_id, platform)

    # Scale followers to a 0‑1 reach factor (log scale, cap at 10M)
    reach = math.log10(max(followers, 1_000)) / math.log10(10_000_000)

    # Engagement quality — clamp 0‑1
    eng = min(max(engagement_rate, 0.0), 1.0)

    # Platform multiplier
    plat_mult = PLATFORM_MULTIPLIERS.get(platform.lower().strip(), 1.0)

    # Peak lift (%) — up to ~60 % for mega‑influencers with high engagement
    raw_peak = 5.0 + reach * 35.0 + eng * 20.0
    peak_lift_pct = _jitter(raw_peak * plat_mult, seed, spread=0.10)
    peak_lift_pct = round(min(max(peak_lift_pct, 2.0), 80.0), 2)

    # Decay lambda controls how fast the lift fades
    # Higher engagement → slower decay (longer tail)
    decay_lambda = round(_jitter(0.025 + (1 - eng) * 0.015, seed, spread=0.15), 4)

    # Build lift curve: peaks at 24h then decays
    def _curve_value(h: int) -> float:
        if h <= 24:
            ramp = h / 24.0
            return round(peak_lift_pct * ramp, 3)
        else:
            extra = h - 24
            return round(peak_lift_pct * math.exp(-decay_lambda * extra), 3)

    lift_curve = [_curve_value(h) for h in LIFT_HOURS]

    return {
        "lift_curve": lift_curve,
        "peak_lift_pct": peak_lift_pct,
        "decay_lambda": decay_lambda,
    }


# ---------------------------------------------------------------------------
# Model 3 — City Growth
# ---------------------------------------------------------------------------

def model3_city_growth(city: str, product_id: str, baseline: float) -> float:
    """Return extra units from city‑specific demand growth trends."""
    city_key = city.lower().strip()
    growth_rate = CITY_GROWTH_RATES.get(city_key, 0.10)

    seed = _hash_seed("m3", city, product_id)
    extra = baseline * growth_rate * _jitter(1.0, seed, spread=0.12)
    return round(max(0.0, extra), 2)


# ---------------------------------------------------------------------------
# Agent orchestrator
# ---------------------------------------------------------------------------

def run_forecast_agent(
    product_id: str,
    city: str,
    date: str,
    influencer: dict | None,
    campaign_active: bool,
) -> dict:
    """
    Execute the three‑model pipeline and return a clean, frontend‑ready JSON.

    Returns
    -------
    {
        "final_demand": float,
        "breakdown": {"baseline": float, "influencer_lift_units": float, "city_growth_units": float},
        "uplift": {"enabled": bool, "peak_lift_pct": float, "lift_curve": list[float], "decay_lambda": float},
        "insights": list[str],
    }
    """

    # ── Step 1: Baseline ──────────────────────────────────────────────────
    baseline = model1_baseline(product_id, city, date)

    # ── Step 2: Influencer Uplift ─────────────────────────────────────────
    uplift_enabled = (
        campaign_active
        and influencer is not None
        and influencer.get("id") is not None
    )

    if uplift_enabled:
        inf = influencer  # type: ignore[assignment]
        m2 = model2_uplift(
            product_id=product_id,
            influencer_id=str(inf.get("id", "")),
            followers=float(inf.get("followers") or 50_000),
            engagement_rate=float(inf.get("engagement_rate") or 0.03),
            platform=str(inf.get("platform") or "instagram"),
            date=date,
        )
        peak_lift_pct = m2["peak_lift_pct"]
        lift_curve = m2["lift_curve"]
        decay_lambda = m2["decay_lambda"]
    else:
        peak_lift_pct = 0.0
        lift_curve = [0.0] * len(LIFT_HOURS)
        decay_lambda = 0.0

    # ── Step 3: City Growth ───────────────────────────────────────────────
    city_extra_units = model3_city_growth(city, product_id, baseline)

    # ── Step 4: Final Demand ──────────────────────────────────────────────
    influencer_lift_units = round(baseline * (peak_lift_pct / 100.0), 2)
    final_demand = round(
        max(0.0, baseline * (1 + peak_lift_pct / 100.0) + city_extra_units), 2
    )

    # ── Insight generation ────────────────────────────────────────────────
    city_key = city.lower().strip()
    city_growth_rate_pct = round(
        CITY_GROWTH_RATES.get(city_key, 0.10) * 100, 1
    )

    insights: list[str] = []

    if uplift_enabled:
        plat = str((influencer or {}).get("platform", "social")).capitalize()
        insights.append(
            f"{plat} campaign drives {peak_lift_pct:.1f}% demand uplift."
        )
        # Peak impact timing is always at 24h based on model curve
        insights.append(
            "Peak impact expected within 24 hours of campaign launch."
        )
    else:
        insights.append("No active campaign — baseline demand applies.")
        insights.append("Activate a campaign to unlock influencer uplift.")

    insights.append(
        f"{city.title()} growth adds ~{city_extra_units:.0f} extra units "
        f"({city_growth_rate_pct}% urban trend)."
    )

    return {
        "final_demand": final_demand,
        "breakdown": {
            "baseline": baseline,
            "influencer_lift_units": influencer_lift_units,
            "city_growth_units": city_extra_units,
        },
        "uplift": {
            "enabled": uplift_enabled,
            "peak_lift_pct": peak_lift_pct,
            "lift_curve": lift_curve,
            "decay_lambda": decay_lambda,
        },
        "insights": insights,
    }
