#!/usr/bin/env python3
"""
Compute derived features from extracted_data.csv and merge them back into the same file.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = ML_DIR / "data" / "processed" / "extracted_data.csv"


def parse_forecast_numeric(series: pd.Series, inflow: pd.Series) -> pd.Series:
    def _parse(value, current):
        if pd.isna(value):
            return current
        text = str(value).strip().lower()
        if text in {"-do-", "do-", "no sig. change", "no sig change"}:
            return current
        import re

        range_match = re.search(
            r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", str(value)
        )
        if range_match:
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            return (low + high) / 2.0
        numbers = re.findall(r"\d+(?:\.\d+)?", str(value))
        if numbers:
            return float(numbers[0])
        return current

    return pd.Series(
        [_parse(v, i) for v, i in zip(series, inflow, strict=True)],
        index=series.index,
    )


def add_calculated_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["station", "date"]).reset_index(drop=True)

    df["month"] = df["date"].dt.month
    df["day_of_year"] = df["date"].dt.dayofyear

    if "forecast_24h_inflow_numeric" not in df.columns:
        df["forecast_24h_inflow_numeric"] = parse_forecast_numeric(
            df.get("forecast_24h_inflow", pd.Series(dtype=object)),
            df["inflow_thousands_cusecs"],
        )

    group = df.groupby("station", sort=False)
    df["inflow_change_1"] = group["inflow_thousands_cusecs"].diff()
    df["inflow_change_3"] = (
        df["inflow_thousands_cusecs"] - group["inflow_thousands_cusecs"].shift(3)
    )
    df["outflow_change_1"] = group["outflow_thousands_cusecs"].diff()

    df["inflow_outflow_difference"] = (
        df["inflow_thousands_cusecs"] - df["outflow_thousands_cusecs"]
    )

    df["capacity_utilization"] = df["inflow_thousands_cusecs"] / df["design_capacity"]

    df["forecast_change"] = (
        df["forecast_24h_inflow_numeric"] - df["inflow_thousands_cusecs"]
    )

    df["historical_peak_ratio"] = (
        df["inflow_thousands_cusecs"]
        / df["max_historical_peak_thousands_cusecs"]
    )

    df["is_flood_season"] = df["month"].isin([6, 7, 8, 9]).astype(int)

    df = df.drop(columns=["forecast_24h_inflow_numeric"], errors="ignore")
    return df.sort_values(["date", "station"]).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add calculated columns to extracted_data.csv"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_CSV,
        help="CSV file to read and update",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (defaults to --input)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s: %(message)s",
    )

    output_path = args.output or args.input
    if not args.input.exists():
        raise FileNotFoundError(
            f"{args.input} not found. Run extract_data.py first."
        )

    LOGGER.info("Reading %s", args.input)
    df = pd.read_csv(args.input, parse_dates=["date"])
    enriched = add_calculated_columns(df)

    enriched.to_csv(output_path, index=False)
    LOGGER.info("Wrote %s rows with calculated columns to %s", len(enriched), output_path)


if __name__ == "__main__":
    main()
