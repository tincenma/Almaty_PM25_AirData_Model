export type ModelFamily = 'XGBoost' | 'Ridge'
export type Metric = {
  horizon_hours: number; model: string; MAE: number; RMSE: number; R2: number;
  MAE_improvement_vs_persistence_pct: number; fit_seconds: number
}
export type SeasonMetric = { horizon_hours: number; model: string; season: string; MAE: number; RMSE: number; n: number }
export type Overview = {
  station: { id: string; name: string; city: string; latitude: number; longitude: number };
  horizons: number[]; models: ModelFamily[]; default_origin: string; available_dates: string[];
  eligible_origins: number; observed_hours: number; coverage_pct: number;
  metrics: Metric[]; seasons: SeasonMetric[];
  periods: { start: string; train_end: string; validation_end: string; test_end: string };
  dataset: { commit: string; sha256: string; attribution: string; license: string }
}
export type Forecast = {
  origin: string; model: ModelFamily; station_id: string; current_pm25: number;
  input_coverage_24h: number;
  history: { time: string; value: number | null }[];
  outcomes: { time: string; value: number | null }[];
  forecasts: { horizon_hours: number; target_time: string; predicted: number; observed: number }[]
}

export type StationInfo = {
  id: string; name: string; source: string; source_name: string;
  latitude: number | null; longitude: number | null;
  latest_measurement: string; latest_pm25: number | null;
  first_measurement: string; records: number;
  reporting_status: 'recent' | 'not_recent' | 'unknown'; model_available: boolean;
}
export type StationCatalog = {
  checked_at: string | null; dataset_commit: string | null; source_url: string | null;
  trained_station: StationInfo | null; stations: StationInfo[]; refresh_error: string | null;
  current_model_station?: StationInfo | null;
}

export type LatestForecast = {
  station: {station_id: string; station_name: string; source: string};
  origin: string; generated_at: string; age_hours: number; stale: boolean;
  current_pm25: number; input_coverage_24h: number; input_coverage_168h: number;
  history: {time: string; value: number | null}[];
  forecasts: {horizon_hours: number; target_time: string; predicted: number; target_is_past: boolean; model: ModelFamily}[];
  metrics: {horizon_hours: number; model: string; MAE: number; RMSE: number; R2: number; samples: number}[];
  refresh_error: string | null; trained_at: string; test_start: string;
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}). Please try again.`)
  }
  return response.json() as Promise<T>
}

export const forecastRequest = (origin: string, model: ModelFamily) => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ origin, model }),
})

