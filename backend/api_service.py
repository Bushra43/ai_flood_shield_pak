"""
FloodShield API service layer.

Serves dashboard payloads for the Next.js frontend.

Modes (FLOODSHIELD_MODE):
  - local  (default): run ML on the latest rows of the local CSV
  - live:              scrape FFD + run the full FloodShield engine
                       (falls back to local if FFD is unreachable)
"""

from __future__ import annotations

import math
import os
import re
import time
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

import floodshield_engine as engine

# Cache live/local status briefly so the dashboard can refresh without
# re-running the full ML pipeline on every request.
_STATUS_CACHE: dict[str, Any] = {"payload": None, "expires_at": 0.0}
_STATUS_TTL_SECONDS = int(os.getenv("FLOODSHIELD_STATUS_TTL", "120"))


def _clean_nan(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (float, np.floating)) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    return value


def _as_float(value: Any, default: float = 0.0) -> float:
    cleaned = _clean_nan(value)
    if cleaned is None:
        return default
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return default


def _as_percent_confidence(value: Any) -> float:
    """Engine stores confidence in 0–1; UI expects 0–100."""
    conf = _as_float(value, 0.0)
    if conf <= 1.0:
        return round(conf * 100.0, 1)
    return round(conf, 1)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [
        re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_")
        for c in out.columns
    ]
    return out


def _read_chenab_marala_csv() -> pd.DataFrame:
    if not os.path.exists(engine.HISTORY_FILE):
        raise FileNotFoundError(f"{engine.HISTORY_FILE} was not found.")

    df = _normalize_columns(pd.read_csv(engine.HISTORY_FILE))

    required = ["date", "inflow_thousands_cusecs", "outflow_thousands_cusecs"]
    for column in required:
        if column not in df.columns:
            raise ValueError(f"Missing required CSV column: {column}")

    if "river" in df.columns:
        df = df[df["river"].astype(str).str.strip().str.lower() == "chenab"]

    if "station" in df.columns:
        df = df[df["station"].astype(str).str.strip().str.lower() == "marala"]

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["date"]).sort_values("date")

    df["inflow"] = pd.to_numeric(df["inflow_thousands_cusecs"], errors="coerce")
    df["outflow"] = pd.to_numeric(df["outflow_thousands_cusecs"], errors="coerce")

    forecast_raw = (
        df["forecast_24h_inflow"]
        if "forecast_24h_inflow" in df.columns
        else pd.Series([None] * len(df), index=df.index)
    )
    forecast_text = forecast_raw.astype(str).where(forecast_raw.notna(), None)

    lows: list[float | None] = []
    highs: list[float | None] = []
    mids: list[float] = []
    texts: list[str] = []

    for text in forecast_text.tolist():
        low, high = engine.extract_forecast_range(text)
        low_f = None if pd.isna(low) else float(low)
        high_f = None if pd.isna(high) else float(high)
        lows.append(low_f)
        highs.append(high_f)

        if low_f is None and high_f is None:
            mids.append(np.nan)
            texts.append("N/A")
        elif low_f is not None and high_f is not None and low_f != high_f:
            mids.append((low_f + high_f) / 2.0)
            texts.append(f"{low_f:g} - {high_f:g}")
        else:
            value = low_f if low_f is not None else high_f
            mids.append(float(value))
            texts.append(f"{value:g}")

    df["forecast_low"] = lows
    df["forecast_high"] = highs
    df["forecast_24h"] = mids
    df["ffd_forecast_text"] = texts
    df["ffd_forecast_level"] = ""
    df["source_url"] = "local CSV"

    if "flood_level" in df.columns:
        df["csv_status"] = df["flood_level"].astype(str)
    else:
        df["csv_status"] = None

    return df.dropna(subset=["inflow"]).reset_index(drop=True)


def load_engine_history(minimum_records: int = 14) -> pd.DataFrame:
    """Return a history frame shaped for floodshield_engine.create_features()."""
    df = _read_chenab_marala_csv()
    history = (
        df[
            [
                "date",
                "inflow",
                "outflow",
                "forecast_24h",
                "forecast_low",
                "forecast_high",
                "ffd_forecast_text",
                "ffd_forecast_level",
                "source_url",
            ]
        ]
        .dropna(subset=["date", "inflow"])
        .sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .tail(max(minimum_records, 10))
        .copy()
        .reset_index(drop=True)
    )

    if len(history) < 7:
        raise RuntimeError(
            f"Need at least 7 Marala observations; found {len(history)}."
        )

    return history


def _status_from_csv(raw: Any, inflow: float) -> str:
    """Map noisy CSV flood_level values onto FloodShield risk labels."""
    text = str(raw or "").strip()
    lowered = text.lower()

    if lowered in {"", "nan", "none", "below low", "no flood"}:
        return engine.get_threshold_risk(inflow)

    for cls in engine.RISK_CLASSES:
        if lowered == cls.lower():
            return cls

    # Some processed rows misplace numeric peaks into flood_level.
    try:
        float(text.replace(",", ""))
        return engine.get_threshold_risk(inflow)
    except ValueError:
        return engine.get_threshold_risk(inflow)


def get_history(limit: int = 30) -> list[dict[str, Any]]:
    """Recent observation rows for /api/history."""
    df = _read_chenab_marala_csv()
    tail = df.tail(max(limit, 1)).copy()

    points: list[dict[str, Any]] = []
    for _, row in tail.iterrows():
        inflow = _as_float(row["inflow"])
        forecast_text = row.get("ffd_forecast_text")
        if forecast_text in {None, "N/A"} or str(forecast_text).lower() in {
            "below low",
            "nan",
            "none",
        }:
            forecast_text = None
            forecast_min = None
            forecast_max = None
        else:
            forecast_min = _clean_nan(row.get("forecast_low"))
            forecast_max = _clean_nan(row.get("forecast_high"))

        points.append(
            {
                "date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
                "inflow": round(inflow, 2),
                "outflow": round(_as_float(row["outflow"]), 2),
                "forecast_min": forecast_min,
                "forecast_max": forecast_max,
                "forecast_text": forecast_text,
                "status": _status_from_csv(row.get("csv_status"), inflow),
            }
        )

    return points


def _shape_status_from_engine_result(result: dict[str, Any]) -> dict[str, Any]:
    forecast_text = str(result.get("ffd_forecast_text") or "N/A")
    low, high = engine.extract_forecast_range(forecast_text)
    forecast_min = None if pd.isna(low) else float(low)
    forecast_max = None if pd.isna(high) else float(high)

    if forecast_min is None and result.get("ffd_forecast_value") is not None:
        forecast_min = _as_float(result["ffd_forecast_value"])
        forecast_max = forecast_min

    # Prefer day+1 quantitative flow from the seven-day outlook when present.
    outlook = result.get("seven_day_outlook") or {}
    days = outlook.get("days") or []
    day_one = days[0] if days else {}
    flow = day_one.get("river_flow_forecast") or {}
    if forecast_min is None:
        forecast_min = _clean_nan(flow.get("low"))
    if forecast_max is None:
        forecast_max = _clean_nan(flow.get("high"))
        if forecast_max is None:
            forecast_max = forecast_min

    alert = result.get("alert") or {}
    english = alert.get("english") or result.get("english_alert") or ""
    urdu = alert.get("urdu") or result.get("urdu_alert") or ""
    generated_by = (
        alert.get("generated_by")
        or result.get("alert_generated_by")
        or "Template"
    )

    payload: dict[str, Any] = {
        "date": result["date"],
        "river": result.get("river", engine.RIVER),
        "station": result.get("station", engine.STATION),
        "current_inflow": round(_as_float(result.get("current_inflow")), 2),
        "current_outflow": round(_as_float(result.get("current_outflow")), 2),
        "ffd_forecast_min": forecast_min if forecast_min is not None else 0.0,
        "ffd_forecast_max": forecast_max if forecast_max is not None else 0.0,
        "ffd_forecast_text": forecast_text,
        "current_danger": result.get("current_risk")
        or result.get("current_danger")
        or "Normal",
        "ffd_forecast_risk": result.get("forecast_risk")
        or result.get("ffd_forecast_risk")
        or "Normal",
        "ml_next_day_risk": result.get("ml_prediction")
        or result.get("ml_next_day_risk")
        or "Normal",
        "ml_confidence": _as_percent_confidence(result.get("ml_confidence")),
        "final_alert": result.get("final_risk")
        or result.get("final_alert")
        or "Normal",
        "english_alert": english,
        "urdu_alert": urdu,
        "alert_generated_by": generated_by,
        "mode": result.get("mode", "local"),
        "ffd_source": result.get("ffd_source"),
        "qwen_status": alert.get("qwen_status"),
        "alert_source": alert.get("alert_source"),
        "forecast_status": result.get("forecast_status"),
        "data_freshness": result.get("data_freshness"),
        "seven_day_outlook": outlook or None,
    }
    if result.get("fallback_reason"):
        payload["fallback_reason"] = result["fallback_reason"]
    return payload


def run_local_status() -> dict[str, Any]:
    """Compute FloodShield status from the local processed CSV + model."""
    history = load_engine_history(minimum_records=14)
    feature_df = engine.create_features(history)
    latest = feature_df.iloc[-1]

    current_risk = engine.get_threshold_risk(latest["inflow_current"])
    forecast_risk = engine.determine_forecast_risk(latest)

    model_package = engine.load_floodshield_model()
    ml_prediction, ml_confidence, class_probabilities = engine.make_ml_prediction(
        feature_df,
        model_package,
    )

    final_risk = engine.determine_final_risk(
        current_risk,
        forecast_risk,
        ml_prediction,
    )

    issue_day = pd.Timestamp(latest["date"]).date()
    day_one = issue_day + pd.Timedelta(days=1)
    day_state = engine.forecast_day_status(
        issue_day,
        day_one,
        engine.karachi_today(),
    )
    if day_state["expired"]:
        final_risk = "Insufficient data"

    try:
        ml_horizons = engine.predict_flood_risk_horizons(
            feature_df,
            engine.MODEL_DIR,
            latest["date"],
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Horizon models could not be scored (local): {exc}")
        ml_horizons = []

    result: dict[str, Any] = {
        "date": latest["date"].strftime("%Y-%m-%d"),
        "river": engine.RIVER,
        "station": engine.STATION,
        "current_inflow": float(latest["inflow_current"]),
        "current_outflow": float(latest["outflow_current"]),
        "ffd_forecast_value": (
            None
            if pd.isna(latest["forecast_24h"])
            else float(latest["forecast_24h"])
        ),
        "ffd_forecast_text": latest["ffd_forecast_text"],
        "current_risk": current_risk,
        "forecast_risk": forecast_risk,
        "ml_prediction": ml_prediction,
        "ml_confidence": ml_confidence,
        "ml_probabilities": class_probabilities,
        "final_risk": final_risk,
        "forecast_status": day_state["status"],
        "ffd_source": latest.get("source_url", "local CSV"),
        "mode": "local",
    }

    result["alert"] = engine.generate_qwen_alert(result)
    result["seven_day_outlook"] = engine.build_seven_day_outlook(
        issue_date=latest["date"],
        current_risk=current_risk,
        forecast_risk=forecast_risk,
        forecast_text=latest["ffd_forecast_text"],
        forecast_level=latest.get("ffd_forecast_level", ""),
        forecast_low=latest.get("forecast_low"),
        forecast_high=latest.get("forecast_high"),
        ml_prediction=ml_prediction,
        ml_probabilities=class_probabilities,
        ml_horizons=ml_horizons,
        jammu=None,
        ffd_outlook=None,
        final_risk=final_risk,
        current_inflow=latest["inflow_current"],
        current_outflow=latest["outflow_current"],
        source_url=latest.get("source_url", "local CSV"),
    )
    result["data_freshness"] = result["seven_day_outlook"].get("data_freshness")
    return _shape_status_from_engine_result(result)


def run_live_status() -> dict[str, Any]:
    """Run the full live engine; fall back to local CSV mode on failure."""
    try:
        result = engine.run_floodshield()
        result["mode"] = "live"
        return _shape_status_from_engine_result(result)
    except Exception as exc:  # noqa: BLE001 — intentional graceful fallback
        local = run_local_status()
        local["mode"] = "local"
        local["fallback_reason"] = str(exc)
        return local


def get_status(force_refresh: bool = False) -> dict[str, Any]:
    now = time.time()
    cached = _STATUS_CACHE.get("payload")
    if (
        not force_refresh
        and cached is not None
        and now < float(_STATUS_CACHE.get("expires_at") or 0)
    ):
        return cached

    mode = os.getenv("FLOODSHIELD_MODE", "local").strip().lower()
    payload = run_live_status() if mode == "live" else run_local_status()

    _STATUS_CACHE["payload"] = payload
    _STATUS_CACHE["expires_at"] = now + _STATUS_TTL_SECONDS
    return payload


@lru_cache(maxsize=1)
def get_model_info() -> dict[str, Any]:
    """Model / project metadata for /api/model-info."""
    info: dict[str, Any] = {
        "training_data": "2024–2025",
        "testing_evaluation": "2026",
        "river": "Chenab",
        "station": "Marala",
        "data_source": "FFD / PMD",
        "ml_engine": (
            "7 calendar-horizon classifiers (day +1…+7); "
            "Extra Trees / Random Forest flood-risk classification"
        ),
        "generative_ai": "Qwen (phrasing only)",
        "live_data": "FFD Bulletin + local Marala CSV",
        "output": "Bilingual Early Warning + seven-day outlook",
        "accuracy": None,
        "precision": None,
        "recall": None,
        "f1_score": None,
    }

    try:
        package = engine.load_floodshield_model()
    except Exception:  # noqa: BLE001
        return info

    metrics = package.get("metrics_2026") or package.get("metrics") or {}
    if isinstance(metrics, dict):
        accuracy = metrics.get("accuracy")
        macro_f1 = metrics.get("macro_f1") or metrics.get("f1")
        # Precision / recall are not always stored; leave null when absent.
        precision = metrics.get("precision") or metrics.get("precision_macro")
        recall = metrics.get("recall") or metrics.get("recall_macro")

        def to_pct(value: Any) -> float | None:
            if value is None or (isinstance(value, float) and math.isnan(value)):
                return None
            number = float(value)
            if number <= 1.0:
                number *= 100.0
            return round(number, 1)

        info["accuracy"] = to_pct(accuracy)
        info["precision"] = to_pct(precision)
        info["recall"] = to_pct(recall)
        info["f1_score"] = to_pct(macro_f1)

    training_years = package.get("training_years")
    if training_years:
        info["training_data"] = "–".join(str(y) for y in training_years)

    test_year = package.get("test_year")
    if test_year is not None:
        info["testing_evaluation"] = str(test_year)

    return info


def get_health() -> dict[str, Any]:
    csv_ok = os.path.exists(engine.HISTORY_FILE)
    model_ok = os.path.exists(engine.MODEL_FILE)
    horizon_dir = engine.MODEL_DIR / "horizons"
    horizons_present = {
        str(h): (horizon_dir / f"floodshield_horizon_{h}.pkl").exists()
        for h in engine.HORIZONS
    }
    all_horizons = all(horizons_present.values())
    return {
        "ok": csv_ok and model_ok and all_horizons,
        "mode": os.getenv("FLOODSHIELD_MODE", "local"),
        "csv_present": csv_ok,
        "model_present": model_ok,
        "horizons_present": horizons_present,
        "history_file": engine.HISTORY_FILE,
        "model_file": engine.MODEL_FILE,
        "model_dir": str(engine.MODEL_DIR),
    }
