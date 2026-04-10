"""Create minimal ml_ready_data.csv when notebooks have not been run locally."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "ws_demand_dataset"
OUT_FILE = OUT_DIR / "ml_ready_data.csv"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    skus = [
        ("WS-CI-001", "WS", "Cookware"),
        ("PB-BD-001", "PB", "Bedding"),
        ("WE-DC-001", "WE", "Decor"),
    ]
    base_map = {"WS-CI-001": 25.0, "PB-BD-001": 40.0, "WE-DC-001": 60.0}
    rows: list[dict] = []
    for sku, brand, cat in skus:
        base = base_map[sku]
        for i, d in enumerate(dates):
            u = max(0, int(base + 8 * np.sin(i / 18) + rng.normal(0, 10)))
            rows.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "sku_id": sku,
                    "brand_id": brand,
                    "category": cat,
                    "units_sold": u,
                }
            )
    df = pd.DataFrame(rows)
    df.to_csv(OUT_FILE, index=False)
    print(f"[ok] Wrote {OUT_FILE} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
