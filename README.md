# Supply chain analytics

End-to-end demo that connects **MODEL1** (tabular demand: Random Forest / XGBoost / LightGBM winner saved as `best_model.pkl`) and **MODEL2** (seven influencer lift regressors) to a **FastAPI** backend and a **Vite + React + Tailwind** control-tower UI. The **LSTM notebook** is not used in this pipeline.

## Prerequisites

- Python 3.10+
- Node 18+
- Notebook outputs: `ws_demand_dataset/ml_ready_data.csv`, optional `ws_model/best_model.pkl` + `feature_cols.pkl`, optional `features_engineered.csv` + `models/*_best.pkl`

## 1. Generate demand data and train MODEL1

Open and run [`MODEL1_XGBOOST.ipynb`](MODEL1_XGBOOST.ipynb) through the dataset, feature-engineering, and training cells. This creates:

- `ws_demand_dataset/ml_ready_data.csv`
- `ws_model/best_model.pkl` and `ws_model/feature_cols.pkl`

## 2. (Optional) Train MODEL2

Run [`MODEL2_ML.ipynb`](MODEL2_ML.ipynb) to produce `features_engineered.csv`, `models/{target}_best.pkl`, and `models/{target}_features.json`. The dashboard shows influencer RMSE bars when `analytics/influencer_metrics.json` exists.

**Quick demo (no notebook):** from the repo root, train seven sklearn models on synthetic data (no CatBoost) and write the same file layout:

```bash
python scripts/seed_and_train_influencer_demo.py
```

Then run step 3 and **restart** the API so it reloads the new `models/*.pkl` files.

## 3. Build analytics and case-study tables

From the **repository root**:

```bash
python scripts/build_case_study_tables.py
```

This writes:

- `analytics/demand_with_predictions.csv` — MODEL1 predictions (or a rolling fallback if pickles are missing)
- `analytics/sales_timeseries.csv`
- `data/inventory.csv` — synthetic inventory with deliberate stockout/overstock stress cases
- `data/signals.csv` — daily social/search-style signals per SKU
- `analytics/influencer_metrics.json` and `analytics/influencer_sample.csv` when MODEL2 artifacts exist

## 4. Run the API

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# If influencer models were trained with CatBoost, also: pip install catboost
copy .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On macOS/Linux use `source .venv/bin/activate` and `cp` instead of `copy`.

Optional: set `PROJECT_ROOT` in `backend/.env` if you start uvicorn from another working directory.

## 5. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`. Open the printed local URL (usually `http://localhost:5173`).

To call a remote API instead, set `VITE_API_URL` in `frontend/.env`.

## API overview

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Artifact and model load status |
| GET | `/api/kpis/dashboard` | Aggregated KPIs |
| GET | `/api/meta/skus` | SKU list |
| GET | `/api/demand/timeseries?sku_id=` | Actual vs predicted |
| GET | `/api/signals/timeseries?sku_id=` | External signals |
| GET | `/api/inventory/summary` | Inventory rows |
| GET | `/api/risk/skus` | Stockout / overstock register |
| GET | `/api/brief/weekly` | Template buyer brief |
| POST | `/api/simulate` | What-if inventory drawdown |
| GET | `/api/influencer/summary` | MODEL2 metrics + loader status |

## Project layout

- `backend/app` — FastAPI application
- `frontend/` — React dashboard
- `scripts/build_case_study_tables.py` — ETL and synthetic inventory/signals
