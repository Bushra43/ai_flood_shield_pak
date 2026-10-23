#!/usr/bin/env python3
"""
Extract gauging-station data from PMD Flood Forecasting Division bulletins (PDF).

Reads all PDFs under bulletins/bulletins_2024, bulletins_2025, and bulletins_2026
and writes extracted_data.csv.
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pdfplumber

LOGGER = logging.getLogger(__name__)

ML_DIR = Path(__file__).resolve().parents[1]
BULLETINS_DIR = ML_DIR / "data" / "raw" / "bulletins"
OUTPUT_CSV = ML_DIR / "data" / "processed" / "extracted_data.csv"

MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

FLOOD_LEVEL_ALIASES = {
    "-do-": None,
    "do-": None,
    "below low": "Below Low",
    "low": "Low",
    "low to medium": "Low to Medium",
    "medium": "Medium",
    "high": "High",
    "very high": "Very High",
    "exceptionally high": "Exceptionally High",
}


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--", "Nil", "nil"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def _date_from_parts(day: str, month_name: str, year: str) -> date | None:
    month = MONTHS.get(month_name.lower())
    if not month:
        return None
    return date(int(year), month, int(day))


def parse_date_from_text(text: str) -> date | None:
    patterns = [
        r"Dated:\s*-?\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)[,\-]\s*(\d{4})",
        r"DAILY\s+FLOOD\s+BULLETIN\s+(\d{1,2})[-\s]([A-Za-z]+)[-\s](\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            parsed = _date_from_parts(*match.groups())
            if parsed:
                return parsed
    return None


def parse_date_from_filename(path: Path) -> date | None:
    name = path.stem
    patterns = [
        (r"^(\d{2})(\d{2})(\d{4})$", lambda m: (m[0], m[1], m[2])),
        (r"^(\d{2})-(\d{2})-(\d{4})", lambda m: (m[0], m[1], m[2])),
        (r"Flood-Bulletin-(\d{4})-(\d{2})-(\d{2})", lambda m: (m[2], m[1], m[0])),
        (r"(\d{4})-(\d{2})-(\d{2})", lambda m: (m[2], m[1], m[0])),
    ]
    for pattern, parts_fn in patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if match:
            day, month, year = parts_fn(match.groups())
            return date(int(year), int(month), int(day))
    return None


def normalize_flood_level(raw: str | None, previous: str | None) -> str | None:
    if raw is None:
        return previous
    text = re.sub(r"\s+", " ", str(raw).strip())
    lower = text.lower()
    if lower in FLOOD_LEVEL_ALIASES:
        resolved = FLOOD_LEVEL_ALIASES[lower]
        return previous if resolved is None else resolved
    return text.title() if text else previous


def parse_historical_peak(raw: str | None) -> tuple[float | None, int | None]:
    if raw is None:
        return None, None
    text = re.sub(r"\s+", " ", str(raw).replace("\n", " ")).strip()
    peak_match = re.search(r"([\d.]+)", text)
    peak = float(peak_match.group(1)) if peak_match else None

    year_match = re.search(r"E\s*\(\s*(\d{4})\s*\)", text, flags=re.IGNORECASE)
    if not year_match:
        year_match = re.search(r"\(\s*(\d{4})\s*\)", text)
    if year_match:
        year = int(year_match.group(1))
    else:
        year_candidates = [
            int(y)
            for y in re.findall(r"(?<![\d.])(\d{4})(?![\d.])", text)
            if 1900 <= int(y) <= 2100
        ]
        year = year_candidates[-1] if year_candidates else None

    return peak, year


def parse_forecast_numeric(raw: str | None, current_inflow: float | None) -> float | None:
    if raw is None:
        return None
    text = re.sub(r"\s+", " ", str(raw).strip())
    lower = text.lower()
    if lower in {"-do-", "do-", "no sig. change", "no sig change"}:
        return current_inflow

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return (low + high) / 2.0

    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]
    if numbers:
        return numbers[0]
    return None


def find_quantitative_table(pdf: pdfplumber.PDF) -> list[list[str | None]] | None:
    for page in pdf.pages:
        for table in page.extract_tables() or []:
            if not table or len(table) < 3:
                continue
            header = " ".join(str(cell or "") for cell in table[0]).lower()
            if "quantitative" in header and "stations" in header:
                return table
    return None


def extract_flood_season_year(table: list[list[str | None]]) -> int | None:
    if len(table) < 2:
        return None
    header_row = " ".join(str(cell or "") for cell in table[1])
    match = re.search(r"flood\s*season\s*(\d{4})", header_row, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_rows_from_table(
    table: list[list[str | None]],
    report_date: date,
    source_file: str,
) -> list[dict]:
    flood_season_year = extract_flood_season_year(table)
    rows: list[dict] = []
    current_river: str | None = None
    last_flood_level: str | None = None

    for row in table[2:]:
        if not row or len(row) < 9:
            continue

        station = str(row[1] or "").strip()
        if not station:
            continue

        river_cell = str(row[0] or "").strip()
        if river_cell:
            current_river = river_cell

        design_capacity = parse_number(row[2])
        inflow = parse_number(row[3])
        outflow = parse_number(row[4])
        forecast_raw = str(row[5] or "").strip() or None
        flood_level = normalize_flood_level(row[6], last_flood_level)
        if flood_level:
            last_flood_level = flood_level

        historical_raw = str(row[7] or "").strip() or None
        flood_season_value = parse_number(row[8])
        max_peak, peak_year = parse_historical_peak(historical_raw)

        rows.append(
            {
                "date": report_date.isoformat(),
                "river": current_river,
                "station": station,
                "design_capacity": design_capacity,
                "inflow_thousands_cusecs": inflow,
                "outflow_thousands_cusecs": outflow,
                "forecast_24h_inflow": forecast_raw,
                "forecast_24h_inflow_numeric": parse_forecast_numeric(
                    forecast_raw, inflow
                ),
                "flood_level": flood_level,
                "max_historical_peak_thousands_cusecs": max_peak,
                "max_historical_peak_year": peak_year,
                "flood_season": flood_season_value,
                "flood_season_year": flood_season_year,
                "source_file": source_file,
            }
        )

    return rows


def parse_bulletin_pdf(path: Path) -> list[dict]:
    try:
        with pdfplumber.open(path) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            table = find_quantitative_table(pdf)
    except Exception as exc:
        LOGGER.warning("Failed to read %s: %s", path.name, exc)
        return []

    if not table:
        LOGGER.warning("No quantitative forecast table found in %s", path.name)
        return []

    report_date = parse_date_from_text(full_text) or parse_date_from_filename(path)
    if not report_date:
        LOGGER.warning("Could not determine date for %s", path.name)
        return []

    return extract_rows_from_table(table, report_date, path.name)


def iter_bulletin_pdfs(bulletins_dir: Path) -> list[Path]:
    subfolders = ["bulletins_2024", "bulletins_2025", "bulletins_2026"]
    pdfs: list[Path] = []
    for folder_name in subfolders:
        folder = bulletins_dir / folder_name
        if folder.exists():
            pdfs.extend(sorted(folder.glob("*.pdf")))
        else:
            LOGGER.warning("Missing folder: %s", folder)
    return pdfs


def extract_all(bulletins_dir: Path, station: str | None = None) -> pd.DataFrame:
    all_rows: list[dict] = []
    pdfs = iter_bulletin_pdfs(bulletins_dir)

    if not pdfs:
        raise FileNotFoundError(
            f"No PDF files found under {bulletins_dir}. "
            "Expected bulletins_2024, bulletins_2025, bulletins_2026 subfolders."
        )

    for pdf_path in pdfs:
        rows = parse_bulletin_pdf(pdf_path)
        if station:
            rows = [row for row in rows if row["station"].lower() == station.lower()]
        all_rows.extend(rows)

    if not all_rows:
        raise RuntimeError("No data extracted from bulletin PDFs.")

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "river", "station"]).drop_duplicates(
        ["date", "station"], keep="last"
    )
    return df.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract flood bulletin data from PDFs into extracted_data.csv"
    )
    parser.add_argument(
        "--bulletins-dir",
        type=Path,
        default=BULLETINS_DIR,
        help="Path to bulletins folder containing year subfolders",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_CSV,
        help="Output CSV path",
    )
    parser.add_argument(
        "--station",
        type=str,
        default=None,
        help="Optional station filter (e.g. Marala). Default: extract all stations.",
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

    LOGGER.info("Reading PDFs from %s", args.bulletins_dir)
    df = extract_all(args.bulletins_dir, station=args.station)

    output_columns = [
        "date",
        "river",
        "station",
        "design_capacity",
        "inflow_thousands_cusecs",
        "outflow_thousands_cusecs",
        "forecast_24h_inflow",
        "flood_level",
        "max_historical_peak_thousands_cusecs",
        "max_historical_peak_year",
        "flood_season",
        "flood_season_year",
        "source_file",
    ]
    df[output_columns].to_csv(args.output, index=False)
    LOGGER.info("Wrote %s rows to %s", len(df), args.output)
    LOGGER.info("Date range: %s -> %s", df["date"].min(), df["date"].max())


if __name__ == "__main__":
    main()
