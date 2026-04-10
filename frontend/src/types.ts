export type Health = {
  ok: boolean;
  model1_loaded: boolean;
  model2_targets_loaded: number;
  demand_predictions_present: boolean;
  inventory_present: boolean;
  signals_present: boolean;
  influencer_metrics_present: boolean;
  messages: string[];
};

export type Kpis = {
  stockout_skus: number;
  overstock_skus: number;
  signal_spikes: number;
  total_inventory_skus: number;
};

export type Risk = {
  sku_id: string;
  warehouse_id: string;
  risk_type: string;
  severity: number;
  weeks_of_cover: number;
  expected_demand_in_lead_time: number;
  available_units: number;
  lead_time_days: number;
  reasons: string[];
};

export type Brief = {
  title: string;
  summary: string;
  bullets: string[];
  stockout_count: number;
  overstock_count: number;
  signal_spikes: number;
  generated_at: string;
};

export type SkuMeta = { sku_id: string; category: string };
