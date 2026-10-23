import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "ml" / "scripts"))

os.environ["FLOODSHIELD_DISABLE_QWEN"] = "1"

import floodshield_engine as engine
from train_model import (
    attach_calendar_history,
    attach_horizon_target,
    flood_risk_from_inflow,
    score_predictions,
    select_from_cv,
)


class CalendarAndLabelsTest(unittest.TestCase):
    def test_thresholds_match_ffd_bounds(self):
        self.assertEqual(flood_risk_from_inflow(99.9), "Normal")
        self.assertEqual(flood_risk_from_inflow(100), "Low")
        self.assertEqual(flood_risk_from_inflow(150), "Medium")
        self.assertEqual(flood_risk_from_inflow(200), "High")
        self.assertEqual(flood_risk_from_inflow(400), "Very High")
        self.assertEqual(flood_risk_from_inflow(600), "Exceptional")

    def test_horizon_uses_calendar_day_not_next_row(self):
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2024-06-16", "2024-06-18"]),
            "inflow_current": [40.0, 120.0],
        })
        labeled = attach_horizon_target(frame, "date", 1)
        self.assertTrue(pd.isna(labeled.iloc[0]["target_flood_risk"]))
        self.assertEqual(
            labeled.iloc[0]["target_date"],
            pd.Timestamp("2024-06-17"),
        )

        consecutive = pd.DataFrame({
            "date": pd.to_datetime(["2024-06-16", "2024-06-17"]),
            "inflow_current": [40.0, 120.0],
        })
        labeled = attach_horizon_target(consecutive, "date", 1)
        self.assertEqual(labeled.iloc[0]["target_flood_risk"], "Low")
        self.assertTrue(pd.isna(labeled.iloc[1]["target_flood_risk"]))

    def test_season_gap_is_not_a_one_day_lag(self):
        frame = pd.DataFrame({
            "date": pd.to_datetime(["2024-10-15", "2025-06-15"]),
            "inflow_current": [80.0, 50.0],
        })
        history = attach_calendar_history(frame, "date")
        june = history.iloc[-1]
        self.assertTrue(pd.isna(june["inflow_lag_1"]))
        self.assertNotEqual(june["inflow_lag_1"], 80.0)


class ModelSelectionTest(unittest.TestCase):
    def test_accuracy_does_not_overrule_macro_f1(self):
        choice, _basis = select_from_cv([
            {
                "name": "Majority baseline",
                "cv_macro_f1": 0.40,
                "cv_minority_recall": 0.0,
                "cv_accuracy": 0.99,
            },
            {
                "name": "Random Forest (balanced)",
                "cv_macro_f1": 0.62,
                "cv_minority_recall": 0.35,
                "cv_accuracy": 0.70,
            },
        ])
        self.assertEqual(choice, "Random Forest (balanced)")

    def test_minority_recall_breaks_a_macro_f1_tie(self):
        choice, _basis = select_from_cv([
            {
                "name": "Random Forest (unweighted)",
                "cv_macro_f1": 0.50,
                "cv_minority_recall": 0.10,
                "cv_accuracy": 0.99,
            },
            {
                "name": "Random Forest (balanced)",
                "cv_macro_f1": 0.50,
                "cv_minority_recall": 0.60,
                "cv_accuracy": 0.40,
            },
        ])
        self.assertEqual(choice, "Random Forest (balanced)")

    def test_absent_and_unsupported_classes_are_not_scored_as_skill(self):
        scored = score_predictions(
            ["Normal", "Normal", "Normal"],
            ["Normal", "Normal", "Normal"],
            "Normal",
            unsupported_classes=["Very High", "Exceptional"],
        )
        self.assertEqual(scored["accuracy"], 1.0)
        self.assertIsNone(scored["minority_recall"])
        self.assertFalse(scored["evaluation_reliable"])
        self.assertIn("Very High", scored["classes_absent_from_evaluation"])
        self.assertEqual(
            scored["per_class"]["Very High"]["status"],
            "unsupported_not_scored",
        )
        self.assertIsNone(scored["per_class"]["Very High"]["recall"])


class RiskAndOutlookTest(unittest.TestCase):
    def setUp(self):
        engine._qwen_runtime["blocked_reason"] = None
        os.environ["FLOODSHIELD_DISABLE_QWEN"] = "1"

    def test_official_warning_is_not_downgraded(self):
        self.assertEqual(
            engine.higher_risk(["Normal", "Low", "Medium"]),
            "Medium",
        )
        self.assertEqual(
            engine.determine_final_risk("Low", "High", "Normal"),
            "High",
        )
        self.assertEqual(
            engine.official_category_from_text("Below Low"),
            "Normal",
        )
        self.assertEqual(
            engine.official_category_from_text(
                "Exceptionally High flood is expected."
            ),
            "Exceptional",
        )

    def test_weekly_outlook_applies_only_inside_its_dates(self):
        outlook = {
            "category": "Medium",
            "start_date": "2026-10-23",
            "end_date": "2026-10-25",
            "flood_text": "Medium flood",
        }
        inside, _text = engine.official_category_for_date(
            outlook,
            datetime(2026, 10, 24).date(),
        )
        outside, _text = engine.official_category_for_date(
            outlook,
            datetime(2026, 10, 27).date(),
        )
        self.assertEqual(inside, "Medium")
        self.assertIsNone(outside)

    def test_outlook_dates_start_the_day_after_the_issue_date(self):
        engine.karachi_today = lambda: datetime(2026, 10, 22).date()
        outlook = engine.build_seven_day_outlook(
            issue_date="2026-10-22",
            current_risk="Normal",
            forecast_risk="Low",
            forecast_text="100 - 120",
            forecast_level="Low",
            forecast_low=100,
            forecast_high=120,
            ml_prediction="Normal",
            ml_probabilities={"Normal": 0.8},
            ml_horizons=[],
            jammu={"available": False, "forecasts": [], "error": "HTTP 403"},
            ffd_outlook={
                "category": "Medium",
                "start_date": "2026-10-23",
                "end_date": "2026-10-25",
                "flood_text": "Medium",
                "meteorological_text": "",
                "next_bulletin": None,
            },
            final_risk="Low",
            current_inflow=51.9,
            current_outflow=26.1,
            source_url="https://ffd.pmd.gov.pk/bulletin",
        )
        dates = [day["forecast_date"] for day in outlook["days"]]
        self.assertEqual(dates[0], "2026-10-23")
        self.assertEqual(dates[-1], "2026-10-29")
        self.assertEqual(len(dates), 7)
        self.assertEqual(outlook["days"][0]["final_risk"], "Low")
        self.assertEqual(outlook["days"][1]["final_risk"], "Medium")
        self.assertEqual(outlook["days"][5]["final_risk"], "Insufficient data")
        self.assertNotEqual(outlook["days"][5]["final_risk"], "Normal")
        self.assertFalse(outlook["days"][0]["expired"])
        self.assertEqual(
            outlook["days"][0]["alert"]["generated_by"],
            "FloodShield templates",
        )
        self.assertNotEqual(outlook["days"][0]["alert"]["qwen_status"], "success")

    def test_expired_bulletin_is_not_called_current(self):
        engine.karachi_today = lambda: datetime(2026, 10, 22).date()
        status = engine.forecast_day_status(
            "2026-09-04",
            "2026-09-05",
            datetime(2026, 10, 22).date(),
        )
        self.assertEqual(status["status"], "expired")
        self.assertFalse(status["official_applies"])
        outlook = engine.build_seven_day_outlook(
            issue_date="2026-09-04",
            current_risk="Normal",
            forecast_risk="Low",
            forecast_text="100 - 120",
            forecast_level="Low",
            forecast_low=100,
            forecast_high=120,
            ml_prediction="Normal",
            ml_probabilities={},
            ml_horizons=[{
                "horizon_days": 1,
                "predicted_category": "Normal",
                "model_available": True,
                "probabilities": {},
            }],
            jammu={"available": False, "forecasts": []},
            ffd_outlook=None,
            final_risk="Low",
            current_inflow=51.9,
            current_outflow=26.1,
            source_url="https://ffd.pmd.gov.pk/bulletin",
        )
        self.assertTrue(outlook["data_freshness"]["stale"])
        for day in outlook["days"]:
            self.assertEqual(day["final_risk"], "Insufficient data")
            self.assertTrue(day["expired"])
            self.assertNotEqual(day["final_risk"], "Normal")
            self.assertIn("not a current forecast", day["alert"]["english"])

    def test_jammu_rain_does_not_change_the_flood_category(self):
        engine.karachi_today = lambda: datetime(2026, 10, 22).date()
        outlook = engine.build_seven_day_outlook(
            issue_date="2026-10-22",
            current_risk="Normal",
            forecast_risk="Low",
            forecast_text="100 - 120",
            forecast_level="Low",
            forecast_low=100,
            forecast_high=120,
            ml_prediction="Normal",
            ml_probabilities={"Normal": 0.8},
            ml_horizons=[],
            jammu={
                "available": True,
                "source_name": "open-meteo",
                "source_url": engine.OPEN_METEO_URL,
                "note": engine.JAMMU_NOTE,
                "forecasts": [{
                    "date": "2026-10-23",
                    "condition": "Rain",
                    "temperature_text": "30 / 20 °C",
                    "temperature_high_c": 30.0,
                    "temperature_low_c": 20.0,
                    "precip_chance_pct": 90,
                    "precip_amount_mm": 80.0,
                    "precip_amount_text": "80 mm",
                }],
            },
            ffd_outlook=None,
            final_risk="Low",
            current_inflow=51.9,
            current_outflow=26.1,
            source_url="https://ffd.pmd.gov.pk/bulletin",
        )
        day = outlook["days"][0]
        self.assertEqual(day["forecast_date"], "2026-10-23")
        self.assertEqual(day["final_risk"], "Low")
        self.assertEqual(day["jammu_weather"]["precip_amount_mm"], 80.0)
        self.assertFalse(day["jammu_weather"]["changes_flood_category"])
        self.assertFalse(
            outlook["jammu_extended_forecast"]["changes_flood_category"]
        )
        self.assertEqual(
            outlook["jammu_extended_forecast"]["source_name"],
            "open-meteo",
        )


class ScrapeAndQwenTest(unittest.TestCase):
    def test_forecast_range_keeps_both_ends(self):
        low, high = engine.extract_forecast_range("40-50")
        self.assertEqual((low, high), (40.0, 50.0))

    def test_history_loader_does_not_drop_ranges(self):
        original = engine.HISTORY_FILE
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "history.csv"
                dates = [
                    (datetime(2026, 6, 15) + timedelta(days=offset)).date()
                    for offset in range(8)
                ]
                pd.DataFrame({
                    "date": dates,
                    "river": ["CHENAB"] * 8,
                    "station": ["Marala"] * 8,
                    "inflow_thousands_cusecs": [40 + offset for offset in range(8)],
                    "outflow_thousands_cusecs": [20] * 8,
                    "forecast_24h_inflow": ["40-50"] * 8,
                }).to_csv(path, index=False)
                engine.HISTORY_FILE = str(path)
                frame = engine.load_recent_history_from_csv(
                    pd.Timestamp("2100-01-01"),
                    minimum_records=8,
                )
                self.assertEqual(float(frame.iloc[-1]["forecast_24h"]), 40.0)
                self.assertEqual(float(frame.iloc[-1]["forecast_high"]), 50.0)
        finally:
            engine.HISTORY_FILE = original

    def test_http_403_retries_then_succeeds_without_logging_body(self):
        calls = {"n": 0}

        class Response:
            def __init__(self, status, text):
                self.status_code = status
                self.text = text

        def get(url, headers=None, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                return Response(403, "secret page body")
            return Response(200, "M" * 80)

        text = engine.fetch_text(
            "https://example.test/bulletin",
            get,
            attempts=3,
            pause_seconds=0,
        )
        self.assertEqual(calls["n"], 3)
        self.assertEqual(text, "M" * 80)

    def test_jammu_403_does_not_invent_zero_rain(self):
        payload = engine._jammu_unavailable("HTTP 403 from timeanddate")
        self.assertFalse(payload["available"])
        self.assertEqual(payload["forecasts"], [])
        self.assertNotIn("precip_amount_mm", payload)
        missing = engine._optional_number(None, 0)
        zero = engine._optional_number([0.0], 0)
        self.assertIsNone(missing)
        self.assertEqual(zero, 0.0)

    def test_open_meteo_keeps_reported_zero_and_missing_rain(self):
        rows = engine.parse_open_meteo_daily({
            "daily": {
                "time": ["2026-10-22", "2026-10-23"],
                "weather_code": [61, None],
                "temperature_2m_max": [28.0, 27.0],
                "temperature_2m_min": [17.0, None],
                "precipitation_sum": [0.0, None],
                "precipitation_probability_max": [10, None],
            }
        })
        self.assertEqual(rows[0]["precip_amount_mm"], 0.0)
        self.assertEqual(rows[0]["condition"], "Rain")
        self.assertIsNone(rows[1]["precip_amount_mm"])
        self.assertIsNone(rows[1]["precip_chance_pct"])
        self.assertIsNone(rows[1]["condition"])

    def test_open_meteo_requests_fourteen_jammu_days(self):
        seen = {}

        class Response:
            status_code = 200

            def json(self):
                return {
                    "daily": {
                        "time": [f"2026-10-{day:02d}" for day in range(1, 15)],
                        "weather_code": [1] * 14,
                        "temperature_2m_max": [30.0] * 14,
                        "temperature_2m_min": [20.0] * 14,
                        "precipitation_sum": [1.5] * 14,
                        "precipitation_probability_max": [40] * 14,
                    }
                }

        def get(url, params=None, headers=None, timeout=None):
            seen["url"] = url
            seen["params"] = params
            return Response()

        payload = engine.fetch_open_meteo_jammu(get=get, pause_seconds=0)
        self.assertEqual(seen["url"], engine.OPEN_METEO_URL)
        self.assertEqual(seen["params"]["latitude"], engine.JAMMU_LATITUDE)
        self.assertEqual(seen["params"]["longitude"], engine.JAMMU_LONGITUDE)
        self.assertEqual(seen["params"]["forecast_days"], 14)
        self.assertTrue(payload["available"])
        self.assertEqual(payload["source_name"], "open-meteo")
        self.assertFalse(payload["changes_flood_category"])
        self.assertEqual(len(payload["forecasts"]), 14)
        self.assertEqual(payload["forecasts"][0]["date"], "2026-10-01")
        self.assertEqual(payload["forecasts"][-1]["date"], "2026-10-14")

    def test_expired_cache_is_rejected(self):
        now = datetime(2026, 10, 22, tzinfo=timezone.utc)
        old = {
            "available": True,
            "retrieved_at": "2026-10-01T00:00:00+00:00",
            "forecasts": [{"date": "2026-10-02"}],
        }
        self.assertFalse(engine.cache_is_fresh(
            old, now, 6 * 60 * 60, datetime(2026, 10, 22).date(),
        ))
        past_dates = {
            "available": True,
            "retrieved_at": now.isoformat(),
            "forecasts": [{"date": "2026-09-04"}],
        }
        self.assertFalse(engine.cache_is_fresh(
            past_dates, now, 6 * 60 * 60, datetime(2026, 10, 22).date(),
        ))
        short_open_meteo = {
            "available": True,
            "source_name": "open-meteo",
            "retrieved_at": now.isoformat(),
            "forecasts": [{"date": "2026-10-22"}],
        }
        self.assertFalse(engine.cache_is_fresh(
            short_open_meteo, now, 6 * 60 * 60, datetime(2026, 10, 22).date(),
        ))

    def test_qwen_fallback_is_not_reported_as_qwen(self):
        engine._qwen_runtime["blocked_reason"] = None
        result = {
            "final_risk": "Low",
            "current_inflow": 51.9,
            "current_outflow": 26.1,
            "ffd_forecast_text": "100 - 120",
            "ml_prediction": "Normal",
            "date": "2026-10-22",
            "forecast_status": "current",
            "current_risk": "Normal",
            "forecast_risk": "Low",
        }
        alert = engine.generate_qwen_alert(result)
        self.assertEqual(result["final_risk"], "Low")
        self.assertEqual(alert["generated_by"], "FloodShield templates")
        self.assertEqual(alert["qwen_status"], "unavailable")
        self.assertNotEqual(alert["alert_source"], "qwen")

    def test_qwen_success_cannot_change_the_category(self):
        engine._qwen_runtime["blocked_reason"] = None
        os.environ["FLOODSHIELD_DISABLE_QWEN"] = "0"
        os.environ["DASHSCOPE_API_KEY"] = "test-key"
        os.environ["DASHSCOPE_BASE_URL"] = "https://example.test/v1"

        class Message:
            content = '{"english": "Final alert level: Low.", "urdu": "کم"}'

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        class FakeClient:
            def __init__(self):
                self.chat = self
                self.completions = self

            def create(self, **_kwargs):
                return Response()

        original = engine._qwen_client
        engine._qwen_client = lambda: FakeClient()
        try:
            result = {
                "final_risk": "Low",
                "current_inflow": 51.9,
                "current_outflow": 26.1,
                "ffd_forecast_text": "100 - 120",
                "ml_prediction": "Normal",
                "date": "2026-10-22",
                "forecast_status": "current",
                "current_risk": "Normal",
                "forecast_risk": "Low",
            }
            alert = engine.generate_qwen_alert(result)
            self.assertEqual(result["final_risk"], "Low")
            self.assertEqual(alert["qwen_status"], "success")
            self.assertEqual(alert["generated_by"], "Qwen")
            self.assertIn("Low", alert["english"])
        finally:
            engine._qwen_client = original
            os.environ["FLOODSHIELD_DISABLE_QWEN"] = "1"
            engine._qwen_runtime["blocked_reason"] = None


if __name__ == "__main__":
    unittest.main()
