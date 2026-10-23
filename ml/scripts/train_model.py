# ============================================================
# AI FLOODSHIELD PAK
# Flood Risk ML Model - Chenab River at Marala
#
# Training data : 2024 + 2025
# Testing data  : 2026  (untouched until the final test)
#
# Targets:
# A separate classifier for each calendar horizon,
# Day +1 through Day +7. The label is the flood category
# of Marala inflow on issue_date + horizon days.
# Features are only those known on the issue day.
#
# Horizon 1 is also saved as floodshield_marala_model.pkl
# so the existing next-day engine can still load it.
# ============================================================

import os
import re
import shutil
import warnings
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore")


# ============================================================
# 1. CONFIGURATION
# ============================================================

# ml/scripts/train_model.py → ML_DIR is ml/
ML_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = ML_DIR
OUTPUT_DIR = ML_DIR / "outputs"

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

HORIZONS = (1, 2, 3, 4, 5, 6, 7)
MODEL_VERSION = "floodshield-marala-7day-2"
RANDOM_STATE = 42
# A class with fewer than two issue-day examples cannot be learned.
# Those labels stay in the test set. They are removed from training only.
MIN_CLASS_EXAMPLES = 2
MIN_TRAIN_ROWS = 40
MIN_TRAIN_CLASSES = 2

ISSUE_TIME_FEATURE_RULE = (
    "Features are computed only from information known on the "
    "issue day: observed inflow and outflow, lags and rolling "
    "history of those observations, seasonality, and the FFD "
    "24-hour inflow forecast published on that day. The 24-hour "
    "forecast is a same-day input, not a seven-day discharge "
    "forecast. The target is the flood category of inflow on "
    "the calendar date issue_date + horizon days. No future "
    "inflow, future label, or Jammu weather is used."
)

HYDROLOGICAL_LIMITATIONS = [
    "Historical inflow labels are mostly Normal. Very High has "
    "no examples in this dataset, so it cannot be learned and no "
    "score is reported for it.",
    "A class with fewer than two training examples is unsupported. "
    "The single Exceptional day is not treated as a learned class.",
    "Accuracy is high because almost every day is Normal. Model "
    "selection uses macro-F1 and minority-class recall. Accuracy "
    "is reported and is not the selection rule.",
    "The 2026 test window contains almost no minority-class days, "
    "so a reliable seven-day estimate of flood recall is not "
    "possible from this split.",
    "The record is monsoon-only (June-October). The gap between "
    "seasons is about 243 days. Lags use the calendar, so that "
    "gap is missing history rather than a one-day lag.",
    "Jammu weather is not in the historical CSV, so it is not a "
    "supervised feature and is not used at training time.",
    "Training reads the first number of a forecast range. Public "
    "alerts use the upper end of that range. Both behaviors are "
    "intentional.",
    "FFD does not publish seven daily Marala discharge forecasts. "
    "These models are category classifiers, not a substitute for "
    "an official seven-day hydrograph.",
]


def resolve_data_file():
    """CSV path from FLOODSHIELD_DATA_FILE, else ml/data/processed/."""

    override = os.environ.get("FLOODSHIELD_DATA_FILE")
    if override:
        return Path(override)
    return (
        ML_DIR
        / "data"
        / "processed"
        / "chenab_marala_dataset.csv"
    )


def resolve_model_dir():
    """Model directory from FLOODSHIELD_MODEL_DIR, else ml/models/."""

    override = os.environ.get("FLOODSHIELD_MODEL_DIR")
    if override:
        return Path(override)
    return ML_DIR / "models"


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def normalize_column_name(name):
    """Convert a column name into snake_case."""

    name = str(name).strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")


def clean_numeric(series):
    """
    Convert messy numeric text into floats.

    A range such as '10 - 20' keeps the first number (10).
    The live alert engine still uses the upper end.
    """

    series = series.astype(str).str.strip()
    series = series.str.replace(",", "", regex=False)
    series = series.replace({
        "": np.nan,
        "-": np.nan,
        "--": np.nan,
        "nan": np.nan,
        "none": np.nan,
        "n/a": np.nan,
        "na": np.nan,
    })
    series = series.str.extract(
        r"([-+]?\d*\.?\d+)",
        expand=False,
    )
    return pd.to_numeric(series, errors="coerce")


def find_column(df, possible_names, required=True):
    """Find a column from several possible names."""

    columns = list(df.columns)

    for name in possible_names:
        if name in columns:
            return name

    for name in possible_names:
        for column in columns:
            if name in column or column in name:
                return column

    if required:
        raise ValueError(
            "\nCould not find required column.\n"
            f"Expected something similar to:\n{possible_names}\n\n"
            f"Available columns:\n{columns}"
        )

    return None


def flood_risk_from_inflow(inflow):
    """Convert inflow (thousand cusecs) into an FFD-style category."""

    if pd.isna(inflow):
        return np.nan

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


def class_counts(labels):
    """Count risk classes, including classes that do not appear."""

    counts = (
        pd.Series(labels)
        .value_counts()
        .reindex(RISK_CLASSES, fill_value=0)
    )
    return {label: int(counts.loc[label]) for label in RISK_CLASSES}


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


# ============================================================
# 3. LOAD AND CLEAN
# ============================================================

def load_observations(data_file):
    """Load the Marala CSV and engineer issue-day features."""

    data_file = Path(data_file)
    if not data_file.exists():
        raise FileNotFoundError(
            f"\n'{data_file}' was not found.\n"
            "Set FLOODSHIELD_DATA_FILE or place the CSV at "
            "ml/data/processed/chenab_marala_dataset.csv."
        )

    df = pd.read_csv(data_file)
    print("=" * 70)
    print("AI FLOODSHIELD PAK - MARALA 7-DAY FLOOD-RISK MODELS")
    print("=" * 70)
    print(f"\nOriginal rows: {len(df)}")
    print(f"Original columns: {len(df.columns)}")

    df.columns = [normalize_column_name(c) for c in df.columns]
    print("\nStandardized columns:")
    for column in df.columns:
        print("  -", column)

    date_col = find_column(
        df,
        ["date", "observation_date", "bulletin_date"],
    )
    inflow_col = find_column(
        df,
        [
            "inflow_thousands_of_cusecs",
            "inflow_thousands_cusecs",
            "inflow_thousand_cusecs",
            "inflow",
            "in_flow",
        ],
    )
    outflow_col = find_column(
        df,
        [
            "outflow_thousands_of_cusecs",
            "outflow_thousands_cusecs",
            "outflow_thousand_cusecs",
            "outflow",
            "out_flow",
        ],
        required=False,
    )
    forecast_col = find_column(
        df,
        [
            "forecast_24h_inflow",
            "forecast_24hr_inflow",
            "forecast_24hrs_inflow",
            "forecast_next_24h_inflow",
            "forecast_next_24hrs_inflow",
            "forecast_next_24_hrs_inflow",
            "quantitative_forecast_for_next_24_hrs_inflow",
            "quantitative_forecast_for_next_24_hours_inflow",
            "quantitative_forecast_next_24_hrs_inflow",
            "forecast_inflow",
            "quantitative_forecast",
        ],
        required=False,
    )

    print("\nDetected important columns:")
    print("Date     :", date_col)
    print("Inflow   :", inflow_col)
    print("Outflow  :", outflow_col)
    print("Forecast :", forecast_col)

    df[date_col] = pd.to_datetime(
        df[date_col],
        errors="coerce",
        dayfirst=True,
    )
    invalid_dates = int(df[date_col].isna().sum())
    if invalid_dates:
        print(f"\nRemoving {invalid_dates} row(s) with invalid dates.")

    df = df.dropna(subset=[date_col]).copy()
    df = df.sort_values(date_col).reset_index(drop=True)

    df[inflow_col] = clean_numeric(df[inflow_col])
    if outflow_col:
        df[outflow_col] = clean_numeric(df[outflow_col])
    if forecast_col:
        df[forecast_col] = clean_numeric(df[forecast_col])
        print("\n24-hour forecast data check:")
        print("Available values :", int(df[forecast_col].notna().sum()))
        print("Missing values   :", int(df[forecast_col].isna().sum()))
        print("Minimum forecast :", df[forecast_col].min())
        print("Maximum forecast :", df[forecast_col].max())
        print(
            "Note: ranges keep the FIRST number for training. "
            "Alerts use the UPPER number."
        )

    df = df.dropna(subset=[inflow_col]).copy()
    df = df.sort_values(date_col).reset_index(drop=True)

    duplicate_dates = int(df[date_col].duplicated().sum())
    if duplicate_dates > 0:
        print(f"\nWARNING: Found {duplicate_dates} duplicate date(s).")
        print("Keeping the last record for each date.")
        df = (
            df.sort_values(date_col)
            .drop_duplicates(subset=[date_col], keep="last")
            .reset_index(drop=True)
        )

    gaps = df[date_col].sort_values().diff().dt.days
    long_gaps = int((gaps > 1).sum())
    print(f"\nCalendar gaps longer than one day: {long_gaps}")
    if long_gaps:
        print(
            "Lags use the calendar. A gap is missing history, "
            "not a one-day lag."
        )

    df["year"] = df[date_col].dt.year
    df["month"] = df[date_col].dt.month
    df["day"] = df[date_col].dt.day
    df["day_of_year"] = df[date_col].dt.dayofyear
    df["day_of_week"] = df[date_col].dt.dayofweek
    df["flood_season"] = df["month"].isin([6, 7, 8, 9]).astype(int)

    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["doy_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365.25)

    df["inflow_current"] = df[inflow_col]
    df["capacity_utilization"] = df["inflow_current"] / DESIGN_CAPACITY
    df["distance_from_low_flood"] = df["inflow_current"] - LOW_FLOOD

    if outflow_col:
        df["outflow_current"] = df[outflow_col]
        df["inflow_outflow_difference"] = (
            df["inflow_current"] - df["outflow_current"]
        )
        df["inflow_outflow_ratio"] = (
            df["inflow_current"]
            / df["outflow_current"].replace(0, np.nan)
        )

    if forecast_col:
        df["forecast_24h"] = df[forecast_col]
        df["forecast_change"] = df["forecast_24h"] - df["inflow_current"]
        df["forecast_change_pct"] = (
            df["forecast_change"]
            / df["inflow_current"].replace(0, np.nan)
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

    df = attach_calendar_history(df, date_col)

    features = build_feature_list(
        df,
        has_outflow=bool(outflow_col),
        has_forecast=bool(forecast_col),
    )

    label_support = class_counts(
        df["inflow_current"].apply(flood_risk_from_inflow)
    )
    print("\nInflow-derived class counts (all rows, not a horizon target):")
    for label, count in label_support.items():
        print(f"  {label:12} {count}")

    return df, date_col, features, label_support


def build_feature_list(df, has_outflow, has_forecast):
    """Issue-day feature names. Empty columns are dropped."""

    features = [
        "inflow_current",
        "month",
        "day_of_year",
        "day_of_week",
        "flood_season",
        "month_sin",
        "month_cos",
        "doy_sin",
        "doy_cos",
        "capacity_utilization",
        "distance_from_low_flood",
        "inflow_lag_1",
        "inflow_lag_2",
        "inflow_lag_3",
        "inflow_lag_7",
        "inflow_change_1",
        "inflow_change_3",
        "inflow_change_7",
        "inflow_pct_change_1",
        "inflow_pct_change_3",
        "inflow_mean_3d",
        "inflow_mean_7d",
        "inflow_max_3d",
        "inflow_max_7d",
        "inflow_std_3d",
        "inflow_std_7d",
        "inflow_vs_3d_mean",
        "inflow_vs_7d_mean",
    ]

    if has_outflow:
        features += [
            "outflow_current",
            "outflow_lag_1",
            "outflow_lag_3",
            "inflow_outflow_difference",
            "inflow_outflow_ratio",
        ]

    if has_forecast:
        features += [
            "forecast_24h",
            "forecast_change",
            "forecast_change_pct",
            "forecast_low_margin",
            "forecast_high_margin",
            "forecast_risk_numeric",
        ]

    valid = []
    for feature in features:
        if feature not in df.columns:
            continue
        if df[feature].notna().sum() == 0:
            print(f"Removing empty feature: {feature}")
            continue
        valid.append(feature)

    print("\nNumber of ML features:", len(valid))
    print("\nFeatures used:")
    for feature in valid:
        print("  -", feature)
    return valid


def attach_horizon_target(df, date_col, horizon_days):
    """
    Label each issue day with inflow exactly `horizon_days` later.

    A row shift is not used. Off-season gaps must not pair October
    with the next June. Missing calendar dates stay unlabeled.
    """

    lookup = df[[date_col, "inflow_current"]].rename(
        columns={
            date_col: "target_date",
            "inflow_current": "target_inflow",
        }
    )
    labeled = df.copy()
    labeled["target_date"] = labeled[date_col] + pd.to_timedelta(
        horizon_days,
        unit="D",
    )
    labeled = labeled.merge(lookup, on="target_date", how="left")
    labeled["target_flood_risk"] = labeled["target_inflow"].apply(
        flood_risk_from_inflow
    )
    return labeled


# ============================================================
# 4. MODELS
# ============================================================

def _tree_pipeline(estimator):
    """Median imputation fitted inside each training fold, not before it."""

    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", estimator),
    ])


def _forest_kwargs():
    return {
        "n_estimators": 400,
        "max_depth": None,
        "min_samples_split": 4,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
    }


def candidate_models():
    """
    Four estimators compared on the same chronological split.

    The unweighted forest is the high-accuracy baseline that mostly
    predicts Normal. Balanced weights are the imbalance remedy.
    No resampling is applied outside a training fold; class_weight
    is computed by scikit-learn from the rows inside each fit.
    """

    forest = _forest_kwargs()
    return {
        "Majority baseline": _tree_pipeline(
            DummyClassifier(strategy="most_frequent")
        ),
        "Random Forest (unweighted)": _tree_pipeline(
            RandomForestClassifier(class_weight=None, **forest)
        ),
        "Random Forest (balanced)": _tree_pipeline(
            RandomForestClassifier(class_weight="balanced", **forest)
        ),
        "Extra Trees (balanced)": _tree_pipeline(
            ExtraTreesClassifier(class_weight="balanced", **forest)
        ),
    }


def _format_metric(value):
    if value is None:
        return "not estimable"
    return f"{value:.4f}"


def score_predictions(y_true, y_pred, majority_label, unsupported_classes=None):
    """
    Score one fixed prediction vector.

    Macro-F1 uses only classes that appear in y_true. Classes with
    no evaluation rows are reported as absent, not as a fake zero
    that was averaged into the headline score. Very High is never
    given a performance claim when it has no training examples.
    """

    y_true = pd.Series(list(y_true), dtype="object").astype(str).reset_index(drop=True)
    y_pred = pd.Series(list(y_pred), dtype="object").astype(str).reset_index(drop=True)
    unsupported = set(unsupported_classes or [])
    present = [
        label for label in RISK_CLASSES
        if int((y_true == label).sum()) > 0
    ]
    absent = [label for label in RISK_CLASSES if label not in present]
    predicted_counts = y_pred.value_counts().to_dict()

    per_class = {}
    if present:
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true,
            y_pred,
            labels=present,
            zero_division=0,
        )
        scored = {
            label: index for index, label in enumerate(present)
        }
    else:
        scored = {}

    for label in RISK_CLASSES:
        support_n = int((y_true == label).sum())
        predicted_n = int(predicted_counts.get(label, 0))
        row = {
            "precision": None,
            "recall": None,
            "f1": None,
            "support": support_n,
            "predicted": predicted_n,
            "status": "absent_from_evaluation",
        }
        if label in unsupported:
            row["training_status"] = "unsupported"
        else:
            row["training_status"] = "supported"
        if support_n > 0:
            index = scored[label]
            row.update({
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
                "status": "scored",
            })
        elif predicted_n > 0:
            row["precision"] = 0.0
            row["status"] = "absent_from_evaluation_but_predicted"
        if label in unsupported and support_n == 0:
            row["status"] = "unsupported_not_scored"
        per_class[label] = row

    minority_labels = [
        label for label in present if label != majority_label
    ]
    if present:
        macro_f1 = float(f1_score(
            y_true,
            y_pred,
            labels=present,
            average="macro",
            zero_division=0,
        ))
        balanced = float(balanced_accuracy_score(y_true, y_pred))
        accuracy = float(accuracy_score(y_true, y_pred))
    else:
        macro_f1 = None
        balanced = None
        accuracy = None

    if minority_labels:
        minority_recall = float(recall_score(
            y_true,
            y_pred,
            labels=minority_labels,
            average="macro",
            zero_division=0,
        ))
    else:
        minority_recall = None

    minority_support = int(sum(
        per_class[label]["support"] for label in minority_labels
    ))
    matrix = confusion_matrix(
        y_true,
        y_pred,
        labels=RISK_CLASSES,
    ).tolist() if len(y_true) else []

    return {
        "accuracy": accuracy,
        "balanced_accuracy": balanced,
        "macro_f1": macro_f1,
        "macro_f1_classes": present,
        "minority_recall": minority_recall,
        "minority_labels": minority_labels,
        "minority_support": minority_support,
        "evaluation_reliable": minority_support >= 2,
        "classes_present": present,
        "classes_absent_from_evaluation": absent,
        "per_class": per_class,
        "confusion_matrix": matrix,
        "confusion_matrix_labels": list(RISK_CLASSES),
        "rows": int(len(y_true)),
    }


def select_from_cv(summaries):
    """
    Choose a model by cross-validated macro-F1, then minority recall.

    Accuracy is not part of the ordering. Equal primary scores break
    toward the pre-specified balanced forest, not toward a higher
    or lower accuracy.
    """

    usable = [
        row for row in summaries
        if row.get("cv_macro_f1") is not None
    ]
    if not usable:
        return None, "no_valid_cross_validation"

    def ordering(row):
        minority = row.get("cv_minority_recall")
        minority_key = -1.0 if minority is None else float(minority)
        return (float(row["cv_macro_f1"]), minority_key)

    ranked = sorted(usable, key=ordering, reverse=True)
    best_key = ordering(ranked[0])
    tied = [row for row in ranked if ordering(row) == best_key]
    basis = "cv_macro_f1_then_minority_recall"
    if len(tied) > 1:
        preference = {
            "Random Forest (balanced)": 3,
            "Extra Trees (balanced)": 2,
            "Random Forest (unweighted)": 1,
            "Majority baseline": 0,
        }
        tied.sort(
            key=lambda row: preference.get(row["name"], -1),
            reverse=True,
        )
        basis = (
            "cv_macro_f1_then_minority_recall_"
            "tie_break_pre_specified_order"
        )
        ranked = tied + [row for row in ranked if row not in tied]

    return ranked[0]["name"], basis


def cross_validate_candidates(X_train, y_train, majority_label):
    """TimeSeriesSplit on training years only. The same folds score every model."""

    print("\n" + "=" * 70)
    print("TIME-SERIES CROSS VALIDATION (2024-2025 ONLY)")
    print("=" * 70)
    print(
        "Selection metric: macro-F1 on classes present in the "
        "validation fold, then minority-class recall. "
        "Accuracy is printed and is not used to select."
    )

    models = candidate_models()
    summaries = []
    if y_train.nunique() < 2 or len(X_train) < 3:
        print("Not enough class variety for cross-validation.")
        return summaries, None, "no_valid_cross_validation"

    n_splits = min(5, max(2, len(X_train) // 40))
    while n_splits > 2 and len(X_train) <= n_splits:
        n_splits -= 1
    splitter = TimeSeriesSplit(n_splits=n_splits)
    folds = list(splitter.split(X_train))
    print(f"TimeSeriesSplit folds: {len(folds)}")

    for name, estimator in models.items():
        fold_scores = []
        try:
            for fold_number, (train_index, valid_index) in enumerate(folds, start=1):
                model = clone(estimator)
                y_fold = y_train.iloc[train_index]
                if y_fold.nunique() < 1 or len(train_index) < 2:
                    continue
                model.fit(X_train.iloc[train_index], y_fold)
                predicted = model.predict(X_train.iloc[valid_index])
                scored = score_predictions(
                    y_train.iloc[valid_index],
                    predicted,
                    majority_label,
                )
                scored["fold"] = fold_number
                fold_scores.append(scored)
        except Exception as exc:
            print(f"\nCould not cross-validate {name}: {exc}")
            summaries.append({
                "name": name,
                "cv_macro_f1": None,
                "cv_minority_recall": None,
                "cv_accuracy": None,
                "folds": 0,
                "folds_with_minority": 0,
                "error": str(exc),
            })
            continue

        macro_values = [
            item["macro_f1"] for item in fold_scores
            if item["macro_f1"] is not None
        ]
        minority_values = [
            item["minority_recall"] for item in fold_scores
            if item["minority_recall"] is not None
        ]
        accuracy_values = [
            item["accuracy"] for item in fold_scores
            if item["accuracy"] is not None
        ]
        summary = {
            "name": name,
            "cv_macro_f1": (
                float(np.mean(macro_values)) if macro_values else None
            ),
            "cv_minority_recall": (
                float(np.mean(minority_values)) if minority_values else None
            ),
            "cv_accuracy": (
                float(np.mean(accuracy_values)) if accuracy_values else None
            ),
            "folds": len(fold_scores),
            "folds_with_minority": len(minority_values),
            "error": None,
        }
        summaries.append(summary)
        print(f"\n{name}")
        print(
            "  CV macro-F1        :",
            _format_metric(summary["cv_macro_f1"]),
        )
        print(
            "  CV minority recall :",
            _format_metric(summary["cv_minority_recall"]),
            f"(folds with a minority class: {summary['folds_with_minority']})",
        )
        print(
            "  CV accuracy        :",
            _format_metric(summary["cv_accuracy"]),
            "(not used for selection)",
        )

    selected_name, basis = select_from_cv(summaries)
    print(f"\nSelected by {basis}: {selected_name}")
    return summaries, selected_name, basis


def _metric_lines(scored):
    """Readable per-class lines. Absent classes are not given a fake F1."""

    lines = [
        f"  accuracy           : {_format_metric(scored['accuracy'])}",
        "  balanced accuracy  : "
        + _format_metric(scored["balanced_accuracy"]),
        "  macro-F1           : "
        + _format_metric(scored["macro_f1"])
        + f" on {scored['macro_f1_classes'] or []}",
        "  minority recall    : "
        + _format_metric(scored["minority_recall"]),
        "  minority support   : " + str(scored["minority_support"]),
        "  evaluation reliable: " + str(scored["evaluation_reliable"]),
        "  absent from this set: "
        + ", ".join(scored["classes_absent_from_evaluation"]),
    ]
    lines.append("  per class:")
    for label in RISK_CLASSES:
        row = scored["per_class"][label]
        if row["status"] == "scored":
            lines.append(
                f"    {label:12} P={row['precision']:.2f} "
                f"R={row['recall']:.2f} F1={row['f1']:.2f} "
                f"support={row['support']} predicted={row['predicted']}"
            )
        else:
            lines.append(
                f"    {label:12} {row['status']} "
                f"support={row['support']} predicted={row['predicted']} "
                f"training={row['training_status']}"
            )
    return lines


def save_confusion_matrix(matrix, horizon_days, model_name, metrics_dir):
    """Save one matrix. Zero rows are classes with no test support."""

    metrics_dir.mkdir(parents=True, exist_ok=True)
    display = ConfusionMatrixDisplay(
        confusion_matrix=np.array(matrix),
        display_labels=RISK_CLASSES,
    )
    fig, ax = plt.subplots(figsize=(10, 7))
    display.plot(
        ax=ax,
        xticks_rotation=45,
        cmap="Blues",
        values_format="d",
    )
    ax.set_title(
        f"FloodShield 2026, day +{horizon_days}, {model_name}\n"
        "Classes with no test rows are not evidence of skill"
    )
    fig.tight_layout()
    figure_path = (
        metrics_dir / f"confusion_matrix_horizon_{horizon_days}.png"
    )
    fig.savefig(figure_path, dpi=120)
    plt.close(fig)
    return figure_path


def trainable_mask(labels):
    """Classes with at least two examples stay. The rest are unsupported."""

    counts = class_counts(labels)
    unsupported = [
        label for label, count in counts.items()
        if count < MIN_CLASS_EXAMPLES
    ]
    supported = [
        label for label, count in counts.items()
        if count >= MIN_CLASS_EXAMPLES
    ]
    return supported, unsupported


def save_feature_importance(model, features, horizon_days, metrics_dir):
    """Write tree importances when the fitted model exposes them."""

    tree_model = model.named_steps["model"]
    if not hasattr(tree_model, "feature_importances_"):
        return None

    importance = pd.DataFrame({
        "feature": features,
        "importance": tree_model.feature_importances_,
    }).sort_values("importance", ascending=False)

    metrics_dir.mkdir(parents=True, exist_ok=True)
    path = metrics_dir / f"feature_importance_horizon_{horizon_days}.csv"
    importance.to_csv(path, index=False)

    print("\nTop features, day +" + str(horizon_days) + ":")
    print(importance.head(10).to_string(index=False))

    if horizon_days == 1:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        importance.to_csv(
            OUTPUT_DIR / "floodshield_feature_importance.csv",
            index=False,
        )
    return importance


def empty_horizon_package(horizon_days, reason, features):
    """A horizon with no valid pairs. Metrics are not invented."""

    return {
        "model": None,
        "model_available": False,
        "model_name": None,
        "features": list(features),
        "risk_classes": list(RISK_CLASSES),
        "thresholds_thousand_cusecs": {
            "Low": LOW_FLOOD,
            "Medium": MEDIUM_FLOOD,
            "High": HIGH_FLOOD,
            "Very High": VERY_HIGH_FLOOD,
            "Exceptional": EXCEPTIONAL_FLOOD,
        },
        "design_capacity_thousand_cusecs": DESIGN_CAPACITY,
        "training_years": [2024, 2025],
        "test_year": 2026,
        "horizon_days": horizon_days,
        "version": MODEL_VERSION,
        "issue_time_feature_rule": ISSUE_TIME_FEATURE_RULE,
        "limitations": list(HYDROLOGICAL_LIMITATIONS),
        "unavailable_reason": reason,
        "metrics_2026": None,
        "class_support": None,
        "supported_classes": [],
        "unsupported_classes": list(RISK_CLASSES),
        "evaluation_reliable": False,
    }


def _drop_targets_inside_test_window(train_df, test_df, date_col):
    """Do not train on an inflow that belongs to the 2026 test window."""

    if train_df.empty or test_df.empty:
        return train_df, 0
    first_test_issue = test_df[date_col].min()
    leaked = train_df["target_date"] >= first_test_issue
    removed = int(leaked.sum())
    if removed:
        print(
            f"Removed {removed} training row(s) whose target date is "
            "on or after the first 2026 issue date."
        )
        train_df = train_df.loc[~leaked].copy()
    return train_df, removed


def train_horizon(df, date_col, features, horizon_days, metrics_dir):
    """Train, compare, and package one calendar horizon."""

    print("\n" + "#" * 70)
    print(f"HORIZON DAY +{horizon_days}")
    print("#" * 70)

    labeled = attach_horizon_target(df, date_col, horizon_days)
    misaligned = labeled["target_date"] != (
        labeled[date_col] + pd.to_timedelta(horizon_days, unit="D")
    )
    if bool(misaligned.any()):
        raise RuntimeError(
            f"Day +{horizon_days} target dates are not the issue "
            "date plus that many calendar days."
        )

    labeled = labeled[labeled["target_flood_risk"].notna()].copy()
    labeled = labeled.sort_values(date_col).reset_index(drop=True)
    print(f"Valid calendar pairs: {len(labeled)}")
    print(f"Source rows         : {len(df)}")
    if len(labeled) >= len(df):
        print(
            "WARNING: horizon labels are not fewer than source rows. "
            "Check that missing dates were left unlabeled."
        )

    train_df = labeled[labeled["year"].isin([2024, 2025])].copy()
    test_df = labeled[labeled["year"] == 2026].copy()
    train_df, removed_leaks = _drop_targets_inside_test_window(
        train_df,
        test_df,
        date_col,
    )
    if len(train_df) and len(test_df):
        if train_df[date_col].max() >= test_df[date_col].min():
            raise RuntimeError(
                "Training issue dates are not strictly before "
                "the 2026 test issue dates."
            )
    print(f"Training rows (2024-2025): {len(train_df)}")
    print(f"Testing rows (2026)      : {len(test_df)}")

    support = {
        "pairs": int(len(labeled)),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "train": class_counts(train_df["target_flood_risk"])
        if len(train_df)
        else class_counts([]),
        "test": class_counts(test_df["target_flood_risk"])
        if len(test_df)
        else class_counts([]),
    }
    print("Training class support:")
    for label, count in support["train"].items():
        print(f"  {label:12} {count}")
    print("2026 class support:")
    for label, count in support["test"].items():
        print(f"  {label:12} {count}")

    supported, unsupported = trainable_mask(
        train_df["target_flood_risk"] if len(train_df) else []
    )
    print("Supported training classes (>= 2 examples):")
    for label in supported or ["none"]:
        print("  -", label)
    print(
        "Unsupported classes (no meaningful performance claim):"
    )
    for label in unsupported or ["none"]:
        count = support["train"].get(label, 0)
        print(f"  - {label} (training examples: {count})")

    trainable = train_df[
        train_df["target_flood_risk"].isin(supported)
    ].copy() if len(train_df) else train_df
    enough = (
        len(trainable) >= MIN_TRAIN_ROWS
        and len(supported) >= MIN_TRAIN_CLASSES
    )
    if not enough:
        reason = (
            f"Day +{horizon_days} is unavailable. Trainable rows: "
            f"{len(trainable)}. Supported classes: {supported}. "
            "A horizon is not invented when the training label "
            "set is too small."
        )
        print(reason)
        package = empty_horizon_package(horizon_days, reason, features)
        package["class_support"] = support
        package["unsupported_classes"] = unsupported
        package["supported_classes"] = supported
        package["evaluation_reliable"] = False
        return package, None

    majority_label = trainable["target_flood_risk"].mode().iloc[0]
    X_train = trainable[features]
    y_train = trainable["target_flood_risk"]
    cv_summaries, selected_name, selection_basis = cross_validate_candidates(
        X_train,
        y_train,
        majority_label,
    )
    if selected_name is None:
        selected_name = "Random Forest (balanced)"
        selection_basis = "pre_specified_balanced_forest_cv_unavailable"

    models = candidate_models()
    print("\n" + "=" * 70)
    print(f"2026 TEST COMPARISON — DAY +{horizon_days}")
    print("=" * 70)
    print(
        "Each candidate is fit once on 2024-2025 and scored once "
        "on 2026. The saved model is the cross-validation choice. "
        "The test table is not used to pick a different model."
    )

    comparison = []
    fitted = {}
    report_lines = [
        f"FloodShield day +{horizon_days}",
        f"Selected: {selected_name}",
        f"Selection basis: {selection_basis}",
        "Accuracy is not the selection metric.",
        f"Unsupported classes: {unsupported}",
        f"Training support: {support['train']}",
        f"2026 support: {support['test']}",
        "",
    ]
    y_test = (
        test_df["target_flood_risk"] if len(test_df) else pd.Series(dtype=object)
    )
    X_test = test_df[features] if len(test_df) else None

    for name, estimator in models.items():
        model = clone(estimator)
        model.fit(X_train, y_train)
        fitted[name] = model
        if X_test is None or len(test_df) == 0:
            scored = None
        else:
            scored = score_predictions(
                y_test,
                model.predict(X_test),
                majority_label,
                unsupported,
            )
        comparison.append({
            "name": name,
            "selected": name == selected_name,
            "test_2026": scored,
        })
        print(f"\n{name}" + ("  [selected]" if name == selected_name else ""))
        if scored is None:
            print("  2026 metrics: no test rows")
            report_lines.append(f"{name}: no 2026 rows")
        else:
            for line in _metric_lines(scored):
                print(line)
            report_lines.append(name + (" [selected]" if name == selected_name else ""))
            report_lines.extend(_metric_lines(scored))
            report_lines.append(
                "  confusion matrix labels: " + ", ".join(RISK_CLASSES)
            )
            report_lines.append(f"  confusion matrix: {scored['confusion_matrix']}")
            report_lines.append("")

    best_model = fitted[selected_name]
    selected_test = next(
        item["test_2026"] for item in comparison if item["selected"]
    )
    metrics_dir.mkdir(parents=True, exist_ok=True)
    report_path = metrics_dir / f"classification_report_horizon_{horizon_days}.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    figure_path = None
    if selected_test is not None:
        figure_path = save_confusion_matrix(
            selected_test["confusion_matrix"],
            horizon_days,
            selected_name,
            metrics_dir,
        )
        if not selected_test["evaluation_reliable"]:
            print(
                "\n2026 does not contain enough minority-class days "
                "to treat this horizon's accuracy as flood skill."
            )

    prediction_frame = None
    if selected_test is not None:
        y_pred = best_model.predict(X_test)
        prediction_frame = pd.DataFrame({
            "date": test_df[date_col].values,
            "horizon_days": horizon_days,
            "forecast_date": test_df["target_date"].values,
            "current_inflow": test_df["inflow_current"].values,
            "actual_next_inflow": test_df["target_inflow"].values,
            "actual_flood_risk": y_test.values,
            "predicted_flood_risk": y_pred,
        })
        if hasattr(best_model, "predict_proba"):
            probabilities = best_model.predict_proba(X_test)
            prediction_frame["prediction_confidence"] = probabilities.max(axis=1)
        if horizon_days == 1:
            horizon_one = prediction_frame[
                [
                    "date",
                    "current_inflow",
                    "actual_next_inflow",
                    "actual_flood_risk",
                    "predicted_flood_risk",
                ]
            ].copy()
            if "prediction_confidence" in prediction_frame.columns:
                horizon_one["prediction_confidence"] = prediction_frame[
                    "prediction_confidence"
                ].values
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output = OUTPUT_DIR / "floodshield_2026_predictions.csv"
            horizon_one.to_csv(output, index=False)
            print(f"\nSaved 2026 day+1 predictions to:\n{output}")

    if selected_name != "Majority baseline":
        save_feature_importance(
            best_model,
            features,
            horizon_days,
            metrics_dir,
        )

    public_comparison = []
    for item in comparison:
        scored = item["test_2026"] or {}
        cv_row = next(
            (row for row in cv_summaries if row["name"] == item["name"]),
            {},
        )
        public_comparison.append({
            "name": item["name"],
            "selected": item["selected"],
            "cv_macro_f1": cv_row.get("cv_macro_f1"),
            "cv_minority_recall": cv_row.get("cv_minority_recall"),
            "cv_accuracy": cv_row.get("cv_accuracy"),
            "folds_with_minority": cv_row.get("folds_with_minority"),
            "test_accuracy": scored.get("accuracy"),
            "test_balanced_accuracy": scored.get("balanced_accuracy"),
            "test_macro_f1": scored.get("macro_f1"),
            "test_minority_recall": scored.get("minority_recall"),
            "test_minority_support": scored.get("minority_support"),
            "evaluation_reliable": scored.get("evaluation_reliable"),
            "per_class": scored.get("per_class"),
            "confusion_matrix": scored.get("confusion_matrix"),
            "classes_absent_from_evaluation": scored.get(
                "classes_absent_from_evaluation"
            ),
        })

    metrics = {
        "selected_model": selected_name,
        "selection_basis": selection_basis,
        "accuracy": None if selected_test is None else selected_test["accuracy"],
        "balanced_accuracy": (
            None if selected_test is None else selected_test["balanced_accuracy"]
        ),
        "macro_f1": None if selected_test is None else selected_test["macro_f1"],
        "minority_recall": (
            None if selected_test is None else selected_test["minority_recall"]
        ),
        "evaluation_reliable": (
            False if selected_test is None else selected_test["evaluation_reliable"]
        ),
        "per_class": None if selected_test is None else selected_test["per_class"],
        "classes_absent_from_test": (
            [] if selected_test is None
            else selected_test["classes_absent_from_evaluation"]
        ),
        "confusion_matrix": (
            None if selected_test is None else selected_test["confusion_matrix"]
        ),
        "confusion_matrix_labels": list(RISK_CLASSES),
        "classification_report_path": str(report_path),
        "confusion_matrix_path": (
            None if figure_path is None else str(figure_path)
        ),
        "comparison": public_comparison,
        "targets_removed_for_test_window": removed_leaks,
    }

    package = {
        "model": best_model,
        "model_available": True,
        "model_name": selected_name,
        "features": list(features),
        "risk_classes": list(RISK_CLASSES),
        "supported_classes": list(supported),
        "unsupported_classes": list(unsupported),
        "evaluation_reliable": metrics["evaluation_reliable"],
        "thresholds_thousand_cusecs": {
            "Low": LOW_FLOOD,
            "Medium": MEDIUM_FLOOD,
            "High": HIGH_FLOOD,
            "Very High": VERY_HIGH_FLOOD,
            "Exceptional": EXCEPTIONAL_FLOOD,
        },
        "design_capacity_thousand_cusecs": DESIGN_CAPACITY,
        "training_years": [2024, 2025],
        "test_year": 2026,
        "horizon_days": horizon_days,
        "version": MODEL_VERSION,
        "cv_summaries_2024_2025": cv_summaries,
        "metrics_2026": metrics,
        "class_support": support,
        "majority_label": str(majority_label),
        "issue_time_feature_rule": ISSUE_TIME_FEATURE_RULE,
        "limitations": list(HYDROLOGICAL_LIMITATIONS),
        "split": (
            "Chronological. Training rows are issue dates in 2024 and "
            "2025. Test rows are issue dates in 2026. No shuffled split. "
            "The median imputer and class weights are fit on training "
            "rows only. Classes with fewer than two training examples "
            "are unsupported and are not used as training labels."
        ),
    }
    return package, prediction_frame


def backup_existing_model(model_dir):
    """Keep the previous next-day pickle before it is replaced."""

    source = model_dir / "floodshield_marala_model.pkl"
    destination = model_dir / "floodshield_marala_model_nextday_backup.pkl"
    if not source.exists():
        print(f"\nNo existing model to back up at {source}")
        return None
    if destination.exists():
        print(f"\nBackup already exists and was left in place:\n{destination}")
        return destination
    model_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(f"\nBacked up the existing model to:\n{destination}")
    return destination


def save_packages(packages, model_dir):
    """Write horizon files and the compatible horizon-1 artifact."""

    model_dir.mkdir(parents=True, exist_ok=True)
    horizon_dir = model_dir / "horizons"
    horizon_dir.mkdir(parents=True, exist_ok=True)

    for horizon, package in packages.items():
        path = horizon_dir / f"floodshield_horizon_{horizon}.pkl"
        joblib.dump(package, path)
        print(f"Saved day +{horizon}: {path}")

    horizon_one = packages[1]
    compatible = model_dir / "floodshield_marala_model.pkl"
    joblib.dump(horizon_one, compatible)
    print(f"Saved compatible horizon-1 model: {compatible}")
    if "model" not in horizon_one or "features" not in horizon_one:
        raise RuntimeError(
            "Horizon-1 package is missing model or features."
        )


def write_metrics_index(packages, label_support, metrics_dir):
    """Save a JSON-free text summary plus a small JSON index."""

    import json

    metrics_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "version": MODEL_VERSION,
        "inflow_class_counts": label_support,
        "limitations": HYDROLOGICAL_LIMITATIONS,
        "horizons": {},
    }
    lines = [
        "FloodShield Marala horizon metrics",
        f"Version: {MODEL_VERSION}",
        "",
        "Inflow-derived class counts:",
    ]
    for label, count in label_support.items():
        lines.append(f"  {label}: {count}")
    lines.append("")
    lines.append("Limitations:")
    for item in HYDROLOGICAL_LIMITATIONS:
        lines.append(f"  - {item}")
    lines.append("")

    reliable_horizons = []
    for horizon, package in packages.items():
        metrics = package.get("metrics_2026") or {}
        public_metrics = {
            key: metrics.get(key)
            for key in (
                "accuracy",
                "balanced_accuracy",
                "macro_f1",
                "minority_recall",
                "evaluation_reliable",
                "classes_absent_from_test",
                "selection_basis",
            )
        }
        comparison = []
        for row in metrics.get("comparison") or []:
            comparison.append({
                key: row.get(key)
                for key in (
                    "name",
                    "selected",
                    "cv_macro_f1",
                    "cv_minority_recall",
                    "cv_accuracy",
                    "test_accuracy",
                    "test_balanced_accuracy",
                    "test_macro_f1",
                    "test_minority_recall",
                    "test_minority_support",
                    "evaluation_reliable",
                    "classes_absent_from_evaluation",
                    "per_class",
                    "confusion_matrix",
                )
            })
        if package.get("evaluation_reliable"):
            reliable_horizons.append(horizon)
        summary["horizons"][str(horizon)] = {
            "model_available": package.get("model_available"),
            "model_name": package.get("model_name"),
            "supported_classes": package.get("supported_classes"),
            "unsupported_classes": package.get("unsupported_classes"),
            "evaluation_reliable": package.get("evaluation_reliable"),
            "class_support": package.get("class_support"),
            "metrics_2026": public_metrics if metrics else None,
            "comparison": comparison,
            "unavailable_reason": package.get("unavailable_reason"),
        }
        lines.append(f"Day +{horizon}")
        lines.append(f"  available: {package.get('model_available')}")
        lines.append(f"  model: {package.get('model_name')}")
        lines.append(f"  supported: {package.get('supported_classes')}")
        lines.append(f"  unsupported: {package.get('unsupported_classes')}")
        lines.append(f"  support: {package.get('class_support')}")
        lines.append(
            "  2026 evaluation reliable: "
            + str(package.get("evaluation_reliable"))
        )
        if metrics:
            lines.append(
                "  selected 2026 accuracy / balanced / macro-F1 / "
                "minority recall: "
                f"{_format_metric(public_metrics['accuracy'])} / "
                f"{_format_metric(public_metrics['balanced_accuracy'])} / "
                f"{_format_metric(public_metrics['macro_f1'])} / "
                f"{_format_metric(public_metrics['minority_recall'])}"
            )
            lines.append(
                "  classes absent from 2026 test: "
                + str(public_metrics.get("classes_absent_from_test"))
            )
            lines.append("  comparison (accuracy was not used to select):")
            for row in comparison:
                lines.append(
                    f"    {row['name']}"
                    + (" [selected]" if row["selected"] else "")
                )
                lines.append(
                    "      CV macro-F1 / minority recall / accuracy: "
                    f"{_format_metric(row['cv_macro_f1'])} / "
                    f"{_format_metric(row['cv_minority_recall'])} / "
                    f"{_format_metric(row['cv_accuracy'])}"
                )
                lines.append(
                    "      2026 macro-F1 / minority recall / accuracy: "
                    f"{_format_metric(row['test_macro_f1'])} / "
                    f"{_format_metric(row['test_minority_recall'])} / "
                    f"{_format_metric(row['test_accuracy'])}"
                )
                per_class = row.get("per_class") or {}
                for label, details in per_class.items():
                    if not details:
                        continue
                    if details.get("status") == "scored":
                        lines.append(
                            f"        {label}: recall={details['recall']:.2f} "
                            f"f1={details['f1']:.2f} support={details['support']}"
                        )
                    else:
                        lines.append(
                            f"        {label}: {details.get('status')} "
                            f"support={details.get('support')}"
                        )
        else:
            lines.append("  2026 metrics: unavailable")
            if package.get("unavailable_reason"):
                lines.append(f"  reason: {package.get('unavailable_reason')}")
        lines.append("")

    if reliable_horizons:
        conclusion = (
            "Minority-class evaluation is reliable only for horizons: "
            + ", ".join(str(item) for item in reliable_horizons)
        )
    else:
        conclusion = (
            "Reliable seven-day evaluation of minority flood classes "
            "is not possible on this dataset. The 2026 test labels are "
            "almost entirely Normal, and Very High has zero examples. "
            "High accuracy is the majority-class rate, not flood skill."
        )
    summary["evaluation_conclusion"] = conclusion
    lines.append("Conclusion:")
    lines.append(f"  {conclusion}")
    lines.append("")

    text_path = metrics_dir / "horizon_metrics.txt"
    json_path = metrics_dir / "horizon_metrics.json"
    text_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote metric index:\n{text_path}")


# ============================================================
# 5. LIVE MULTI-HORIZON PREDICTION
# ============================================================

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


# ============================================================
# 6. TRAINING ENTRY POINT
# ============================================================

def main():
    """Train all seven horizons. Importing this module does not train."""

    data_file = resolve_data_file()
    model_dir = resolve_model_dir()
    metrics_dir = model_dir / "metrics"

    df, date_col, features, label_support = load_observations(data_file)
    train_years = df["year"].isin([2024, 2025])
    features = [
        feature
        for feature in features
        if df.loc[train_years, feature].notna().any()
    ]
    print(f"\nFeatures kept after the training-year check: {len(features)}")
    backup_existing_model(model_dir)

    packages = {}
    for horizon in HORIZONS:
        package, _predictions = train_horizon(
            df,
            date_col,
            features,
            horizon,
            metrics_dir,
        )
        packages[horizon] = package

    save_packages(packages, model_dir)
    write_metrics_index(packages, label_support, metrics_dir)

    print("\n" + "=" * 70)
    print("HYDROLOGICAL LIMITATIONS")
    print("=" * 70)
    for item in HYDROLOGICAL_LIMITATIONS:
        print(" -", item)

    print("\n" + "=" * 70)
    print("FLOODSHIELD 7-DAY TRAINING COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
