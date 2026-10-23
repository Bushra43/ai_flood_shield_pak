# ============================================================
# AI FLOODSHIELD PAK
# FloodShield Live Decision Engine
#
# River   : Chenab
# Station : Marala
#
# Next-day result (unchanged keys):
#   current threshold risk
#   FFD 24-hour upper-end risk
#   ML next-day class
#   final_risk = highest of those three
#
# Seven-day outlook:
#   one row for bulletin date + 1 ... + 7
#   later days use an official warning that covers that date
#   and that horizon's own model
#   Jammu weather is context only and never changes the category
#
# Qwen never decides the flood level.
# ============================================================

import json
import os
import re
import time
import warnings
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

warnings.filterwarnings("ignore")


# ============================================================
# 1. CONFIGURATION
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
ML_DIR = REPO_ROOT / "ml"

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")

HISTORY_FILE = os.environ.get(
    "FLOODSHIELD_DATA_FILE",
    str(ML_DIR / "data" / "processed" / "chenab_marala_dataset.csv"),
)
MODEL_DIR = Path(
    os.environ.get("FLOODSHIELD_MODEL_DIR", str(ML_DIR / "models"))
)
MODEL_FILE = str(MODEL_DIR / "floodshield_marala_model.pkl")

# Keep BASE_DIR alias for any remaining relative helpers.
BASE_DIR = ML_DIR

FFD_BASE_URL = "https://ffd.pmd.gov.pk"
FFD_BULLETIN_URL = "https://ffd.pmd.gov.pk/bulletin"
JAMMU_URL = "https://www.timeanddate.com/weather/india/jammu/ext"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
# Jammu city. This is a weather-proxy location, not a river gauge.
JAMMU_LATITUDE = 32.7266
JAMMU_LONGITUDE = 74.8570
# Two-week daily forecast. Open-Meteo accepts 1 through 16.
JAMMU_FORECAST_DAYS = 14
JAMMU_CACHE = ML_DIR / "data" / "cache" / "jammu_ext_forecast.json"
JAMMU_CACHE_SECONDS = 6 * 60 * 60
HORIZONS = (1, 2, 3, 4, 5, 6, 7)

RIVER = "CHENAB"
STATION = "MARALA"
KARACHI = ZoneInfo("Asia/Karachi")

LOW_FLOOD = 100.0
MEDIUM_FLOOD = 150.0
HIGH_FLOOD = 200.0
VERY_HIGH_FLOOD = 400.0
EXCEPTIONAL_FLOOD = 600.0
DESIGN_CAPACITY = 1100.0

RISK_CLASSES = [
    "Normal",
    "Low",
    "Medium",
    "High",
    "Very High",
    "Exceptional",
]

SEVERITY = {
    "Normal": 0,
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Very High": 4,
    "Exceptional": 5,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    )
}

JAMMU_HEADERS = {
    **HEADERS,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 30
JAMMU_TIMEOUT = 20

JAMMU_NOTE = (
    "Open-Meteo 14-day daily forecast for Jammu city "
    f"({JAMMU_LATITUDE}N, {JAMMU_LONGITUDE}E), a single city in part of "
    "the Chenab catchment upstream of Marala. Weather proxy only. "
    "Not catchment rainfall and not Marala discharge. "
    "It does not raise or lower the flood category. "
    "A precipitation value of 0 is the amount Open-Meteo reported. "
    "A missing field stays null and is not stored as zero."
)

OUTLOOK_LIMITATIONS = [
    "Jammu weather is the Open-Meteo 14-day forecast for one city "
    "in part of the Chenab catchment. It is not catchment rainfall, "
    "not Marala discharge, and it does not change the flood category.",
    "FFD publishes a 24-hour quantitative inflow and a short weekly "
    "qualitative outlook, not seven daily Marala discharge forecasts.",
    "Historical labels are mostly Normal. Very High has no examples. "
    "Longer horizons are not accurate severe-flood forecasts.",
    "The historical record is monsoon-only. Winter and spring are absent.",
    "Outside the flood season the latest bulletin may be days old.",
    "Training uses the first number of a forecast range. This alert "
    "uses the upper number. Both behaviors are intentional.",
]

MONTH_NUMBERS = {}
for _index, _name in enumerate(
    [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ],
    start=1,
):
    MONTH_NUMBERS[_name] = _index
    MONTH_NUMBERS[_name[:3]] = _index

URDU_ACTIONS = {
    "Normal":
        "فی الحال سیلابی صورتحال ظاہر نہیں ہو رہی۔ "
        "سرکاری اطلاعات پر نظر رکھیں۔",
    "Low":
        "دریا کے بہاؤ میں اضافہ ہے۔ دریائے چناب کے "
        "قریب رہنے والے افراد محتاط رہیں اور سرکاری "
        "اطلاعات پر نظر رکھیں۔",
    "Medium":
        "سیلاب کا خطرہ قابلِ توجہ ہے۔ نشیبی اور دریا "
        "کے قریب علاقوں کے رہائشی ممکنہ حفاظتی اقدامات "
        "کے لیے تیار رہیں اور سرکاری ہدایات پر عمل کریں۔",
    "High":
        "اونچے درجے کے سیلاب کا خطرہ ہے۔ دریا کے کناروں "
        "اور سیلاب سے متاثر ہونے والے علاقوں سے دور رہیں "
        "اور حکام کی ہدایات پر عمل کریں۔",
    "Very High":
        "بہت اونچے درجے کے سیلاب کا خطرہ ہے۔ حساس علاقوں "
        "کے رہائشی فوری طور پر سرکاری حفاظتی اور انخلا کی "
        "ہدایات پر عمل کریں۔",
    "Exceptional":
        "انتہائی شدید سیلابی خطرہ ہے۔ صورتحال کو ہنگامی "
        "حالت سمجھیں اور فوری طور پر سرکاری انخلا اور "
        "حفاظتی ہدایات پر عمل کریں۔",
    "Insufficient data":
        "اس دن کے لیے سرکاری سیلابی درجہ اور ماڈل دونوں "
        "دستیاب نہیں۔ اسے نارمل یا صفر خطرہ نہ سمجھا جائے۔ "
        "سرکاری اطلاعات پر نظر رکھیں۔",
}


# ============================================================
# 2. BASIC UTILITY FUNCTIONS
# ============================================================

def extract_first_number(value):
    """First number in text, matching the training cleaner."""

    if value is None:
        return np.nan

    text = str(value).replace(",", "").strip()
    match = re.search(r"[-+]?\d*\.?\d+", text)
    if not match:
        return np.nan

    try:
        return float(match.group())
    except ValueError:
        return np.nan


def normalize_text(value):
    """Collapse whitespace for matching."""

    return re.sub(r"\s+", " ", str(value)).strip()


def karachi_today():
    """Local calendar date used only to judge bulletin freshness."""

    return datetime.now(KARACHI).date()


def as_optional_float(value):
    """Float for JSON, or None when the value is missing."""

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def higher_risk(risks):
    """Highest known severity. Unknown values are ignored."""

    valid = [risk for risk in risks if risk in SEVERITY]
    if not valid:
        return None
    return max(valid, key=lambda risk: SEVERITY[risk])


def json_ready(value):
    """Convert numpy and pandas values so json.dumps can print them."""

    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.floating, float)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


# ============================================================
# 3. FLOOD-RISK THRESHOLD FUNCTION
# ============================================================

def get_threshold_risk(inflow):
    """Flood category from inflow in thousands of cusecs."""

    if pd.isna(inflow):
        return "Unknown"

    if inflow < LOW_FLOOD:
        return "Normal"
    elif inflow < MEDIUM_FLOOD:
        return "Low"
    elif inflow < HIGH_FLOOD:
        return "Medium"
    elif inflow < VERY_HIGH_FLOOD:
        return "High"
    elif inflow < EXCEPTIONAL_FLOOD:
        return "Very High"
    else:
        return "Exceptional"


def extract_forecast_range(text):
    """
    Lower and upper ends of an FFD forecast.

    '60 - 90' -> (60, 90). A single number is both ends.
    """

    if text is None:
        return np.nan, np.nan

    cleaned = str(text).replace(",", "")
    # "40-50" is a range. The hyphen is not a minus sign.
    ranged = re.search(
        r"([-+]?\d*\.?\d+)\s*(?:-|–|—|to)\s*([-+]?\d*\.?\d+)",
        cleaned,
        re.IGNORECASE,
    )
    if ranged:
        return float(ranged.group(1)), float(ranged.group(2))

    numbers = re.findall(r"[-+]?\d*\.?\d+", cleaned)
    numbers = [float(item) for item in numbers if item.strip() not in {"", "-", "+", "."}]

    if len(numbers) >= 2:
        return numbers[0], numbers[-1]
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return np.nan, np.nan


def official_category_from_text(text):
    """
    Map a clear official flood phrase to a project label.

    Rain and thunderstorm wording does not become a flood class.
    'Exceptionally High' maps to 'Exceptional'.
    """

    if text is None:
        return None

    cleaned = normalize_text(text).lower()
    if not cleaned:
        return None

    # The severity legend lists every class and is not an outlook.
    if (
        "flood severity scale" in cleaned
        and "below low" in cleaned
        and "exceptionally high" in cleaned
    ):
        return None

    if re.search(r"exceptionally\s+high|\bexceptional\b", cleaned):
        return "Exceptional"
    if re.search(r"very\s+high", cleaned):
        return "Very High"
    if re.search(r"below\s+low", cleaned):
        return "Normal"
    if re.search(
        r"remain(?:s|ing)?\s+normal|normal\s+flows?|"
        r"within the normal|no\s+(?:significant\s+)?flood",
        cleaned,
    ):
        return "Normal"
    if re.search(r"\bmedium\b", cleaned):
        return "Medium"
    if re.search(r"\bhigh\b", cleaned):
        return "High"
    if re.search(r"\blow\b", cleaned):
        return "Low"
    return None


# ============================================================
# 4. DOWNLOAD A WEB PAGE
# ============================================================

def fetch_text(
    url,
    get,
    attempts=3,
    timeout=REQUEST_TIMEOUT,
    headers=None,
    pause_seconds=1,
):
    """
    Bounded HTTP GET.

    A 4xx or 5xx response is a failed attempt. The response body is
    not logged. The raised error is the status or exception name.
    """

    last_error = f"Could not download {url}"
    for attempt in range(1, attempts + 1):
        try:
            response = get(url, headers=headers, timeout=timeout)
            status = int(getattr(response, "status_code", 200))
            if status >= 400:
                last_error = f"HTTP {status} from {url}"
                print(f"Attempt {attempt} failed: {last_error}")
            else:
                text = response.text or ""
                if len(text.strip()) < 50:
                    last_error = f"Empty or truncated response from {url}"
                    print(f"Attempt {attempt} failed: {last_error}")
                else:
                    return text
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__} from {url}"
            print(f"Attempt {attempt} failed: {last_error}")
        if attempt < attempts and pause_seconds:
            time.sleep(pause_seconds)
    raise requests.RequestException(last_error)


def download_page(url):
    """Download an FFD webpage, with timeout and bounded retries."""

    print(f"Downloading {url}")
    return fetch_text(
        url,
        requests.get,
        attempts=3,
        timeout=REQUEST_TIMEOUT,
        headers=HEADERS,
        pause_seconds=1,
    )


def extract_publication_time(html):
    """Publication clock time when the bulletin states one. Otherwise None."""

    text = normalize_text(
        BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    )
    patterns = (
        r"(?:issued|updated)\s*(?:on|at)?\s*[:\-]?\s*"
        r"(\d{1,2}[:.]\d{2}\s*(?:pkt|pst|utc|hrs)?)",
        r"\b(\d{3,4})\s*(?:hrs|hours)\s*(?:pkt|pst)?",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return normalize_text(match.group(1))
    return None


def forecast_day_status(issue_date, forecast_date, today):
    """
    Whether one outlook date is current, stale, or expired.

    A forecast date before today is expired and must not be described
    as the current outlook. A bulletin issued before today is stale
    even when its remaining forecast dates are still ahead.
    """

    issue = pd.Timestamp(issue_date).date()
    forecast = pd.Timestamp(forecast_date).date()
    as_of = pd.Timestamp(today).date()
    expired = forecast < as_of
    stale = issue < as_of
    if expired:
        status = "expired"
    elif issue > as_of:
        status = "future_bulletin"
    elif stale:
        status = "stale"
    else:
        status = "current"
    return {
        "issue_date": issue.isoformat(),
        "forecast_date": forecast.isoformat(),
        "today": as_of.isoformat(),
        "expired": expired,
        "stale": stale,
        "status": status,
        "official_applies": not expired,
    }


def extract_bulletin_date(html):
    """Bulletin date from the page heading or the dated line."""

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    pattern1 = re.search(
        r"DAILY\s+FLOOD\s+BULLETIN\s+"
        r"(\d{1,2})[-\s]"
        r"([A-Za-z]{3,9})[-\s]"
        r"(\d{4})",
        text,
        re.IGNORECASE,
    )
    if pattern1:
        date_text = (
            f"{pattern1.group(1)} "
            f"{pattern1.group(2)} "
            f"{pattern1.group(3)}"
        )
        return pd.to_datetime(date_text, errors="coerce")

    pattern2 = re.search(
        r"Dated:\s*"
        r"(\d{1,2})(?:\s*(?:st|nd|rd|th))?\s*"
        r"([A-Za-z]+)[-\s]"
        r"(\d{4})",
        text,
        re.IGNORECASE,
    )
    if pattern2:
        date_text = (
            f"{pattern2.group(1)} "
            f"{pattern2.group(2)} "
            f"{pattern2.group(3)}"
        )
        return pd.to_datetime(date_text, errors="coerce")

    return pd.NaT


def _calendar_date(day, month_name, year):
    month = MONTH_NUMBERS.get(str(month_name).lower())
    if month is None:
        return None
    try:
        return datetime(int(year), month, int(day)).date()
    except ValueError:
        return None


def parse_outlook_date_range(text):
    """
    Parse ranges such as '16 th October, 2026 to 21 st October, 2026'
    and '16-21 Oct 2026'.
    """

    if not text:
        return None, None

    full = re.search(
        r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
        r"([A-Za-z]+)\s*,?\s*"
        r"(\d{4})\s+"
        r"(?:to|through|–|—|-)\s+"
        r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
        r"([A-Za-z]+)\s*,?\s*"
        r"(\d{4})",
        text,
        re.IGNORECASE,
    )
    if full:
        start = _calendar_date(full.group(1), full.group(2), full.group(3))
        end = _calendar_date(full.group(4), full.group(5), full.group(6))
        if start and end:
            return start, end

    shared = re.search(
        r"(\d{1,2})\s*(?:st|nd|rd|th)?\s*"
        r"(?:to|through|–|—|-)\s*"
        r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
        r"([A-Za-z]+)\s*,?\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if shared:
        start = _calendar_date(
            shared.group(1),
            shared.group(3),
            shared.group(4),
        )
        end = _calendar_date(
            shared.group(2),
            shared.group(3),
            shared.group(4),
        )
        if start and end:
            return start, end

    return None, None


def extract_ffd_outlook(html):
    """
    Weekly qualitative outlook from the same bulletin HTML.

    Only the flood-outlook sentence can set a category. Rainfall
    wording is stored and does not become a flood class.
    """

    soup = BeautifulSoup(html, "html.parser")
    text = normalize_text(soup.get_text(" ", strip=True))

    weekly_match = re.search(
        r"WEEKLY\s+SIGNIFICANT\s+OUTLOOK\b"
        r"(.*?)"
        r"(?:QUANTITATIVE\s+FLOOD\s+FORECAST|"
        r"WEATHER/RAINFALL\s+FORECAST|$)",
        text,
        re.IGNORECASE,
    )
    weekly_text = weekly_match.group(0) if weekly_match else ""

    flood_match = re.search(
        r"FLOOD\s+OUTLOOK\s+"
        r"(.*?)"
        r"(?:Page break|\b\d+\.\s+[A-Z]|QUANTITATIVE\s+FLOOD|"
        r"WEATHER/RAINFALL|$)",
        weekly_text or text,
        re.IGNORECASE,
    )
    flood_text = _clean_outlook_sentence(
        flood_match.group(1) if flood_match else ""
    )

    rain_match = re.search(
        r"RAINFALL\s+OUTLOOK\s+(.*?)(?:FLOOD\s+OUTLOOK|$)",
        weekly_text,
        re.IGNORECASE,
    )
    rain_text = _clean_outlook_sentence(
        rain_match.group(1) if rain_match else ""
    )

    start, end = parse_outlook_date_range(weekly_text or text)
    category = official_category_from_text(flood_text)

    next_match = re.search(
        r"NEXT FORECAST BULLETIN WILL BE ISSUED ON\s+([^.]+)",
        text,
        re.IGNORECASE,
    )
    next_bulletin = (
        normalize_text(next_match.group(1)) if next_match else None
    )

    return {
        "weekly_text": weekly_text,
        "flood_text": flood_text,
        "meteorological_text": rain_text,
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
        "category": category,
        "next_bulletin": next_bulletin,
        "published_at": extract_publication_time(html),
        "source_url": FFD_BULLETIN_URL,
    }


def _clean_outlook_sentence(text):
    """Drop a trailing section number such as 'II.' from a bulletin sentence."""

    cleaned = normalize_text(text)
    cleaned = re.sub(r"\s+[IVXLC]+\.$", "", cleaned)
    return cleaned.strip()


def official_category_for_date(outlook, forecast_date):
    """Official weekly category when the date falls inside its window."""

    if not outlook:
        return None, None

    category = outlook.get("category")
    start = outlook.get("start_date")
    end = outlook.get("end_date")
    if category not in SEVERITY or not start or not end:
        return None, outlook.get("flood_text") or None

    if start <= forecast_date.isoformat() <= end:
        return category, outlook.get("flood_text") or None
    return None, None


# ============================================================
# 5. EXTRACT MARALA ROW FROM BULLETIN
# ============================================================

def extract_marala_from_html(html, source_url):
    """Chenab / Marala row from the quantitative forecast table."""

    soup = BeautifulSoup(html, "html.parser")
    bulletin_date = extract_bulletin_date(html)

    for row in soup.find_all("tr"):
        cells = [
            normalize_text(cell.get_text(" ", strip=True))
            for cell in row.find_all(["td", "th"])
        ]
        if len(cells) < 5:
            continue

        joined = " | ".join(cells).upper()
        if "CHENAB" not in joined or "MARALA" not in joined:
            continue

        station_index = next(
            (
                index
                for index, value in enumerate(cells)
                if "MARALA" in value.upper()
            ),
            None,
        )
        if station_index is None or len(cells) <= station_index + 3:
            continue

        inflow_text = cells[station_index + 1]
        outflow_text = cells[station_index + 2]
        forecast_text = cells[station_index + 3]
        forecast_level = (
            cells[station_index + 4]
            if len(cells) > station_index + 4
            else ""
        )
        forecast_low, forecast_high = extract_forecast_range(forecast_text)

        return {
            "date": bulletin_date,
            "river": RIVER,
            "station": STATION,
            "inflow": extract_first_number(inflow_text),
            "outflow": extract_first_number(outflow_text),
            "forecast_24h": extract_first_number(forecast_text),
            "forecast_low": forecast_low,
            "forecast_high": forecast_high,
            "ffd_forecast_text": forecast_text,
            "ffd_forecast_level": forecast_level,
            "source_url": source_url,
            "published_at": extract_publication_time(html),
        }

    try:
        tables = pd.read_html(StringIO(html))
        for table in tables:
            table_text = table.astype(str)
            contains_marala = (
                table_text.apply(
                    lambda column: column.str.contains(
                        "Marala",
                        case=False,
                        na=False,
                    )
                )
                .any()
                .any()
            )
            if not contains_marala:
                continue

            for _, row in table.iterrows():
                row_values = [normalize_text(value) for value in row.tolist()]
                joined = " | ".join(row_values).upper()
                if "MARALA" not in joined or "CHENAB" not in joined:
                    continue

                station_index = next(
                    (
                        index
                        for index, value in enumerate(row_values)
                        if "MARALA" in value.upper()
                    ),
                    None,
                )
                if station_index is None:
                    continue

                remaining = row_values[station_index + 1:]
                if len(remaining) < 3:
                    continue

                forecast_text = remaining[2]
                forecast_low, forecast_high = extract_forecast_range(
                    forecast_text
                )
                return {
                    "date": bulletin_date,
                    "river": RIVER,
                    "station": STATION,
                    "inflow": extract_first_number(remaining[0]),
                    "outflow": extract_first_number(remaining[1]),
                    "forecast_24h": extract_first_number(forecast_text),
                    "forecast_low": forecast_low,
                    "forecast_high": forecast_high,
                    "ffd_forecast_text": forecast_text,
                    "ffd_forecast_level": (
                        remaining[3] if len(remaining) >= 4 else ""
                    ),
                    "source_url": source_url,
                    "published_at": extract_publication_time(html),
                }
    except Exception:
        pass

    raise ValueError(
        "Could not find Chenab / Marala data "
        f"in bulletin: {source_url}"
    )


def find_recent_bulletin_links(html, current_url, max_links=15):
    """Recent bulletin PDF or page links from the publication history."""

    soup = BeautifulSoup(html, "html.parser")
    links = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        absolute_url = urljoin(FFD_BASE_URL, href)
        is_pdf = ".pdf" in absolute_url.lower()
        is_bulletin_page = "/b/" in absolute_url.lower()
        if not (is_pdf or is_bulletin_page):
            continue
        if absolute_url == current_url or absolute_url in links:
            continue
        links.append(absolute_url)
        if len(links) >= max_links:
            break

    return links


# ============================================================
# 6. LOAD RECENT FFD MARALA HISTORY
# ============================================================

def _history_column(columns, options, label):
    for name in options:
        if name in columns:
            return name
    raise ValueError(
        f"Missing required CSV column for {label}. "
        f"Tried: {options}"
    )


def load_recent_history_from_csv(live_date, minimum_records=8):
    """Observations strictly before the live bulletin date."""

    if not os.path.exists(HISTORY_FILE):
        raise FileNotFoundError(f"{HISTORY_FILE} was not found.")

    df = pd.read_csv(HISTORY_FILE)
    df.columns = [
        re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower()).strip("_")
        for column in df.columns
    ]

    date_col = _history_column(df.columns, ["date"], "date")
    inflow_col = _history_column(
        df.columns,
        [
            "inflow_thousands_cusecs",
            "inflow_thousands_of_cusecs",
            "inflow",
        ],
        "inflow",
    )
    outflow_col = _history_column(
        df.columns,
        [
            "outflow_thousands_cusecs",
            "outflow_thousands_of_cusecs",
            "outflow",
        ],
        "outflow",
    )

    if "river" in df.columns:
        df = df[
            df["river"].astype(str).str.strip().str.lower() == "chenab"
        ]
    if "station" in df.columns:
        df = df[
            df["station"].astype(str).str.strip().str.lower() == "marala"
        ]

    df["date"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["date"])
    df = df[df["date"] < live_date].copy()

    df["inflow"] = pd.to_numeric(df[inflow_col], errors="coerce")
    df["outflow"] = pd.to_numeric(df[outflow_col], errors="coerce")

    if "forecast_24h_inflow" in df.columns:
        # Values are ranges such as "40-50". pd.to_numeric would make
        # every one of them missing. Training uses the first number.
        # The alert path uses the upper number.
        parsed = df["forecast_24h_inflow"].map(extract_forecast_range)
        df["forecast_low"] = parsed.map(lambda item: item[0])
        df["forecast_high"] = parsed.map(lambda item: item[1])
        df["forecast_24h"] = df["forecast_low"]
        df["ffd_forecast_text"] = df["forecast_24h_inflow"].astype(str)
    else:
        df["forecast_24h"] = np.nan
        df["forecast_low"] = np.nan
        df["forecast_high"] = np.nan
        df["ffd_forecast_text"] = ""
    df["ffd_forecast_level"] = ""
    df["source_url"] = "historical CSV"

    df = (
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
    )
    df = df.tail(max(minimum_records, 10)).copy()

    if len(df) < 7:
        raise RuntimeError(
            f"Only {len(df)} historical records "
            "were available before the live bulletin."
        )

    return df


def fetch_recent_marala_history(minimum_records=8):
    """
    Latest Marala row from FFD, plus earlier rows from the CSV.

    The bulletin HTML is kept on this function as last_bulletin_html
    so the weekly outlook can be parsed without a second download.
    """

    print("\nConnecting to FFD website...")
    latest_html = download_page(FFD_BULLETIN_URL)
    fetch_recent_marala_history.last_bulletin_html = latest_html

    latest_record = extract_marala_from_html(
        latest_html,
        FFD_BULLETIN_URL,
    )
    print("Latest Marala bulletin extracted.")

    live_date = pd.to_datetime(latest_record["date"])
    if pd.isna(live_date):
        raise RuntimeError(
            "Could not determine latest FFD bulletin date."
        )

    historical = load_recent_history_from_csv(
        live_date,
        minimum_records=minimum_records,
    )
    print(f"Historical records loaded from CSV: {len(historical)}")

    history = pd.concat(
        [historical, pd.DataFrame([latest_record])],
        ignore_index=True,
    )
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history = (
        history.dropna(subset=["date", "inflow"])
        .sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )

    print(f"Total observations available to ML: {len(history)}")

    if len(history) >= 2:
        previous_date = history.iloc[-2]["date"]
        latest_date = history.iloc[-1]["date"]
        gap_days = (latest_date - previous_date).days
        if gap_days > 1:
            print(
                "\nWARNING:"
                f" Previous observation is {gap_days} days "
                "before the latest bulletin."
            )
            print(
                "ML prediction can still run, but recent-history "
                "features are less reliable."
            )

    return history


def dashboard_history(limit=60):
    """Recent CSV rows for the dashboard. This does not scrape FFD."""

    frame = load_recent_history_from_csv(
        pd.Timestamp("2100-01-01"),
        minimum_records=limit,
    )
    rows = []
    for _, row in frame.iterrows():
        low = row["forecast_low"]
        high = row["forecast_high"]
        outflow = row["outflow"]
        rows.append({
            "date": pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
            "inflow": float(row["inflow"]),
            "outflow": None if pd.isna(outflow) else float(outflow),
            "forecast_min": None if pd.isna(low) else float(low),
            "forecast_max": None if pd.isna(high) else float(high),
            "forecast_text": (
                None if pd.isna(row["ffd_forecast_text"])
                else str(row["ffd_forecast_text"])
            ),
            "status": get_threshold_risk(row["inflow"]),
        })
    return rows


# ============================================================
# 7. CREATE ML FEATURES
# (Horizon helpers inlined so HF Space does not import ml/scripts.)
# ============================================================

def _aligned(series, index):
    """Values of a calendar series on the original observation dates."""

    return series.reindex(index).to_numpy()


def attach_calendar_history(df, date_col):
    """
    Add lags and rolling history on the calendar, not the row index.

    The Marala record skips from October to the next June. A row
    shift would call that 243-day gap "yesterday". Missing calendar
    days stay missing. Rolling windows use only days before the
    issue date, so the current and future inflows are not features.
    """

    frame = df.copy()
    frame["_history_date"] = pd.to_datetime(frame[date_col])
    frame = (
        frame.sort_values("_history_date")
        .drop_duplicates("_history_date", keep="last")
        .reset_index(drop=True)
    )
    dates = pd.DatetimeIndex(frame["_history_date"])

    inflow = pd.Series(frame["inflow_current"].to_numpy(), index=dates)
    inflow = inflow[~inflow.index.duplicated(keep="last")]
    daily_inflow = inflow.asfreq("D")
    past_inflow = daily_inflow.shift(1)

    frame["inflow_lag_1"] = _aligned(daily_inflow.shift(1), inflow.index)
    frame["inflow_lag_2"] = _aligned(daily_inflow.shift(2), inflow.index)
    frame["inflow_lag_3"] = _aligned(daily_inflow.shift(3), inflow.index)
    frame["inflow_lag_7"] = _aligned(daily_inflow.shift(7), inflow.index)
    frame["inflow_change_1"] = frame["inflow_current"] - frame["inflow_lag_1"]
    frame["inflow_change_3"] = frame["inflow_current"] - frame["inflow_lag_3"]
    frame["inflow_change_7"] = frame["inflow_current"] - frame["inflow_lag_7"]
    frame["inflow_pct_change_1"] = (
        frame["inflow_change_1"] / frame["inflow_lag_1"].replace(0, np.nan)
    )
    frame["inflow_pct_change_3"] = (
        frame["inflow_change_3"] / frame["inflow_lag_3"].replace(0, np.nan)
    )
    frame["inflow_mean_3d"] = _aligned(
        past_inflow.rolling("3D", min_periods=1).mean(),
        inflow.index,
    )
    frame["inflow_mean_7d"] = _aligned(
        past_inflow.rolling("7D", min_periods=1).mean(),
        inflow.index,
    )
    frame["inflow_max_3d"] = _aligned(
        past_inflow.rolling("3D", min_periods=1).max(),
        inflow.index,
    )
    frame["inflow_max_7d"] = _aligned(
        past_inflow.rolling("7D", min_periods=1).max(),
        inflow.index,
    )
    frame["inflow_std_3d"] = _aligned(
        past_inflow.rolling("3D", min_periods=2).std(),
        inflow.index,
    )
    frame["inflow_std_7d"] = _aligned(
        past_inflow.rolling("7D", min_periods=2).std(),
        inflow.index,
    )
    frame["inflow_vs_3d_mean"] = (
        frame["inflow_current"] - frame["inflow_mean_3d"]
    )
    frame["inflow_vs_7d_mean"] = (
        frame["inflow_current"] - frame["inflow_mean_7d"]
    )

    if "outflow_current" in frame.columns:
        outflow = pd.Series(frame["outflow_current"].to_numpy(), index=dates)
        outflow = outflow[~outflow.index.duplicated(keep="last")]
        daily_outflow = outflow.asfreq("D")
        frame["outflow_lag_1"] = _aligned(daily_outflow.shift(1), outflow.index)
        frame["outflow_lag_3"] = _aligned(daily_outflow.shift(3), outflow.index)

    return frame.drop(columns=["_history_date"])


def _issue_row(feature_frame, issue_date):
    """Use the issue-date row, otherwise the latest row."""

    frame = feature_frame.copy()
    if "date" not in frame.columns:
        return frame.iloc[-1:]

    dates = pd.to_datetime(frame["date"], errors="coerce")
    issue = pd.to_datetime(issue_date)
    mask = dates.dt.normalize() == pd.Timestamp(issue).normalize()
    if mask.any():
        return frame.loc[mask].iloc[-1:]
    return frame.iloc[-1:]


def _predict_one_package(package, row):
    """Score one saved pipeline. Returns category, probabilities, ok."""

    if not package or not package.get("model_available", True):
        return None, {}, False
    model = package.get("model")
    features = package.get("features")
    if model is None or not features:
        return None, {}, False

    missing = [name for name in features if name not in row.columns]
    if missing:
        raise ValueError(
            "Issue-day features missing: " + ", ".join(missing)
        )

    prediction = model.predict(row[features])[0]
    probabilities = {}
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(row[features])[0]
        classes = getattr(model, "classes_", [])
        probabilities = {
            str(label): float(prob)
            for label, prob in zip(classes, probs)
        }
    return str(prediction), probabilities, True


def predict_flood_risk_horizons(feature_frame, model_dir, issue_date):
    """
    Score the same issue-day feature row with each horizon model.

    This does not roll the day+1 model forward. A missing horizon
    stays unavailable and is not filled with the day+1 class.
    """

    model_dir = Path(model_dir)
    issue_ts = pd.to_datetime(issue_date)
    row = _issue_row(feature_frame, issue_ts)
    results = []

    for horizon in HORIZONS:
        forecast_date = (
            issue_ts + pd.to_timedelta(horizon, unit="D")
        ).strftime("%Y-%m-%d")
        path = model_dir / "horizons" / f"floodshield_horizon_{horizon}.pkl"
        if horizon == 1 and not path.exists():
            path = model_dir / "floodshield_marala_model.pkl"

        base = {
            "forecast_date": forecast_date,
            "horizon_days": horizon,
            "predicted_category": None,
            "probabilities": {},
            "model_available": False,
        }

        if not path.exists():
            results.append(base)
            continue

        try:
            package = joblib.load(path)
            category, probabilities, available = _predict_one_package(
                package,
                row,
            )
            base["predicted_category"] = category
            base["probabilities"] = probabilities
            base["model_available"] = available
            base["model_name"] = package.get("model_name")
            base["supported_classes"] = list(
                package.get("supported_classes") or []
            )
            base["unsupported_classes"] = list(
                package.get("unsupported_classes") or []
            )
            base["evaluation_reliable"] = bool(
                package.get("evaluation_reliable")
            )
            if not available:
                base["unavailable_reason"] = package.get(
                    "unavailable_reason"
                )
        except Exception as exc:
            base["error"] = str(exc)
            base["model_available"] = False
            base["predicted_category"] = None

        results.append(base)

    return results


def create_features(history):
    """Same issue-day features used to train the horizon models."""

    df = history.copy().sort_values("date").reset_index(drop=True)

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["day_of_year"] = df["date"].dt.dayofyear
    df["day_of_week"] = df["date"].dt.dayofweek
    df["flood_season"] = df["month"].isin([6, 7, 8, 9]).astype(int)

    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["doy_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365.25)

    df["inflow_current"] = df["inflow"]
    df["outflow_current"] = df["outflow"]
    df["forecast_24h"] = df["forecast_24h"]

    df["capacity_utilization"] = df["inflow_current"] / DESIGN_CAPACITY
    df["distance_from_low_flood"] = df["inflow_current"] - LOW_FLOOD

    df = attach_calendar_history(df, "date")

    df["inflow_outflow_difference"] = (
        df["inflow_current"] - df["outflow_current"]
    )
    df["inflow_outflow_ratio"] = (
        df["inflow_current"] / df["outflow_current"].replace(0, np.nan)
    )

    df["forecast_change"] = df["forecast_24h"] - df["inflow_current"]
    df["forecast_change_pct"] = (
        df["forecast_change"] / df["inflow_current"].replace(0, np.nan)
    )
    df["forecast_low_margin"] = df["forecast_24h"] - LOW_FLOOD
    df["forecast_high_margin"] = df["forecast_24h"] - HIGH_FLOOD
    df["forecast_risk_numeric"] = pd.cut(
        df["forecast_24h"],
        bins=[
            -np.inf,
            LOW_FLOOD,
            MEDIUM_FLOOD,
            HIGH_FLOOD,
            VERY_HIGH_FLOOD,
            EXCEPTIONAL_FLOOD,
            np.inf,
        ],
        labels=[0, 1, 2, 3, 4, 5],
        right=False,
    ).astype(float)

    return df


# ============================================================
# 8. LOAD TRAINED MODEL AND PREDICT THE NEXT DAY
# ============================================================

def load_floodshield_model():
    """Load the horizon-1 package saved for the existing engine."""

    if not os.path.exists(MODEL_FILE):
        raise FileNotFoundError(f"{MODEL_FILE} was not found.")

    package = joblib.load(MODEL_FILE)
    for key in ("model", "features"):
        if key not in package:
            raise KeyError(
                f"'{key}' missing from saved model package."
            )
    return package


def make_ml_prediction(feature_df, model_package):
    """Next-day class from the compatible horizon-1 model."""

    model = model_package.get("model")
    if (
        model is None
        or not model_package.get("model_available", True)
    ):
        return None, None, {}
    required_features = model_package["features"]
    latest = feature_df.iloc[-1:].copy()

    missing = [
        feature
        for feature in required_features
        if feature not in latest.columns
    ]
    if missing:
        raise ValueError(
            "Live feature engineering is missing:\n" + "\n".join(missing)
        )

    X_live = latest[required_features].copy()
    prediction = model.predict(X_live)[0]
    confidence = None
    class_probabilities = {}

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(X_live)[0]
        classes = model.classes_
        class_probabilities = {
            str(label): float(probability)
            for label, probability in zip(classes, probabilities)
        }
        confidence = float(np.max(probabilities))

    return prediction, confidence, class_probabilities


def determine_forecast_risk(latest_row):
    """Risk of the upper end of the FFD 24-hour forecast."""

    forecast_high = latest_row.get("forecast_high", np.nan)
    if pd.isna(forecast_high):
        forecast_high = latest_row.get("forecast_24h", np.nan)
    return get_threshold_risk(forecast_high)


def determine_final_risk(current_risk, forecast_risk, ml_risk):
    """
    Highest of current condition, 24-hour forecast, and ML.

    Unknown values are ignored. This function does not look at
    Jammu weather and does not downgrade an official class it
    is given.
    """

    valid_risks = [
        risk
        for risk in (current_risk, forecast_risk, ml_risk)
        if risk in SEVERITY
    ]
    if not valid_risks:
        return "Unknown"

    return max(valid_risks, key=lambda risk: SEVERITY[risk])


# ============================================================
# 9. JAMMU EXTENDED FORECAST
# ============================================================

def _jammu_unavailable(reason):
    """Failure payload. Precipitation is null, never zero."""

    return {
        "source_url": JAMMU_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "available": False,
        "forecasts": [],
        "error": reason,
        "role": "external_weather_indicator",
        "note": JAMMU_NOTE,
        "from_cache": False,
    }


def cache_is_fresh(payload, now, ttl_seconds, today):
    """True only for a successful cache that is young and not entirely past."""

    if not payload or not payload.get("available"):
        return False
    try:
        stamp = datetime.fromisoformat(payload.get("retrieved_at"))
    except (TypeError, ValueError):
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    age = (now - stamp.astimezone(timezone.utc)).total_seconds()
    if age < 0 or age > ttl_seconds:
        return False
    dates = [
        item.get("date")
        for item in payload.get("forecasts") or []
        if item.get("date")
    ]
    today_text = pd.Timestamp(today).date().isoformat()
    if dates and not any(item >= today_text for item in dates):
        return False
    if payload.get("source_name") != "open-meteo":
        return False
    if len(dates) < JAMMU_FORECAST_DAYS:
        return False
    return True


def _read_jammu_cache():
    if not JAMMU_CACHE.exists():
        return None
    try:
        payload = json.loads(JAMMU_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not cache_is_fresh(
        payload,
        datetime.now(timezone.utc),
        JAMMU_CACHE_SECONDS,
        karachi_today(),
    ):
        print("\nJammu cache is missing, expired, or covers only past dates.")
        return None

    payload["from_cache"] = True
    payload["role"] = "external_weather_indicator"
    payload["note"] = payload.get("note") or JAMMU_NOTE
    return payload


def _write_jammu_cache(payload):
    JAMMU_CACHE.parent.mkdir(parents=True, exist_ok=True)
    stored = dict(payload)
    stored.pop("from_cache", None)
    JAMMU_CACHE.write_text(
        json.dumps(stored, indent=2),
        encoding="utf-8",
    )


def _parse_temperature(text):
    raw = normalize_text(text)
    numbers = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", raw)]
    high = numbers[0] if numbers else None
    low = numbers[1] if len(numbers) > 1 else None
    lowered = raw.lower()
    if "°c" in lowered or "℃" in raw:
        unit = "C"
    elif "°f" in lowered or "℉" in raw:
        unit = "F"
    else:
        unit = None

    def to_celsius(reading):
        if reading is None or unit is None:
            return None
        if unit == "C":
            return reading
        return (reading - 32.0) * 5.0 / 9.0

    return {
        "text": raw,
        "unit": unit,
        "high_c": to_celsius(high),
        "low_c": to_celsius(low),
    }


def _parse_precip_amount(text):
    """Return millimetres only when the unit is explicit."""

    raw = normalize_text(text)
    if raw.lower() in {"", "-", "—", "–", "n/a", "na", "none"}:
        return None, raw

    match = re.search(r"\d+(?:\.\d+)?", raw.replace(",", ""))
    if not match:
        return None, raw

    value = float(match.group())
    lowered = raw.lower()
    if "mm" in lowered:
        return value, raw
    if "cm" in lowered:
        return value * 10.0, raw
    if '"' in raw or "inch" in lowered or re.search(r"\bin\b", lowered):
        return value * 25.4, raw
    return None, raw


def _parse_chance(text):
    raw = normalize_text(text)
    if raw.lower() in {"", "-", "—", "–", "n/a", "na", "none"}:
        return None
    match = re.search(r"\d+(?:\.\d+)?", raw)
    if not match:
        return None
    return float(match.group())


def _reference_year(page_text):
    match = re.search(
        r"Updated[\s\S]{0,160}?(20\d{2})",
        page_text,
        re.IGNORECASE,
    )
    today = karachi_today()
    if match:
        return int(match.group(1)), today.month
    return today.year, today.month


def _assign_forecast_dates(day_texts, page_text):
    """Turn 'Thu Oct 22' into dates, wrapping the year after December."""

    year, reference_month = _reference_year(page_text)
    dates = []
    previous_month = None

    for day_text in day_texts:
        month_match = re.search(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"[a-z]*\s+(\d{1,2})",
            day_text,
            re.IGNORECASE,
        )
        if not month_match:
            dates.append(None)
            continue

        month = MONTH_NUMBERS[month_match.group(1).lower()[:3]]
        day = int(month_match.group(2))
        if previous_month is not None and month < previous_month:
            year += 1
        elif (
            previous_month is None
            and reference_month >= 11
            and month <= 2
            and month < reference_month
        ):
            year += 1

        try:
            dates.append(datetime(year, month, day).date())
        except ValueError:
            dates.append(None)
        previous_month = month

    return dates


def _header_map(headers):
    """Column indexes from header words, not from a fixed layout."""

    indexes = {}
    for index, header in enumerate(headers):
        text = header.lower().strip()
        if text == "day" or text.startswith("day"):
            indexes.setdefault("day", index)
        elif "weather" in text or text == "condition":
            indexes.setdefault("weather", index)
        elif "chance" in text:
            indexes.setdefault("chance", index)
        elif "amount" in text:
            indexes.setdefault("amount", index)
        elif (
            ("temperature" in text or text == "temp")
            and "feels" not in text
        ):
            indexes.setdefault("temperature", index)
    return indexes


def parse_jammu_extended_html(html):
    """
    Parse the Jammu extended-forecast table.

    An empty or unrecognized table is unavailable. Missing rain is
    null, not zero.
    """

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    forecasts = []

    for table in soup.find_all("table"):
        all_rows = table.find_all("tr")
        header_index = None
        columns = None
        for index, row in enumerate(all_rows):
            cells = [
                normalize_text(cell.get_text(" ", strip=True))
                for cell in row.find_all(["th", "td"])
            ]
            mapping = _header_map(cells)
            if mapping.get("day") is None:
                continue
            if "chance" in mapping or "amount" in mapping:
                header_index = index
                columns = mapping
                break
        if header_index is None:
            continue

        for row in all_rows[header_index + 1:]:
            cells = [
                normalize_text(cell.get_text(" ", strip=True))
                for cell in row.find_all(["th", "td"])
            ]
            if len(cells) <= columns["day"]:
                continue
            day_text = cells[columns["day"]]
            if not re.search(
                r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec",
                day_text,
                re.IGNORECASE,
            ):
                continue

            def cell(name):
                index = columns.get(name)
                if index is None or index >= len(cells):
                    return ""
                return cells[index]

            temperature = _parse_temperature(cell("temperature"))
            amount_mm, amount_text = _parse_precip_amount(cell("amount"))
            forecasts.append({
                "day_text": day_text,
                "condition": cell("weather") or None,
                "temperature_text": temperature["text"] or None,
                "temperature_unit": temperature["unit"],
                "temperature_high_c": temperature["high_c"],
                "temperature_low_c": temperature["low_c"],
                "precip_chance_pct": _parse_chance(cell("chance")),
                "precip_amount_mm": amount_mm,
                "precip_amount_text": amount_text or None,
            })

        if forecasts:
            break

    dates = _assign_forecast_dates(
        [item["day_text"] for item in forecasts],
        page_text,
    )
    for item, forecast_date in zip(forecasts, dates):
        item["date"] = (
            forecast_date.isoformat() if forecast_date else None
        )

    if not forecasts:
        return _jammu_unavailable(
            "Jammu forecast table was empty or could not be parsed."
        )

    return {
        "source_url": JAMMU_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "available": True,
        "forecasts": forecasts,
        "error": None,
        "role": "external_weather_indicator",
        "note": JAMMU_NOTE,
        "from_cache": False,
    }


def _optional_number(values, index):
    """Keep a real zero. A missing field stays None."""

    if not isinstance(values, list) or index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _wmo_text(code):
    if code is None:
        return None
    code = int(code)
    if code == 0:
        return "Clear"
    if code in (1, 2, 3):
        return "Cloudy"
    if code in (45, 48):
        return "Fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "Rain"
    if 71 <= code <= 77 or 85 <= code <= 86:
        return "Snow"
    if code >= 95:
        return "Thunderstorm"
    return f"Weather code {code}"


def parse_open_meteo_daily(payload):
    """
    Daily Jammu rows from an Open-Meteo JSON body.

    A missing precipitation field stays null. A reported 0 stays 0.
    """

    daily = (payload or {}).get("daily") or {}
    dates = daily.get("time") or []
    if not dates:
        raise ValueError("Open-Meteo returned no daily dates.")

    forecasts = []
    for index, day in enumerate(dates):
        amount = _optional_number(daily.get("precipitation_sum"), index)
        chance = _optional_number(
            daily.get("precipitation_probability_max"),
            index,
        )
        high = _optional_number(daily.get("temperature_2m_max"), index)
        low = _optional_number(daily.get("temperature_2m_min"), index)
        code = _optional_number(daily.get("weather_code"), index)
        forecasts.append({
            "date": day,
            "day_text": day,
            "condition": _wmo_text(code),
            "temperature_text": (
                None if high is None
                else f"{high:g} °C" if low is None
                else f"{high:g} / {low:g} °C"
            ),
            "temperature_unit": "C" if high is not None else None,
            "temperature_high_c": high,
            "temperature_low_c": low,
            "precip_chance_pct": chance,
            "precip_amount_mm": amount,
            "precip_amount_text": None if amount is None else f"{amount:g} mm",
        })
    return forecasts


def _open_meteo_payload(forecasts, error=None):
    available = bool(forecasts) and error is None
    return {
        "source_url": OPEN_METEO_URL,
        "source_name": "open-meteo",
        "location": {
            "name": "Jammu",
            "latitude": JAMMU_LATITUDE,
            "longitude": JAMMU_LONGITUDE,
            "timezone": "Asia/Karachi",
        },
        "forecast_days_requested": JAMMU_FORECAST_DAYS,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "available": available,
        "forecasts": forecasts,
        "error": error,
        "role": "external_weather_indicator",
        "changes_flood_category": False,
        "note": JAMMU_NOTE,
        "from_cache": False,
    }


def fetch_open_meteo_jammu(get=None, pause_seconds=1):
    """
    14-day Jammu daily forecast from Open-Meteo.

    This is the Jammu weather source. It is not a Chenab discharge
    forecast and it does not change the flood category.
    """

    getter = get or requests.get
    params = {
        "latitude": JAMMU_LATITUDE,
        "longitude": JAMMU_LONGITUDE,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
        ]),
        "timezone": "Asia/Karachi",
        "forecast_days": JAMMU_FORECAST_DAYS,
    }
    last_error = "Open-Meteo request failed."
    for attempt in range(1, 4):
        try:
            response = getter(
                OPEN_METEO_URL,
                params=params,
                headers={"User-Agent": "FloodShieldPAK/1.0"},
                timeout=JAMMU_TIMEOUT,
            )
            status = int(getattr(response, "status_code", 200))
            if status >= 400:
                last_error = f"HTTP {status} from Open-Meteo"
                print(f"\nOpen-Meteo attempt {attempt} failed: {last_error}")
            else:
                forecasts = parse_open_meteo_daily(response.json())
                if len(forecasts) < JAMMU_FORECAST_DAYS:
                    last_error = (
                        f"Open-Meteo returned {len(forecasts)} days, "
                        f"expected {JAMMU_FORECAST_DAYS}."
                    )
                    print(f"\nOpen-Meteo attempt {attempt} failed: {last_error}")
                else:
                    print(
                        "\nOpen-Meteo Jammu forecast: "
                        f"{forecasts[0]['date']} to {forecasts[-1]['date']} "
                        f"({len(forecasts)} days)."
                    )
                    return _open_meteo_payload(forecasts)
        except (requests.RequestException, ValueError, AttributeError) as exc:
            last_error = type(exc).__name__
            print(f"\nOpen-Meteo attempt {attempt} failed: {last_error}")
        if attempt < 3 and pause_seconds:
            time.sleep(pause_seconds)

    failed = _open_meteo_payload([], error=last_error)
    print("\nJammu weather is unavailable. Rain was not set to zero.")
    return failed


def fetch_jammu_extended_forecast():
    """
    Jammu 14-day weather from Open-Meteo, cached for six hours.

    An expired cache, a cache from another site, or a short cache is
    not reused. Missing rain is left null.
    """

    cached = _read_jammu_cache()
    if cached is not None:
        print(
            "\nJammu Open-Meteo forecast loaded from the 6-hour cache: "
            f"{len(cached.get('forecasts') or [])} days."
        )
        cached["changes_flood_category"] = False
        return cached

    forecast = fetch_open_meteo_jammu()
    if forecast.get("available"):
        _write_jammu_cache(forecast)
    return forecast


def jammu_for_date(jammu, forecast_date):
    """One day's Jammu fields, marked as an external indicator."""

    base = {
        "role": "external_weather_indicator",
        "available": False,
        "source_url": (jammu or {}).get("source_url") or OPEN_METEO_URL,
        "source_name": (jammu or {}).get("source_name"),
        "note": (jammu or {}).get("note") or JAMMU_NOTE,
        "changes_flood_category": False,
        "condition": None,
        "temperature_text": None,
        "temperature_high_c": None,
        "temperature_low_c": None,
        "precip_chance_pct": None,
        "precip_amount_mm": None,
        "precip_amount_text": None,
    }
    if not jammu or not jammu.get("available"):
        base["error"] = (jammu or {}).get("error")
        return base

    target = forecast_date.isoformat()
    for item in jammu.get("forecasts", []):
        if item.get("date") != target:
            continue
        base.update({
            "available": True,
            "error": None,
            "condition": item.get("condition"),
            "temperature_text": item.get("temperature_text"),
            "temperature_high_c": item.get("temperature_high_c"),
            "temperature_low_c": item.get("temperature_low_c"),
            "precip_chance_pct": item.get("precip_chance_pct"),
            "precip_amount_mm": item.get("precip_amount_mm"),
            "precip_amount_text": item.get("precip_amount_text"),
        })
        return base

    base["error"] = "No Jammu row for this date."
    return base


# ============================================================
# 10. ALERTS
# ============================================================

def get_alert_action(risk):
    """Public-safety sentence. Official instructions take priority."""

    actions = {
        "Normal": (
            "No flood condition is currently indicated. "
            "Continue monitoring official updates."
        ),
        "Low": (
            "River flow is elevated. People near the river "
            "should remain alert and monitor official updates."
        ),
        "Medium": (
            "Flood risk is significant. People in low-lying "
            "areas near the river should prepare for possible "
            "protective action and follow official instructions."
        ),
        "High": (
            "High flood risk is indicated. Avoid riverbanks "
            "and flood-prone areas and be ready to follow "
            "evacuation instructions from authorities."
        ),
        "Very High": (
            "Very high flood risk is indicated. People in "
            "vulnerable areas should urgently follow official "
            "safety and evacuation instructions."
        ),
        "Exceptional": (
            "Exceptional flood danger is indicated. Treat the "
            "situation as an emergency and immediately follow "
            "official evacuation and safety instructions."
        ),
        "Insufficient data": (
            "A flood category could not be set for this day. "
            "Do not treat the gap as Normal or as zero risk. "
            "Monitor official FFD updates."
        ),
    }
    return actions.get(
        risk,
        "Monitor official FFD and disaster-management updates.",
    )


def create_template_alert(result):
    """Next-day alert used when Qwen is not available."""

    risk = result["final_risk"]
    inflow = result["current_inflow"]
    forecast_text = result["ffd_forecast_text"]
    ml_risk = result["ml_prediction"]

    inflow_text = (
        "unavailable" if inflow is None or (isinstance(inflow, float) and np.isnan(inflow))
        else f"{float(inflow):.1f}"
    )
    status = result.get("forecast_status") or "current"
    if status == "expired":
        status_line = (
            "This FFD bulletin's 24-hour forecast date has passed. "
            "It is not a current forecast.\n"
        )
    elif status == "stale":
        status_line = (
            f"The latest FFD bulletin is dated {result.get('date')}, "
            "which is before today in Asia/Karachi. "
            "Only forecast dates that are still today or later apply.\n"
        )
    else:
        status_line = (
            f"FFD bulletin date: {result.get('date')}.\n"
        )

    english = (
        f"FloodShield Alert — Chenab River at Marala\n\n"
        f"{status_line}"
        f"Current inflow: {inflow_text} thousand cusecs.\n"
        f"FFD 24-hour forecast: {forecast_text} thousand cusecs.\n"
        f"ML next-day prediction: {ml_risk}.\n"
        f"Final alert level: {risk}.\n\n"
        f"{get_alert_action(risk)}\n\n"
        f"Source: Pakistan Meteorological Department, "
        f"Flood Forecasting Division (FFD)."
    )
    urdu = (
        f"فلڈ شیلڈ الرٹ — دریائے چناب، مرالہ\n\n"
        f"موجودہ پانی کا بہاؤ: {inflow_text} ہزار کیوسک\n"
        f"FFD کی اگلے 24 گھنٹوں کی پیش گوئی: "
        f"{forecast_text} ہزار کیوسک\n"
        f"مشین لرننگ کی اگلے دن کی پیش گوئی: {ml_risk}\n"
        f"حتمی الرٹ لیول: {risk}\n\n"
        f"{URDU_ACTIONS.get(risk, 'سرکاری اطلاعات پر نظر رکھیں۔')}"
    )
    return {
        "english": english,
        "urdu": urdu,
        "generated_by": "FloodShield templates",
        "alert_source": "template",
        "qwen_status": "not_called",
        "qwen_error": None,
    }


def qwen_configuration_status():
    """Configuration check. The key itself is never returned."""

    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(REPO_ROOT / ".env")
    key = os.getenv("DASHSCOPE_API_KEY") or ""
    base_url = os.getenv("DASHSCOPE_BASE_URL") or ""
    model = os.getenv("DASHSCOPE_MODEL") or "qwen-flash"
    return {
        "configured": bool(key.strip() and base_url.strip()),
        "key_present": bool(key.strip()),
        "base_url_set": bool(base_url.strip()),
        "model": model,
    }


def _qwen_model_name():
    return os.getenv("DASHSCOPE_MODEL") or "qwen-flash"


def _sanitize_error(exc):
    """Drop credentials from an exception before it is logged."""

    detail = str(exc)
    key = os.getenv("DASHSCOPE_API_KEY") or ""
    if key:
        detail = detail.replace(key, "[redacted]")
    detail = re.sub(r"sk-[A-Za-z0-9._\-]{8,}", "[redacted]", detail)
    detail = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", detail, flags=re.I)
    return f"{type(exc).__name__}: {detail[:240]}"


def _qwen_disabled_reason():
    if os.getenv("FLOODSHIELD_DISABLE_QWEN") == "1":
        return "Qwen disabled by FLOODSHIELD_DISABLE_QWEN"
    status = qwen_configuration_status()
    if not status["configured"]:
        return "DASHSCOPE_API_KEY or DASHSCOPE_BASE_URL is not set"
    return None


def _qwen_client():
    if _qwen_disabled_reason():
        return None
    from openai import OpenAI

    return OpenAI(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url=os.environ["DASHSCOPE_BASE_URL"],
        timeout=30,
    )


_qwen_runtime = {"blocked_reason": None}


def probe_qwen():
    """One small completion. Does not choose a flood category."""

    status = qwen_configuration_status()
    reason = _qwen_disabled_reason()
    if reason:
        return {
            **status,
            "qwen_status": "unavailable",
            "error": reason,
        }
    try:
        client = _qwen_client()
        response = client.chat.completions.create(
            model=_qwen_model_name(),
            messages=[{
                "role": "user",
                "content": 'Reply with JSON only: {"ok": true}',
            }],
            temperature=0,
            max_tokens=30,
        )
        content = response.choices[0].message.content or ""
        return {
            **status,
            "qwen_status": "success",
            "error": None,
            "reply_received": bool(content.strip()),
        }
    except Exception as exc:
        return {
            **status,
            "qwen_status": "unavailable",
            "error": _sanitize_error(exc),
        }


def _parse_qwen_json(content):
    content = re.sub(
        r"^```(?:json)?\s*",
        "",
        content.strip(),
        flags=re.IGNORECASE,
    )
    content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def _template_alert(alert, source, status, error=None):
    """Mark a template so it cannot be reported as a Qwen success."""

    stamped = dict(alert)
    stamped["generated_by"] = "FloodShield templates"
    stamped["alert_source"] = source
    stamped["qwen_status"] = status
    stamped["qwen_error"] = error
    return stamped


def _qwen_block_reason():
    return _qwen_runtime.get("blocked_reason") or _qwen_disabled_reason()


def _blocked_template(alert, reason):
    unconfigured = (
        "not set" in reason.lower()
        or "disabled" in reason.lower()
    )
    if unconfigured:
        return _template_alert(
            alert,
            "template_unconfigured",
            "unavailable",
            reason,
        )
    return _template_alert(alert, "template_fallback", "fallback", reason)


def generate_qwen_alert(result):
    """
    Qwen writes the next-day alert only.

    The category is already decided. A failed or skipped call is
    labeled as a template. It is never labeled as Qwen.
    """

    template = create_template_alert(result)
    reason = _qwen_block_reason()
    if reason:
        print(f"\nQwen not used: {reason}")
        print("Using built-in bilingual templates.")
        return _blocked_template(template, reason)

    locked_risk = result["final_risk"]
    try:
        client = _qwen_client()
        prompt = f"""
You are the language-generation component of AI FloodShield PAK.

The flood-risk calculations have already been completed by deterministic
rules and a trained machine-learning model.

DO NOT recalculate, increase, decrease or change the risk category.

River: Chenab
Station: Marala
Date: {result['date']}
Current inflow: {result['current_inflow']:.1f} thousand cusecs
Current outflow: {result['current_outflow']:.1f} thousand cusecs
Current threshold danger: {result['current_risk']}
FFD next-24-hour forecast: {result['ffd_forecast_text']} thousand cusecs
FFD forecast risk: {result['forecast_risk']}
ML next-day prediction: {result['ml_prediction']}
Final FloodShield alert level: {result['final_risk']}

Write a short public flood alert.

Requirements:
1. Keep FINAL ALERT LEVEL exactly "{result['final_risk']}".
2. Do not invent weather, evacuation orders, locations, measurements or facts.
3. State that official government instructions take priority.
4. Use simple language understandable by the general public.
5. Do not claim the ML prediction is certain.
6. Return JSON only, exactly in this structure:

{{
    "english": "...",
    "urdu": "..."
}}
"""
        response = client.chat.completions.create(
            model=_qwen_model_name(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise bilingual public safety "
                        "alerts. Never change provided risk levels. "
                        "You are not a forecast model and you cannot "
                        "browse the web."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        if result["final_risk"] != locked_risk:
            raise RuntimeError("Alert generation changed final_risk.")
        alert = _parse_qwen_json(response.choices[0].message.content)
        english = alert["english"]
        if locked_risk not in english:
            raise ValueError("Qwen alert dropped the decided category.")
        return {
            "english": english,
            "urdu": alert["urdu"],
            "generated_by": "Qwen",
            "alert_source": "qwen",
            "qwen_status": "success",
            "qwen_error": None,
        }
    except Exception as exc:
        sanitized = _sanitize_error(exc)
        _qwen_runtime["blocked_reason"] = sanitized
        print(f"\nWARNING: Qwen alert generation failed: {sanitized}")
        print("Using built-in alert templates instead.")
        return _template_alert(
            template,
            "template_fallback",
            "fallback",
            sanitized,
        )


def create_horizon_template_alert(day):
    """Deterministic English and Urdu text for one outlook day."""

    risk = day["final_risk"]
    basis = {
        "official_and_model": (
            "This category is the higher of official FFD guidance "
            "covering this date and this horizon's model."
        ),
        "official": (
            "This category comes from official FFD guidance. "
            "A horizon model was not applied."
        ),
        "model": (
            "This category comes from this horizon's model. "
            "No official flood class covers this date. "
            "The model result is not certain."
        ),
        "insufficient_data": (
            "Neither an official flood class nor a horizon model "
            "is available. This day is not Normal and it is not "
            "zero risk."
        ),
    }.get(day["decision_basis"], "Monitor official updates.")

    urdu_basis = {
        "official_and_model":
            "یہ درجہ سرکاری رہنمائی اور اس دن کے ماڈل میں سے "
            "زیادہ محتاط درجہ ہے۔",
        "official":
            "یہ درجہ سرکاری ایف ایف ڈی رہنمائی سے آیا ہے۔",
        "model":
            "یہ درجہ اس دن کے مشین لرننگ ماڈل سے آیا ہے۔ "
            "یہ یقینی پیش گوئی نہیں۔",
        "insufficient_data":
            "اس دن کے لیے سرکاری درجہ اور ماڈل دونوں نہیں ہیں۔ "
            "اسے نارمل یا صفر خطرہ نہ سمجھا جائے۔",
    }.get(day["decision_basis"], "سرکاری اطلاعات پر نظر رکھیں۔")

    reasons = "\n".join(f"- {reason}" for reason in day["reasons"])
    missing_bits = []
    missing = day["missing"]
    if missing.get("official_daily_discharge"):
        missing_bits.append(
            "no daily Marala discharge number past 24 hours"
        )
    if missing.get("ml_model"):
        missing_bits.append("horizon model unavailable")
    if missing.get("jammu_weather"):
        missing_bits.append("Jammu weather unavailable")
    missing_text = ", ".join(missing_bits) if missing_bits else "none"

    stale_sentence = ""
    stale_urdu = ""
    if day.get("expired") or day.get("forecast_status") == "expired":
        stale_sentence = (
            f"Forecast date {day['forecast_date']} is before today. "
            "This row is expired and is not a current forecast.\n"
        )
        stale_urdu = (
            f"پیش گوئی کی تاریخ {day['forecast_date']} گزر چکی ہے۔ "
            "یہ موجودہ پیش گوئی نہیں۔\n"
        )
    elif day.get("stale"):
        stale_sentence = (
            f"The FFD bulletin date is {day['issue_date']}, which is "
            "older than today in Asia/Karachi. This date is anchored "
            "to the bulletin, not labeled as today.\n"
        )
        stale_urdu = (
            f"ایف ایف ڈی بلیٹن کی تاریخ {day['issue_date']} ہے اور "
            "یہ آج کی تاریخ نہیں۔ یہ پیش گوئی بلیٹن کی تاریخ سے جڑی ہے۔\n"
        )

    english = (
        f"FloodShield outlook — Chenab River at Marala\n\n"
        f"Forecast date: {day['forecast_date']} "
        f"(day +{day['horizon_days']} from bulletin "
        f"{day['issue_date']}).\n"
        f"{stale_sentence}"
        f"FloodShield category: {risk}.\n"
        f"{basis}\n"
        f"Reasons:\n{reasons}\n"
        f"Missing data: {missing_text}.\n\n"
        f"{get_alert_action(risk)}\n\n"
        f"Jammu weather does not change this category. "
        f"Official government instructions take priority."
    )
    urdu = (
        f"فلڈ شیلڈ آؤٹ لک — دریائے چناب، مرالہ\n\n"
        f"پیش گوئی کی تاریخ: {day['forecast_date']} "
        f"(بلیٹن {day['issue_date']} سے دن +{day['horizon_days']})\n"
        f"{stale_urdu}"
        f"فلڈ شیلڈ درجہ: {risk}\n"
        f"{urdu_basis}\n"
        f"کمی: {missing_text}\n\n"
        f"{URDU_ACTIONS.get(risk, 'سرکاری اطلاعات پر نظر رکھیں۔')}\n\n"
        f"جموں کا موسم اس درجے کو نہیں بدلتا۔ "
        f"سرکاری ہدایات مقدم ہیں۔"
    )
    return {
        "english": english,
        "urdu": urdu,
        "generated_by": "FloodShield templates",
        "alert_source": "template",
        "qwen_status": "not_called",
        "qwen_error": None,
    }


def generate_horizon_alert(day):
    """
    Optional Qwen wording for one decided day.

    The template is used when the key is missing, the call fails,
    or the reply does not keep the decided category.
    """

    template = create_horizon_template_alert(day)
    reason = _qwen_block_reason()
    if reason:
        return _blocked_template(template, reason)

    try:
        client = _qwen_client()
        prompt = f"""
Rewrite this flood outlook in clear English and Urdu.
DO NOT change the category "{day['final_risk']}".
DO NOT add measurements, places, rain amounts, or orders
that are not in the template.
Return JSON only: {{"english": "...", "urdu": "..."}}

{template['english']}
"""
        response = client.chat.completions.create(
            model=_qwen_model_name(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You only rephrase a decided flood category. "
                        "Never change it. You are not a forecast model."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        alert = _parse_qwen_json(response.choices[0].message.content)
        if day["final_risk"] not in alert["english"]:
            reason = "Qwen reply dropped the decided category."
            _qwen_runtime["blocked_reason"] = reason
            return _template_alert(
                template,
                "template_fallback",
                "fallback",
                reason,
            )
        return {
            "english": alert["english"],
            "urdu": alert["urdu"],
            "generated_by": "Qwen",
            "alert_source": "qwen",
            "qwen_status": "success",
            "qwen_error": None,
        }
    except Exception as exc:
        sanitized = _sanitize_error(exc)
        _qwen_runtime["blocked_reason"] = sanitized
        print(f"\nWARNING: Qwen horizon alert failed: {sanitized}")
        return _template_alert(
            template,
            "template_fallback",
            "fallback",
            sanitized,
        )


# ============================================================
# 11. SEVEN-DAY OUTLOOK
# ============================================================

def _horizon_lookup(ml_horizons):
    found = {}
    for item in ml_horizons or []:
        found[int(item["horizon_days"])] = item
    return found


def build_seven_day_outlook(
    issue_date,
    current_risk,
    forecast_risk,
    forecast_text,
    forecast_level,
    forecast_low,
    forecast_high,
    ml_prediction,
    ml_probabilities,
    ml_horizons,
    jammu,
    ffd_outlook,
    final_risk,
    current_inflow,
    current_outflow,
    source_url,
):
    """
    Days issue_date+1 through issue_date+7.

    Day +1 uses the same final category as the top-level result.
    Later days are not floored by today's observed category.
    """

    issue_ts = pd.Timestamp(issue_date)
    issue_day = issue_ts.date()
    today = karachi_today()
    stale = issue_day != today
    freshness_note = (
        f"FFD bulletin date is {issue_day.isoformat()}. "
        f"Asia/Karachi today is {today.isoformat()}. "
    )
    if stale:
        freshness_note += (
            "The bulletin is stale. The seven dates are anchored to "
            "the bulletin observation date and are not labeled as "
            "starting today. "
        )
    else:
        freshness_note += "The bulletin date matches Asia/Karachi today. "
    if ffd_outlook and ffd_outlook.get("next_bulletin"):
        freshness_note += (
            "The bulletin says the next forecast bulletin will be "
            f"issued on {ffd_outlook['next_bulletin']}."
        )

    data_freshness = {
        "bulletin_date": issue_day.isoformat(),
        "as_of_local_date": today.isoformat(),
        "timezone": "Asia/Karachi",
        "stale": stale,
        "note": freshness_note.strip(),
        "next_bulletin": (ffd_outlook or {}).get("next_bulletin"),
        "published_at": (ffd_outlook or {}).get("published_at"),
        "source_url": source_url,
    }

    horizons = _horizon_lookup(ml_horizons)
    qualitative = official_category_from_text(forecast_level)
    days = []

    for step in range(1, 8):
        forecast_date = issue_day + timedelta(days=step)
        weekly_category, weekly_text = official_category_for_date(
            ffd_outlook,
            forecast_date,
        )
        horizon = horizons.get(step, {})
        weather = jammu_for_date(jammu, forecast_date)

        if step == 1:
            ml_category = (
                ml_prediction if ml_prediction in SEVERITY else None
            )
            ml_available = ml_category is not None
            probabilities = ml_probabilities or {}
            official_category = higher_risk(
                [forecast_risk, qualitative, weekly_category]
            )
            official_text = forecast_text
            official_source = "FFD 24-hour quantitative forecast"
            day_final = final_risk
            flow = {
                "low": as_optional_float(forecast_low),
                "high": as_optional_float(forecast_high),
                "unit": "thousand cusecs",
                "applies": True,
            }
        else:
            ml_category = horizon.get("predicted_category")
            ml_available = bool(horizon.get("model_available")) and (
                ml_category in SEVERITY
            )
            if not ml_available:
                ml_category = None
            probabilities = horizon.get("probabilities") or {}
            official_category = weekly_category
            official_text = weekly_text
            official_source = (
                "FFD weekly flood outlook"
                if official_category
                else None
            )
            if official_category and ml_category:
                day_final = higher_risk(
                    [official_category, ml_category]
                )
            elif official_category:
                day_final = official_category
            elif ml_category:
                day_final = ml_category
            else:
                day_final = "Insufficient data"
            flow = {
                "low": None,
                "high": None,
                "unit": "thousand cusecs",
                "applies": False,
                "note": (
                    "FFD does not publish a daily Marala discharge "
                    "number past 24 hours."
                ),
            }

        day_state = forecast_day_status(issue_day, forecast_date, today)
        expired = day_state["expired"]
        if expired:
            official_category = None
            official_source = None
            ml_category = None
            ml_available = False
            day_final = "Insufficient data"
            flow["applies"] = False
            flow["note"] = (
                "This forecast date is before today. "
                "The bulletin does not provide a current outlook for it."
            )

        if official_category and ml_available:
            basis = "official_and_model"
        elif official_category:
            basis = "official"
        elif ml_available:
            basis = "model"
        else:
            basis = "insufficient_data"

        reasons = []
        if expired:
            reasons.append(
                "This forecast date is before today in Asia/Karachi. "
                "Official guidance and the model output are not "
                "described as a current forecast."
            )
        if step == 1:
            reasons.append(
                f"Current observed category is {current_risk} "
                "and is included in the day +1 decision."
            )
            reasons.append(
                "FFD 24-hour upper-end category is "
                f"{forecast_risk}. Text: {forecast_text}."
            )
            if qualitative:
                reasons.append(
                    "FFD qualitative 24-hour level maps to "
                    f"{qualitative} ({forecast_level})."
                )
            if weekly_category:
                reasons.append(
                    "The weekly official outlook also covers this "
                    f"date as {weekly_category}."
                )
            if ml_available:
                reasons.append(
                    f"Horizon 1 model category is {ml_category}."
                )
            else:
                reasons.append("Horizon 1 model was not available.")
        else:
            reasons.append(
                f"Latest observed category {current_risk} is context "
                "only and is not an automatic floor for this day."
            )
            if official_category:
                reasons.append(
                    "Official weekly outlook covers this date as "
                    f"{official_category}."
                )
            else:
                reasons.append(
                    "No official flood class covers this date."
                )
            if ml_available:
                reasons.append(
                    f"Horizon {step} model category is {ml_category}."
                )
            else:
                reasons.append(
                    f"Horizon {step} model was not available. "
                    "The day +1 prediction was not copied forward."
                )
        reasons.append(
            "Jammu weather is an external indicator and does not "
            "change the category."
        )
        if ffd_outlook and ffd_outlook.get("meteorological_text"):
            reasons.append(
                "Weekly rainfall wording is meteorological context "
                "only: "
                + ffd_outlook["meteorological_text"]
            )

        day = {
            "issue_date": issue_day.isoformat(),
            "forecast_date": forecast_date.isoformat(),
            "horizon_days": step,
            "stale": stale,
            "expired": expired,
            "forecast_status": day_state["status"],
            "official_ffd": {
                "category": official_category,
                "text": official_text,
                "level_text": forecast_level if step == 1 else None,
                "applies": (not expired) and official_category in SEVERITY,
                "expired": expired,
                "source": official_source,
                "coverage_start": (
                    forecast_date.isoformat() if step == 1
                    else (ffd_outlook or {}).get("start_date")
                ),
                "coverage_end": (
                    forecast_date.isoformat() if step == 1
                    else (ffd_outlook or {}).get("end_date")
                ),
            },
            "river_flow_forecast": flow,
            "discharge_context": {
                "latest_inflow_thousand_cusecs": as_optional_float(
                    current_inflow
                ),
                "latest_outflow_thousand_cusecs": as_optional_float(
                    current_outflow
                ),
                "observed_category": current_risk,
                "observed_date": issue_day.isoformat(),
                "used_in_decision": step == 1,
            },
            "jammu_weather": weather,
            "ml_prediction": {
                "category": ml_category,
                "model_available": ml_available,
                "probabilities": probabilities if not expired else {},
                "horizon_days": step,
                "model_name": None if expired else horizon.get("model_name"),
                "supported_classes": horizon.get("supported_classes") or [],
                "unsupported_classes": horizon.get("unsupported_classes") or [],
                "evaluation_reliable": horizon.get("evaluation_reliable"),
                "applies": ml_available and not expired,
            },
            "final_risk": day_final,
            "decision_basis": basis,
            "reasons": reasons,
            "missing": {
                "official_daily_discharge": step > 1,
                "ml_model": not ml_available,
                "jammu_weather": not weather.get("available", False),
            },
            "sources": [
                {
                    "name": "FFD bulletin",
                    "url": source_url,
                },
                {
                    "name": f"FloodShield horizon {step} model",
                    "available": ml_available,
                },
                {
                    "name": "Open-Meteo Jammu 14-day forecast",
                    "role": "external_weather_indicator",
                    "url": weather.get("source_url") or OPEN_METEO_URL,
                    "available": bool(weather.get("available")),
                    "changes_flood_category": False,
                },
            ],
        }
        day["alert"] = generate_horizon_alert(day)
        days.append(day)

    return {
        "issue_date": issue_day.isoformat(),
        "timezone": "Asia/Karachi",
        "data_freshness": data_freshness,
        "ffd_weekly_outlook": ffd_outlook,
        "jammu_extended_forecast": {
            "role": "external_weather_indicator",
            "changes_flood_category": False,
            "source_name": (jammu or {}).get("source_name") or "open-meteo",
            "source_url": (jammu or {}).get("source_url") or OPEN_METEO_URL,
            "location": (jammu or {}).get("location") or {
                "name": "Jammu",
                "latitude": JAMMU_LATITUDE,
                "longitude": JAMMU_LONGITUDE,
                "timezone": "Asia/Karachi",
            },
            "available": bool((jammu or {}).get("available")),
            "error": (jammu or {}).get("error"),
            "note": (jammu or {}).get("note") or JAMMU_NOTE,
            "forecasts": list((jammu or {}).get("forecasts") or []),
        },
        "limitations": list(OUTLOOK_LIMITATIONS),
        "days": days,
    }


# ============================================================
# 12. RUN FLOODSHIELD ENGINE
# ============================================================

def run_floodshield():
    """Live next-day result plus the seven-day outlook."""

    print("=" * 72)
    print("AI FLOODSHIELD PAK — LIVE MARALA ENGINE")
    print("=" * 72)

    history = fetch_recent_marala_history(minimum_records=8)
    bulletin_html = getattr(
        fetch_recent_marala_history,
        "last_bulletin_html",
        "",
    )
    ffd_outlook = extract_ffd_outlook(bulletin_html)

    print(f"\nFFD observations loaded: {len(history)}")
    print("\nRecent Marala observations:")
    print(
        history[
            [
                "date",
                "inflow",
                "outflow",
                "forecast_24h",
                "ffd_forecast_text",
            ]
        ]
        .tail(8)
        .to_string(index=False)
    )

    feature_df = create_features(history)
    latest = feature_df.iloc[-1]
    current_risk = get_threshold_risk(latest["inflow_current"])
    forecast_risk = determine_forecast_risk(latest)

    model_package = load_floodshield_model()
    ml_prediction, ml_confidence, class_probabilities = make_ml_prediction(
        feature_df,
        model_package,
    )
    base_final = determine_final_risk(
        current_risk,
        forecast_risk,
        ml_prediction,
    )

    issue_day = pd.Timestamp(latest["date"]).date()
    day_one = issue_day + timedelta(days=1)
    day_state = forecast_day_status(issue_day, day_one, karachi_today())
    weekly_day_one, _weekly_text = official_category_for_date(
        ffd_outlook,
        day_one,
    )
    qualitative = official_category_from_text(
        latest.get("ffd_forecast_level")
    )
    computed_final = higher_risk(
        [base_final, weekly_day_one, qualitative]
    ) or base_final
    if day_state["expired"]:
        final_risk = "Insufficient data"
    else:
        final_risk = computed_final

    try:
        ml_horizons = predict_flood_risk_horizons(
            feature_df,
            MODEL_DIR,
            latest["date"],
        )
    except Exception as exc:
        print(f"\nHorizon models could not be scored: {exc}")
        ml_horizons = []

    jammu = fetch_jammu_extended_forecast()

    result = {
        "date": latest["date"].strftime("%Y-%m-%d"),
        "river": RIVER,
        "station": STATION,
        "current_inflow": float(latest["inflow_current"]),
        "current_outflow": float(latest["outflow_current"]),
        "ffd_forecast_value": as_optional_float(latest["forecast_24h"]),
        "ffd_forecast_text": latest["ffd_forecast_text"],
        "current_risk": current_risk,
        "forecast_risk": forecast_risk,
        "ml_prediction": ml_prediction,
        "ml_confidence": ml_confidence,
        "ml_probabilities": class_probabilities,
        "final_risk": final_risk,
        "computed_bulletin_risk": computed_final,
        "forecast_status": day_state["status"],
        "ffd_source": latest["source_url"],
        "published_at": latest.get("published_at"),
    }

    _qwen_runtime["blocked_reason"] = None
    qwen_status = qwen_configuration_status()
    print(
        "\nQwen configuration: "
        f"configured={qwen_status['configured']} "
        f"key_present={qwen_status['key_present']} "
        f"model={qwen_status['model']}"
    )
    locked_risk = result["final_risk"]
    alert = generate_qwen_alert(result)
    if result["final_risk"] != locked_risk:
        raise RuntimeError("Qwen path changed the decided flood category.")
    result["alert"] = alert
    result["data_freshness"] = None
    result["seven_day_outlook"] = build_seven_day_outlook(
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
        jammu=jammu,
        ffd_outlook=ffd_outlook,
        final_risk=final_risk,
        current_inflow=latest["inflow_current"],
        current_outflow=latest["outflow_current"],
        source_url=latest["source_url"],
    )
    result["data_freshness"] = result["seven_day_outlook"]["data_freshness"]

    print("\n" + "=" * 72)
    print("FLOODSHIELD RESULT")
    print("=" * 72)
    print("\nDate             :", result["date"])
    print("River            :", result["river"])
    print("Station          :", result["station"])
    print(
        "Current inflow   :",
        result["current_inflow"],
        "thousand cusecs",
    )
    print(
        "Current outflow  :",
        result["current_outflow"],
        "thousand cusecs",
    )
    print(
        "FFD 24h forecast :",
        result["ffd_forecast_text"],
        "thousand cusecs",
    )
    print("\nCurrent danger   :", result["current_risk"])
    print("FFD forecast risk:", result["forecast_risk"])
    print("ML next-day risk :", result["ml_prediction"])
    if result["ml_confidence"] is not None:
        print(
            "ML confidence*   :",
            f"{result['ml_confidence'] * 100:.1f}%",
        )
        print(
            "*Classifier confidence, "
            "not a guaranteed flood probability."
        )
    print("\nFINAL ALERT LEVEL:", result["final_risk"])
    print("\nData freshness   :", result["data_freshness"]["note"])

    print("\n" + "-" * 72)
    print("ENGLISH ALERT")
    print("-" * 72)
    print(alert["english"])
    print("\n" + "-" * 72)
    print("URDU ALERT")
    print("-" * 72)
    print(alert["urdu"])
    print("\nAlert generated by:", alert["generated_by"])
    print("Alert source       :", alert.get("alert_source"))
    print("Qwen status        :", alert.get("qwen_status"))
    print("Forecast status    :", result.get("forecast_status"))
    print("\nFFD source:", result["ffd_source"])

    print("\n" + "=" * 72)
    print("SEVEN-DAY OUTLOOK")
    print("=" * 72)
    for day in result["seven_day_outlook"]["days"]:
        print(
            f"  +{day['horizon_days']} {day['forecast_date']}  "
            f"final={day['final_risk']}  "
            f"basis={day['decision_basis']}  "
            f"official={day['official_ffd']['category']}  "
            f"ml={day['ml_prediction']['category']}"
        )

    print("\nLimitations:")
    for item in OUTLOOK_LIMITATIONS:
        print(" -", item)

    print("\n" + "=" * 72)
    print("FLOODSHIELD ENGINE COMPLETE")
    print("=" * 72)
    return result


# ============================================================
# 13. PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        floodshield_result = run_floodshield()
        print("\nSEVEN-DAY JSON")
        print(
            json.dumps(
                json_ready(floodshield_result["seven_day_outlook"]),
                ensure_ascii=False,
                indent=2,
            )
        )
    except requests.RequestException as exc:
        print("\nERROR: Could not connect to FFD website.")
        print(exc)
    except Exception as exc:
        print("\nFLOODSHIELD ERROR:")
        print(exc)
