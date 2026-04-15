# Supply chain analytics platform

This project is a full-stack supply chain analytics dashboard that integrates multiple machine learning models to provide demand forecasting, inventory risk management, and what-if simulations. It connects a Python FastAPI backend with a React-based frontend dashboard.

## Machine learning pipeline

The system uses a three-model pipeline to generate high-fidelity demand forecasts:

1.  **Baseline Model (Model 1)**: An XGBoost regressor trained on historical tabular demand data. It captures multi-year seasonality and product-specific trends.
2.  **Influencer Uplift (Model 2)**: A multi-target regressor bundle that predicts peak uplift and decay curves triggered by influencer marketing campaigns across various social platforms.
3.  **City Growth (Conti Model)**: A LightGBM model that incorporates external economic indicators (income velocity, home prices, and affordability ratios) to adjust demand forecasts based on local city-level growth.

## Prerequisites

- Python 3.10+
- Node.js 18+
- Active internet connection for Google Fonts and Tailwind CSS

## Getting started

### 1. Initialize data and models

Before running the dashboard, you must generate the required datasets and train the models. From the repository root, run the following scripts in sequence:

```bash
# Train the City Growth (Conti) model
python conti_script.py

# Train the Baseline XGBoost model
python model1_script.py

# Train the Influencer Uplift model bundle (demo version)
python scripts/seed_and_train_influencer_demo.py

# Generate analytics tables and inventory datasets
python scripts/build_case_study_tables.py
```

### 2. Start the backend

The backend is built with FastAPI and handles all ML inference and data aggregation.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. Start the frontend

The frontend is a React application powered by Vite and Tailwind CSS.

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at http://127.0.0.1:5173.

## Main features

### Demand forecasting agent
The agent provides a real-time forecast by combining the outputs of the three-model pipeline. It includes visual feedback such as loading overlays and success notifications to ensure high-fidelity interactions.

### Unified risk register
Automatically identifies SKUs at risk of stockout or overstock by comparing current inventory levels against lead times and predicted demand volatility.

### What-if simulation
Allows for real-time inventory drawdown simulations. Unlike simple linear models, this simulation uses the specific daily variable forecasts from the XGBoost model to show detailed projected stock levels over a 14-day horizon.

## API reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | /api/health | Verifies status of models and data files |
| GET | /api/kpis/dashboard | Returns key supply chain metrics |
| GET | /api/meta/skus | Provides a list of available products |
| GET | /api/demand/timeseries | Actual vs predicted demand history |
| POST | /api/demand/forecast | Executes the 3-model forecasting agent |
| POST | /api/simulate | Runs a model-driven inventory simulation |
| GET | /api/brief/weekly | Generates an AI-driven buyer brief |

## Project structure

- **backend/**: FastAPI application, schemas, and ML inference services.
- **frontend/**: React components, Recharts visualizations, and dashboard pages.
- **models/**: Trained model artifacts (.pkl).
- **analytics/**: Processed data tables and prediction results.
- **scripts/**: ETL processes and data sanitization utilities.
