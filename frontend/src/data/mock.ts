import type { FloodStatus, HistoryPoint, ModelInfo } from "@/types/floodshield";

export const MOCK_STATUS: FloodStatus = {
  date: "2026-09-04",
  river: "CHENAB",
  station: "MARALA",
  current_inflow: 51.9,
  current_outflow: 26.1,
  ffd_forecast_min: 100,
  ffd_forecast_max: 120,
  ffd_forecast_text: "100–120",
  current_danger: "Normal",
  ffd_forecast_risk: "Low",
  ml_next_day_risk: "Normal",
  ml_confidence: 72.3,
  final_alert: "Low",
  english_alert:
    "Flood risk is currently Low on the Chenab River at Marala. Water inflow is 51.9 thousand cusecs and outflow is 26.1 thousand cusecs. The forecast for the next 24 hours shows inflow rising to 100–120 thousand cusecs, but the overall risk remains Low. The machine-learning model predicts Normal conditions for tomorrow. Follow official government instructions. This alert is based on current data and models; conditions may change.",
  urdu_alert:
    "چناب ندی مارالہ پر فلڈ کا خطرہ ابھی کم ہے۔ آب کا داخلہ 51.9 ہزار کیوسکس ہے اور باہر جانے والا آب 26.1 ہزار کیوسکس ہے۔ اگلے 24 گھنٹوں کے لیے توقع ہے کہ داخلہ 100-120 ہزار کیوسکس تک بڑھ جائے، لیکن کلی طور پر خطرہ کم رہے گا۔ ماشین لرننگ ماڈل نے کل کے لیے عام حالات کی پیش گوئی کی ہے۔ حکومتی ہدایات کی پیروی کریں۔ یہ انتباہ موجودہ ڈیٹا اور ماڈلز پر مبنی ہے؛ حالات تبدیل ہو سکتے ہیں۔",
  alert_generated_by: "Qwen",
};

export const MOCK_HISTORY: HistoryPoint[] = [
  { date: "2026-08-28", inflow: 35.0, outflow: 50.0, status: "Normal" },
  { date: "2026-08-29", inflow: 36.1, outflow: 60.0, status: "Normal" },
  { date: "2026-08-30", inflow: 41.2, outflow: 70.0, status: "Normal" },
  { date: "2026-08-31", inflow: 36.1, outflow: 60.0, status: "Normal" },
  { date: "2026-09-01", inflow: 36.1, outflow: 60.0, status: "Normal" },
  { date: "2026-09-02", inflow: 41.2, outflow: 60.0, status: "Normal" },
  { date: "2026-09-03", inflow: 36.1, outflow: 60.0, status: "Normal" },
  {
    date: "2026-09-04",
    inflow: 51.9,
    outflow: 26.1,
    forecast_min: 100,
    forecast_max: 120,
    forecast_text: "100–120",
    status: "Low",
  },
];

export const MOCK_MODEL_INFO: ModelInfo = {
  training_data: "2024–2025",
  testing_evaluation: "2026",
  river: "Chenab",
  station: "Marala",
  data_source: "FFD / PMD",
  ml_engine: "Flood Risk Classification",
  generative_ai: "Qwen",
  live_data: "FFD Bulletin",
  output: "Bilingual Early Warning",
  accuracy: null,
  precision: null,
  recall: null,
  f1_score: null,
};
