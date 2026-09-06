# ============================================================
# AI FLOODSHIELD PAK
# FloodShield Live Decision Engine
#
# River   : Chenab
# Station : Marala
#
# What this program does:
#
#   FFD website
#       ↓
#   Latest + recent Marala observations
#       ↓
#   Current official danger
#       +
#   FFD 24-hour forecast risk
#       +
#   Random Forest next-day prediction
#       ↓
#   Final FloodShield risk
#       ↓
#   English + Urdu alert
#
# IMPORTANT:
# Qwen NEVER decides the flood level.
# Qwen is used only to convert the already-computed result
# into easy-to-understand English and Urdu.
# ============================================================

import os
import re
import json
import warnings
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
ML_DIR = REPO_ROOT / "ml"

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")

import joblib
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")


# ============================================================
# 1. CONFIGURATION
# ============================================================

HISTORY_FILE = str(
    ML_DIR / "data" / "processed" / "chenab_marala_dataset.csv"
)
FFD_BASE_URL = "https://ffd.pmd.gov.pk"
FFD_BULLETIN_URL = "https://ffd.pmd.gov.pk/bulletin"

MODEL_FILE = str(ML_DIR / "models" / "floodshield_marala_model.pkl")

RIVER = "CHENAB"
STATION = "MARALA"

# Flood thresholds in thousands of cusecs
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
    "Exceptional"
]

SEVERITY = {
    "Normal": 0,
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Very High": 4,
    "Exceptional": 5
}


# ============================================================
# 2. WEB REQUEST SETTINGS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 30


# ============================================================
# 3. BASIC UTILITY FUNCTIONS
# ============================================================

def extract_first_number(value):
    """
    Extract first numerical value from text.

    Examples:
        '60.0'       -> 60.0
        '60 - 90'    -> 60.0
        '60 R 90'    -> 60.0
        'No change'  -> NaN

    This matches the cleaning approach used in the
    ML training script.
    """

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
    """
    Standardize text for case-insensitive matching.
    """

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


# ============================================================
# 4. FLOOD-RISK THRESHOLD FUNCTION
# ============================================================

def get_threshold_risk(inflow):
    """
    Determine flood category using Marala flood thresholds.

    Input:
        inflow in thousands of cusecs
    """

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


# ============================================================
# 5. FORECAST-RANGE HELPER
# ============================================================

def extract_forecast_range(text):
    """
    Extract lower and upper values from an FFD forecast.

    Examples:
        '60 - 90'  -> (60, 90)
        '290 R 350' -> (290, 350)
        '150'       -> (150, 150)

    If FFD says 'No sig. change', numerical forecast
    may not be available.
    """

    if text is None:
        return np.nan, np.nan

    numbers = re.findall(
        r"[-+]?\d*\.?\d+",
        str(text).replace(",", "")
    )

    numbers = [
        float(x)
        for x in numbers
        if x.strip()
    ]

    if len(numbers) >= 2:
        return numbers[0], numbers[-1]

    if len(numbers) == 1:
        return numbers[0], numbers[0]

    return np.nan, np.nan


# ============================================================
# 6. DOWNLOAD A WEB PAGE
# ============================================================

def download_page(url):
    """
    Download an FFD webpage.
    """

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return response.text


# ============================================================
# 7. FIND BULLETIN DATE
# ============================================================

def extract_bulletin_date(html):
    """
    Try to determine the bulletin date from the webpage.
    """

    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text(" ", strip=True)


    # Examples:
    # DAILY FLOOD BULLETIN 31-AUG-2026
    pattern1 = re.search(
        r"DAILY\s+FLOOD\s+BULLETIN\s+"
        r"(\d{1,2})[-\s]"
        r"([A-Za-z]{3,9})[-\s]"
        r"(\d{4})",
        text,
        re.IGNORECASE
    )

    if pattern1:

        date_text = (
            f"{pattern1.group(1)} "
            f"{pattern1.group(2)} "
            f"{pattern1.group(3)}"
        )

        return pd.to_datetime(
            date_text,
            errors="coerce"
        )


    # Fallback:
    # Dated: 31st August-2026
    pattern2 = re.search(
        r"Dated:\s*"
        r"(\d{1,2})(?:st|nd|rd|th)?\s*"
        r"([A-Za-z]+)[-\s]"
        r"(\d{4})",
        text,
        re.IGNORECASE
    )

    if pattern2:

        date_text = (
            f"{pattern2.group(1)} "
            f"{pattern2.group(2)} "
            f"{pattern2.group(3)}"
        )

        return pd.to_datetime(
            date_text,
            errors="coerce"
        )


    return pd.NaT


# ============================================================
# 8. EXTRACT MARALA ROW FROM BULLETIN
# ============================================================

def extract_marala_from_html(html, source_url):
    """
    Find the CHENAB / Marala row in the FFD quantitative
    flood forecast table.

    Expected row structure on FFD:

    River
    Station
    Inflow
    Outflow
    24-hour forecast
    Forecast flood level
    Historical max
    Historical max year/type
    Flood-season max

    Returns one dictionary.
    """

    soup = BeautifulSoup(html, "html.parser")

    bulletin_date = extract_bulletin_date(html)


    # --------------------------------------------------------
    # Search normal HTML table rows
    # --------------------------------------------------------

    for row in soup.find_all("tr"):

        cells = [
            normalize_text(cell.get_text(" ", strip=True))
            for cell in row.find_all(["td", "th"])
        ]

        if len(cells) < 5:
            continue

        joined = " | ".join(cells).upper()

        if (
            "CHENAB" in joined
            and "MARALA" in joined
        ):

            # Usually:
            # 0 river
            # 1 station
            # 2 inflow
            # 3 outflow
            # 4 24h forecast
            # 5 qualitative level

            river_index = next(
                (
                    i for i, x in enumerate(cells)
                    if "CHENAB" in x.upper()
                ),
                None
            )

            station_index = next(
                (
                    i for i, x in enumerate(cells)
                    if "MARALA" in x.upper()
                ),
                None
            )

            if (
                station_index is None
                or len(cells) <= station_index + 3
            ):
                continue


            inflow_text = cells[station_index + 1]
            outflow_text = cells[station_index + 2]
            forecast_text = cells[station_index + 3]

            forecast_level = ""

            if len(cells) > station_index + 4:
                forecast_level = cells[station_index + 4]


            inflow = extract_first_number(
                inflow_text
            )

            outflow = extract_first_number(
                outflow_text
            )

            # Training script used first numerical forecast
            forecast_24h = extract_first_number(
                forecast_text
            )

            forecast_low, forecast_high = (
                extract_forecast_range(
                    forecast_text
                )
            )


            return {
                "date": bulletin_date,
                "river": RIVER,
                "station": STATION,

                "inflow": inflow,
                "outflow": outflow,

                "forecast_24h": forecast_24h,

                "forecast_low": forecast_low,
                "forecast_high": forecast_high,

                "ffd_forecast_text":
                    forecast_text,

                "ffd_forecast_level":
                    forecast_level,

                "source_url":
                    source_url
            }


    # --------------------------------------------------------
    # Fallback:
    # pandas can sometimes interpret tables that BeautifulSoup
    # does not expose in an obvious structure.
    # --------------------------------------------------------

    try:

        tables = pd.read_html(
            StringIO(html)
        )

        for table in tables:

            table_text = table.astype(str)

            contains_marala = (
                table_text
                .apply(
                    lambda column:
                    column.str.contains(
                        "Marala",
                        case=False,
                        na=False
                    )
                )
                .any()
                .any()
            )

            if not contains_marala:
                continue

            for _, row in table.iterrows():

                row_values = [
                    normalize_text(v)
                    for v in row.tolist()
                ]

                joined = " | ".join(
                    row_values
                ).upper()

                if (
                    "MARALA" not in joined
                    or "CHENAB" not in joined
                ):
                    continue

                # Find Marala position
                station_index = next(
                    (
                        i for i, x in
                        enumerate(row_values)
                        if "MARALA" in x.upper()
                    ),
                    None
                )

                if station_index is None:
                    continue

                remaining = (
                    row_values[
                        station_index + 1:
                    ]
                )

                if len(remaining) < 3:
                    continue

                inflow = extract_first_number(
                    remaining[0]
                )

                outflow = extract_first_number(
                    remaining[1]
                )

                forecast_text = remaining[2]

                forecast_24h = (
                    extract_first_number(
                        forecast_text
                    )
                )

                forecast_low, forecast_high = (
                    extract_forecast_range(
                        forecast_text
                    )
                )

                forecast_level = (
                    remaining[3]
                    if len(remaining) >= 4
                    else ""
                )

                return {
                    "date": bulletin_date,
                    "river": RIVER,
                    "station": STATION,

                    "inflow": inflow,
                    "outflow": outflow,

                    "forecast_24h":
                        forecast_24h,

                    "forecast_low":
                        forecast_low,

                    "forecast_high":
                        forecast_high,

                    "ffd_forecast_text":
                        forecast_text,

                    "ffd_forecast_level":
                        forecast_level,

                    "source_url":
                        source_url
                }

    except Exception:
        pass


    raise ValueError(
        "Could not find Chenab / Marala data "
        f"in bulletin: {source_url}"
    )


# ============================================================
# 9. FIND RECENT BULLETIN LINKS
# ============================================================

def find_recent_bulletin_links(html, current_url, max_links=15):
    """
    Find recent FFD bulletin PDF/page links from publication history.

    FFD's publication history currently exposes recent bulletin
    entries mainly through their PDF links, not through /b/... URLs.
    """

    soup = BeautifulSoup(html, "html.parser")

    links = []

    for a in soup.find_all("a", href=True):

        href = a.get("href", "").strip()
        text = normalize_text(
            a.get_text(" ", strip=True)
        ).lower()

        absolute_url = urljoin(
            FFD_BASE_URL,
            href
        )

        # Accept bulletin PDFs or bulletin pages
        is_pdf = ".pdf" in absolute_url.lower()
        is_bulletin_page = "/b/" in absolute_url.lower()

        if not (is_pdf or is_bulletin_page):
            continue

        # Skip duplicate/current links
        if absolute_url == current_url:
            continue

        if absolute_url in links:
            continue

        links.append(absolute_url)

        if len(links) >= max_links:
            break

    return links


# ============================================================
# 10. LOAD RECENT FFD MARALA HISTORY
# ============================================================

def load_recent_history_from_csv(
    live_date,
    minimum_records=8
):
    """
    Load recent Marala observations from the already-built CSV.

    Only observations BEFORE the current live FFD bulletin date
    are used.

    This avoids repeatedly downloading/parsing historical PDFs.
    """

    if not os.path.exists(HISTORY_FILE):
        raise FileNotFoundError(
            f"{HISTORY_FILE} was not found."
        )

    df = pd.read_csv(HISTORY_FILE)

    # Normalize column names
    df.columns = [
        re.sub(
            r"[^a-z0-9]+",
            "_",
            str(c).strip().lower()
        ).strip("_")
        for c in df.columns
    ]


    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    required = [
        "date",
        "inflow_thousands_cusecs",
        "outflow_thousands_cusecs"
    ]

    for column in required:
        if column not in df.columns:
            raise ValueError(
                f"Missing required CSV column: {column}"
            )


    # --------------------------------------------------------
    # Optional river/station filtering
    # --------------------------------------------------------

    if "river" in df.columns:

        df = df[
            df["river"]
            .astype(str)
            .str.strip()
            .str.lower()
            == "chenab"
        ]


    if "station" in df.columns:

        df = df[
            df["station"]
            .astype(str)
            .str.strip()
            .str.lower()
            == "marala"
        ]


    # --------------------------------------------------------
    # Date
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
        dayfirst=True
    )


    df = df.dropna(
        subset=["date"]
    )


    # Only use data BEFORE today's bulletin
    df = df[
        df["date"] < live_date
    ].copy()


    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    df["inflow"] = pd.to_numeric(
        df["inflow_thousands_cusecs"],
        errors="coerce"
    )

    df["outflow"] = pd.to_numeric(
        df["outflow_thousands_cusecs"],
        errors="coerce"
    )


    # Forecast column
    if "forecast_24h_inflow" in df.columns:

        df["forecast_24h"] = pd.to_numeric(
            df["forecast_24h_inflow"],
            errors="coerce"
        )

    else:

        df["forecast_24h"] = np.nan


    # Fields expected by live engine
    df["forecast_low"] = df["forecast_24h"]
    df["forecast_high"] = df["forecast_24h"]

    df["ffd_forecast_text"] = (
        df["forecast_24h"]
        .astype(str)
    )

    df["ffd_forecast_level"] = ""

    df["source_url"] = "historical CSV"


    # --------------------------------------------------------
    # Keep latest observations
    # --------------------------------------------------------

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
                "source_url"
            ]
        ]
        .dropna(
            subset=[
                "date",
                "inflow"
            ]
        )
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
    )


    # Get slightly more than 7 for safety
    df = df.tail(
        max(minimum_records, 10)
    ).copy()


    if len(df) < 7:

        raise RuntimeError(
            f"Only {len(df)} historical records "
            "were available before the live bulletin."
        )


    return df


def fetch_recent_marala_history(
    minimum_records=8
):
    """
    Get:
      1. latest Marala observation from live FFD website
      2. previous observations from local historical CSV

    Nothing new is permanently stored.
    """

    print(
        "\nConnecting to FFD website..."
    )


    # --------------------------------------------------------
    # Latest LIVE bulletin
    # --------------------------------------------------------

    latest_html = download_page(
        FFD_BULLETIN_URL
    )


    latest_record = (
        extract_marala_from_html(
            latest_html,
            FFD_BULLETIN_URL
        )
    )


    print(
        "Latest Marala bulletin extracted."
    )


    live_date = pd.to_datetime(
        latest_record["date"]
    )


    if pd.isna(live_date):

        raise RuntimeError(
            "Could not determine latest FFD bulletin date."
        )


    # --------------------------------------------------------
    # Historical feature data from CSV
    # --------------------------------------------------------

    historical = (
        load_recent_history_from_csv(
            live_date,
            minimum_records=minimum_records
        )
    )


    print(
        f"Historical records loaded from CSV: "
        f"{len(historical)}"
    )


    # --------------------------------------------------------
    # Append today's live observation
    # --------------------------------------------------------

    latest_df = pd.DataFrame(
        [latest_record]
    )


    history = pd.concat(
        [
            historical,
            latest_df
        ],
        ignore_index=True
    )


    history["date"] = pd.to_datetime(
        history["date"],
        errors="coerce"
    )


    history = (
        history
        .dropna(
            subset=[
                "date",
                "inflow"
            ]
        )
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
        .reset_index(drop=True)
    )


    print(
        f"Total observations available to ML: "
        f"{len(history)}"
    )

    # Check age of previous observation
    if len(history) >= 2:

         previous_date = history.iloc[-2]["date"]
         latest_date = history.iloc[-1]["date"]

    gap_days = (
         latest_date - previous_date
    ).days

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


# ============================================================
# 11. CREATE ML FEATURES
# ============================================================

def create_features(history):
    """
    Recreate the SAME features used when training
    floodshield_marala_model.pkl.

    Very important:
    feature engineering in training and live prediction
    must remain consistent.
    """

    df = history.copy()

    df = df.sort_values(
        "date"
    ).reset_index(drop=True)


    # --------------------------------------------------------
    # Basic date features
    # --------------------------------------------------------

    df["year"] = df["date"].dt.year

    df["month"] = (
        df["date"].dt.month
    )

    df["day"] = (
        df["date"].dt.day
    )

    df["day_of_year"] = (
        df["date"].dt.dayofyear
    )

    df["day_of_week"] = (
        df["date"].dt.dayofweek
    )

    df["flood_season"] = (
        df["month"]
        .isin([6, 7, 8, 9])
        .astype(int)
    )


    # --------------------------------------------------------
    # Cyclical date features
    # --------------------------------------------------------

    df["month_sin"] = np.sin(
        2 * np.pi *
        df["month"] / 12
    )

    df["month_cos"] = np.cos(
        2 * np.pi *
        df["month"] / 12
    )

    df["doy_sin"] = np.sin(
        2 * np.pi *
        df["day_of_year"] / 365.25
    )

    df["doy_cos"] = np.cos(
        2 * np.pi *
        df["day_of_year"] / 365.25
    )


    # --------------------------------------------------------
    # Current hydrological values
    # --------------------------------------------------------

    df["inflow_current"] = (
        df["inflow"]
    )

    df["outflow_current"] = (
        df["outflow"]
    )

    df["forecast_24h"] = (
        df["forecast_24h"]
    )


    # --------------------------------------------------------
    # Capacity features
    # --------------------------------------------------------

    df["capacity_utilization"] = (
        df["inflow_current"] /
        DESIGN_CAPACITY
    )

    df["distance_from_low_flood"] = (
        df["inflow_current"] -
        LOW_FLOOD
    )


    # --------------------------------------------------------
    # Previous-observation lags
    # --------------------------------------------------------

    df["inflow_lag_1"] = (
        df["inflow_current"]
        .shift(1)
    )

    df["inflow_lag_2"] = (
        df["inflow_current"]
        .shift(2)
    )

    df["inflow_lag_3"] = (
        df["inflow_current"]
        .shift(3)
    )

    df["inflow_lag_7"] = (
        df["inflow_current"]
        .shift(7)
    )


    df["outflow_lag_1"] = (
        df["outflow_current"]
        .shift(1)
    )

    df["outflow_lag_3"] = (
        df["outflow_current"]
        .shift(3)
    )


    # --------------------------------------------------------
    # Flow changes
    # --------------------------------------------------------

    df["inflow_change_1"] = (
        df["inflow_current"] -
        df["inflow_lag_1"]
    )

    df["inflow_change_3"] = (
        df["inflow_current"] -
        df["inflow_lag_3"]
    )

    df["inflow_change_7"] = (
        df["inflow_current"] -
        df["inflow_lag_7"]
    )


    df["inflow_pct_change_1"] = (
        df["inflow_change_1"] /
        df["inflow_lag_1"]
        .replace(0, np.nan)
    )

    df["inflow_pct_change_3"] = (
        df["inflow_change_3"] /
        df["inflow_lag_3"]
        .replace(0, np.nan)
    )


    # --------------------------------------------------------
    # Past rolling features
    #
    # shift(1) prevents today's value being included in
    # historical rolling calculations.
    # --------------------------------------------------------

    past_inflow = (
        df["inflow_current"]
        .shift(1)
    )


    df["inflow_mean_3d"] = (
        past_inflow
        .rolling(
            window=3,
            min_periods=1
        )
        .mean()
    )

    df["inflow_mean_7d"] = (
        past_inflow
        .rolling(
            window=7,
            min_periods=1
        )
        .mean()
    )


    df["inflow_max_3d"] = (
        past_inflow
        .rolling(
            window=3,
            min_periods=1
        )
        .max()
    )

    df["inflow_max_7d"] = (
        past_inflow
        .rolling(
            window=7,
            min_periods=1
        )
        .max()
    )


    df["inflow_std_3d"] = (
        past_inflow
        .rolling(
            window=3,
            min_periods=2
        )
        .std()
    )

    df["inflow_std_7d"] = (
        past_inflow
        .rolling(
            window=7,
            min_periods=2
        )
        .std()
    )


    df["inflow_vs_3d_mean"] = (
        df["inflow_current"] -
        df["inflow_mean_3d"]
    )

    df["inflow_vs_7d_mean"] = (
        df["inflow_current"] -
        df["inflow_mean_7d"]
    )


    # --------------------------------------------------------
    # Inflow vs outflow
    # --------------------------------------------------------

    df["inflow_outflow_difference"] = (
        df["inflow_current"] -
        df["outflow_current"]
    )

    df["inflow_outflow_ratio"] = (
        df["inflow_current"] /
        df["outflow_current"]
        .replace(0, np.nan)
    )


    # --------------------------------------------------------
    # FFD forecast features
    # --------------------------------------------------------

    df["forecast_change"] = (
        df["forecast_24h"] -
        df["inflow_current"]
    )

    df["forecast_change_pct"] = (
        df["forecast_change"] /
        df["inflow_current"]
        .replace(0, np.nan)
    )

    df["forecast_low_margin"] = (
        df["forecast_24h"] -
        LOW_FLOOD
    )

    df["forecast_high_margin"] = (
        df["forecast_24h"] -
        HIGH_FLOOD
    )


    # Numerical forecast risk
    df["forecast_risk_numeric"] = (
        pd.cut(
            df["forecast_24h"],
            bins=[
                -np.inf,
                LOW_FLOOD,
                MEDIUM_FLOOD,
                HIGH_FLOOD,
                VERY_HIGH_FLOOD,
                EXCEPTIONAL_FLOOD,
                np.inf
            ],
            labels=[
                0,
                1,
                2,
                3,
                4,
                5
            ],
            right=False
        )
        .astype(float)
    )


    return df


# ============================================================
# 12. LOAD TRAINED MODEL
# ============================================================

def load_floodshield_model():
    """
    Load model package produced by flood_risk_mlmodel.py
    """

    if not os.path.exists(
        MODEL_FILE
    ):

        raise FileNotFoundError(
            f"{MODEL_FILE} was not found."
        )


    package = joblib.load(
        MODEL_FILE
    )


    required_keys = [
        "model",
        "features"
    ]

    for key in required_keys:

        if key not in package:

            raise KeyError(
                f"'{key}' missing from "
                "saved model package."
            )


    return package


# ============================================================
# 13. ML NEXT-DAY PREDICTION
# ============================================================

def make_ml_prediction(
    feature_df,
    model_package
):
    """
    Predict next-day flood-risk class.
    """

    model = (
        model_package["model"]
    )

    required_features = (
        model_package["features"]
    )


    latest = feature_df.iloc[-1:].copy()


    # --------------------------------------------------------
    # Make sure every training feature exists
    # --------------------------------------------------------

    missing = [
        feature
        for feature in required_features
        if feature not in latest.columns
    ]

    if missing:

        raise ValueError(
            "Live feature engineering is missing:\n"
            + "\n".join(missing)
        )


    X_live = latest[
        required_features
    ].copy()


    prediction = (
        model.predict(X_live)[0]
    )


    confidence = None

    class_probabilities = {}


    if hasattr(
        model,
        "predict_proba"
    ):

        probabilities = (
            model.predict_proba(X_live)[0]
        )

        classes = (
            model.classes_
        )

        class_probabilities = {
            str(cls): float(prob)
            for cls, prob
            in zip(
                classes,
                probabilities
            )
        }

        confidence = float(
            np.max(probabilities)
        )


    return (
        prediction,
        confidence,
        class_probabilities
    )


# ============================================================
# 14. FFD FORECAST RISK
# ============================================================

def determine_forecast_risk(
    latest_row
):
    """
    Determine the conservative risk implied by FFD's
    24-hour numerical forecast.

    For a range such as 60-90:
        high end = 90

    For 130-170:
        high end = 170 -> Medium risk

    We use the upper end for public-safety alerting.
    """

    forecast_high = (
        latest_row.get(
            "forecast_high",
            np.nan
        )
    )


    if pd.isna(forecast_high):

        # Fallback to value used by ML model
        forecast_high = (
            latest_row.get(
                "forecast_24h",
                np.nan
            )
        )


    return (
        get_threshold_risk(
            forecast_high
        )
    )


# ============================================================
# 15. FINAL FLOODSHIELD RISK
# ============================================================

def determine_final_risk(
    current_risk,
    forecast_risk,
    ml_risk
):
    """
    Hybrid FloodShield rule.

    Current official threshold condition must never
    be downgraded by ML.

    Final risk = highest credible signal among:
       1. Current river condition
       2. FFD 24-hour forecast
       3. ML next-day prediction

    Unknown values are ignored.
    """

    risks = [
        current_risk,
        forecast_risk,
        ml_risk
    ]

    valid_risks = [
        risk
        for risk in risks
        if risk in SEVERITY
    ]


    if not valid_risks:
        return "Unknown"


    return max(
        valid_risks,
        key=lambda x:
        SEVERITY[x]
    )


# ============================================================
# 16. ALERT TYPE / ACTION
# ============================================================

def get_alert_action(risk):
    """
    Simple public-safety action guidance.

    These are intentionally conservative and generic.
    Official government instructions always take priority.
    """

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
        )
    }


    return actions.get(
        risk,
        "Monitor official FFD and disaster-management updates."
    )


# ============================================================
# 17. BUILT-IN ALERT FALLBACK
# ============================================================

def create_template_alert(result):
    """
    Generate alerts without Qwen.

    This makes the FloodShield Engine continue working if:
      - Qwen API key is missing
      - internet to Alibaba fails
      - free quota is exhausted
    """

    risk = result["final_risk"]

    inflow = result["current_inflow"]

    forecast_text = (
        result["ffd_forecast_text"]
    )

    ml_risk = (
        result["ml_prediction"]
    )


    english = (
        f"FloodShield Alert — Chenab River at Marala\n\n"
        f"Current inflow: {inflow:.1f} thousand cusecs.\n"
        f"FFD 24-hour forecast: {forecast_text} thousand cusecs.\n"
        f"ML next-day prediction: {ml_risk}.\n"
        f"Final alert level: {risk}.\n\n"
        f"{get_alert_action(risk)}\n\n"
        f"Source: Pakistan Meteorological Department, "
        f"Flood Forecasting Division (FFD)."
    )


    # Simple fixed Urdu fallback.
    # Qwen can produce smoother Urdu when available.

    urdu_actions = {

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
            "حفاظتی ہدایات پر عمل کریں۔"
    }


    urdu = (
        f"فلڈ شیلڈ الرٹ — دریائے چناب، مرالہ\n\n"
        f"موجودہ پانی کا بہاؤ: {inflow:.1f} ہزار کیوسک\n"
        f"FFD کی اگلے 24 گھنٹوں کی پیش گوئی: "
        f"{forecast_text} ہزار کیوسک\n"
        f"مشین لرننگ کی اگلے دن کی پیش گوئی: {ml_risk}\n"
        f"حتمی الرٹ لیول: {risk}\n\n"
        f"{urdu_actions.get(risk, 'سرکاری اطلاعات پر نظر رکھیں۔')}"
    )


    return {
        "english": english,
        "urdu": urdu,
        "generated_by": "FloodShield templates"
    }


# ============================================================
# 18. OPTIONAL QWEN ALERT GENERATION
# ============================================================

def generate_qwen_alert(result):
    """
    Use Qwen ONLY for clear English + Urdu wording.

    The numerical results and risk category have ALREADY
    been calculated by FloodShield.

    Required environment variables:

        DASHSCOPE_API_KEY
        DASHSCOPE_BASE_URL

    Example model:
        qwen-turbo

    If Qwen fails, the program automatically falls back
    to deterministic templates.
    """

    api_key = os.getenv(
        "DASHSCOPE_API_KEY"
    )

    base_url = os.getenv(
        "DASHSCOPE_BASE_URL"
    )


    # --------------------------------------------------------
    # No API configured -> fallback
    # --------------------------------------------------------

    if not api_key or not base_url:

        print(
            "\nQwen API not configured. "
            "Using built-in bilingual templates."
        )

        return create_template_alert(
            result
        )


    try:

        from openai import OpenAI


        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )


        # IMPORTANT:
        # We give Qwen the final risk.
        # We explicitly forbid Qwen from changing it.

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


        response = (
            client.chat.completions.create(
                model="qwen-flash", #or qwen-turbo

                messages=[
                    {
                        "role": "system",
                        "content":
                            "You write concise bilingual "
                            "public safety alerts. Never "
                            "change provided risk levels."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],

                temperature=0.2
            )
        )


        content = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )


        # Remove accidental Markdown fences
        content = re.sub(
            r"^```(?:json)?\s*",
            "",
            content,
            flags=re.IGNORECASE
        )

        content = re.sub(
            r"\s*```$",
            "",
            content
        )


        alert = json.loads(
            content
        )


        return {
            "english":
                alert["english"],

            "urdu":
                alert["urdu"],

            "generated_by":
                "Qwen"
        }


    except Exception as e:

        print(
            "\nWARNING: Qwen alert generation failed:"
        )

        print(e)

        print(
            "Using built-in alert templates instead."
        )


        return create_template_alert(
            result
        )


# ============================================================
# 19. RUN FLOODSHIELD ENGINE
# ============================================================

def run_floodshield():
    """
    Main FloodShield workflow.
    """

    print("=" * 72)
    print(
        "AI FLOODSHIELD PAK — LIVE MARALA ENGINE"
    )
    print("=" * 72)


    # --------------------------------------------------------
    # STEP A:
    # Get recent FFD information
    # --------------------------------------------------------

    history = (
        fetch_recent_marala_history(
            minimum_records=8
        )
    )


    print(
        f"\nFFD observations loaded: "
        f"{len(history)}"
    )


    print(
        "\nRecent Marala observations:"
    )

    print(
        history[
            [
                "date",
                "inflow",
                "outflow",
                "forecast_24h",
                "ffd_forecast_text"
            ]
        ]
        .tail(8)
        .to_string(index=False)
    )


    # --------------------------------------------------------
    # STEP B:
    # Feature engineering
    # --------------------------------------------------------

    feature_df = (
        create_features(
            history
        )
    )


    latest = (
        feature_df.iloc[-1]
    )


    # --------------------------------------------------------
    # STEP C:
    # Current danger
    # --------------------------------------------------------

    current_risk = (
        get_threshold_risk(
            latest["inflow_current"]
        )
    )


    # --------------------------------------------------------
    # STEP D:
    # FFD 24-hour forecast danger
    # --------------------------------------------------------

    forecast_risk = (
        determine_forecast_risk(
            latest
        )
    )


    # --------------------------------------------------------
    # STEP E:
    # Load ML model
    # --------------------------------------------------------

    model_package = (
        load_floodshield_model()
    )


    # --------------------------------------------------------
    # STEP F:
    # Next-day ML risk
    # --------------------------------------------------------

    (
        ml_prediction,
        ml_confidence,
        class_probabilities

    ) = make_ml_prediction(
        feature_df,
        model_package
    )


    # --------------------------------------------------------
    # STEP G:
    # Final hybrid alert
    # --------------------------------------------------------

    final_risk = (
        determine_final_risk(
            current_risk,
            forecast_risk,
            ml_prediction
        )
    )


    result = {

        "date":
            latest["date"].strftime(
                "%Y-%m-%d"
            ),

        "river":
            RIVER,

        "station":
            STATION,

        "current_inflow":
            float(
                latest[
                    "inflow_current"
                ]
            ),

        "current_outflow":
            float(
                latest[
                    "outflow_current"
                ]
            ),

        "ffd_forecast_value":
            (
                None
                if pd.isna(
                    latest[
                        "forecast_24h"
                    ]
                )
                else float(
                    latest[
                        "forecast_24h"
                    ]
                )
            ),

        "ffd_forecast_text":
            latest[
                "ffd_forecast_text"
            ],

        "current_risk":
            current_risk,

        "forecast_risk":
            forecast_risk,

        "ml_prediction":
            ml_prediction,

        "ml_confidence":
            ml_confidence,

        "ml_probabilities":
            class_probabilities,

        "final_risk":
            final_risk,

        "ffd_source":
            latest[
                "source_url"
            ]
    }


    # --------------------------------------------------------
    # STEP H:
    # Generate bilingual public alert
    # --------------------------------------------------------

    alert = (
        generate_qwen_alert(
            result
        )
    )


    result["alert"] = alert


    # --------------------------------------------------------
    # DISPLAY FINAL RESULT
    # --------------------------------------------------------

    print(
        "\n" + "=" * 72
    )

    print(
        "FLOODSHIELD RESULT"
    )

    print(
        "=" * 72
    )


    print(
        "\nDate             :",
        result["date"]
    )

    print(
        "River            :",
        result["river"]
    )

    print(
        "Station          :",
        result["station"]
    )

    print(
        "Current inflow   :",
        result["current_inflow"],
        "thousand cusecs"
    )

    print(
        "Current outflow  :",
        result["current_outflow"],
        "thousand cusecs"
    )

    print(
        "FFD 24h forecast :",
        result[
            "ffd_forecast_text"
        ],
        "thousand cusecs"
    )


    print(
        "\nCurrent danger   :",
        result["current_risk"]
    )

    print(
        "FFD forecast risk:",
        result["forecast_risk"]
    )

    print(
        "ML next-day risk :",
        result["ml_prediction"]
    )


    if (
        result[
            "ml_confidence"
        ]
        is not None
    ):

        print(
            "ML confidence*   :",
            f"{result['ml_confidence'] * 100:.1f}%"
        )

        print(
            "*Classifier confidence, "
            "not a guaranteed flood probability."
        )


    print(
        "\nFINAL ALERT LEVEL:",
        result["final_risk"]
    )


    print(
        "\n" + "-" * 72
    )

    print(
        "ENGLISH ALERT"
    )

    print(
        "-" * 72
    )

    print(
        alert["english"]
    )


    print(
        "\n" + "-" * 72
    )

    print(
        "URDU ALERT"
    )

    print(
        "-" * 72
    )

    print(
        alert["urdu"]
    )


    print(
        "\nAlert generated by:",
        alert["generated_by"]
    )


    print(
        "\nFFD source:",
        result["ffd_source"]
    )


    print(
        "\n" + "=" * 72
    )

    print(
        "FLOODSHIELD ENGINE COMPLETE"
    )

    print(
        "=" * 72
    )


    return result


# ============================================================
# 20. PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        floodshield_result = (
            run_floodshield()
        )

    except requests.RequestException as e:

        print(
            "\nERROR: Could not connect to FFD website."
        )

        print(e)


    except Exception as e:

        print(
            "\nFLOODSHIELD ERROR:"
        )

        print(e)