export type RiskLevel =
  | "Normal"
  | "Low"
  | "Medium"
  | "Moderate"
  | "High"
  | "Very High"
  | "Severe"
  | "Extreme"
  | string;

export interface FloodStatus {
  date: string;
  river: string;
  station: string;
  current_inflow: number;
  current_outflow: number;
  ffd_forecast_min: number;
  ffd_forecast_max: number;
  ffd_forecast_text: string;
  current_danger: RiskLevel;
  ffd_forecast_risk: RiskLevel;
  ml_next_day_risk: RiskLevel;
  ml_confidence: number;
  final_alert: RiskLevel;
  english_alert: string;
  urdu_alert: string;
  alert_generated_by: string;
}

export interface HistoryPoint {
  date: string;
  inflow: number;
  outflow: number;
  forecast_min?: number | null;
  forecast_max?: number | null;
  forecast_text?: string | null;
  status?: RiskLevel | null;
}

export interface ModelInfo {
  training_data?: string;
  testing_evaluation?: string;
  river?: string;
  station?: string;
  data_source?: string;
  ml_engine?: string;
  generative_ai?: string;
  live_data?: string;
  output?: string;
  accuracy?: number | null;
  precision?: number | null;
  recall?: number | null;
  f1_score?: number | null;
}

export type DataSourceMode = "api" | "mock" | "loading" | "error" | "empty";

export interface DashboardData {
  status: FloodStatus | null;
  history: HistoryPoint[];
  modelInfo: ModelInfo | null;
  mode: DataSourceMode;
  lastFetchedAt: string | null;
  errorMessage: string | null;
}
