# ============================================================
# AI FLOODSHIELD PAK
# Flood Risk ML Model - Chenab River at Marala
#
# Training data : 2024 + 2025
# Testing data  : 2026
#
# Target:
# Predict NEXT day's flood-risk category using information
# available on the current day.
#
# Required packages:
# pandas, numpy, scikit-learn, matplotlib, joblib
# ============================================================

import os
import re
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.ensemble import (
    RandomForestClassifier,
    ExtraTreesClassifier
)
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    accuracy_score,
    balanced_accuracy_score,
    f1_score
)

warnings.filterwarnings("ignore")


# ============================================================
# 1. CONFIGURATION
# ============================================================

ML_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = str(ML_DIR / "data" / "processed" / "chenab_marala_dataset.csv")
MODEL_FILE = str(ML_DIR / "models" / "floodshield_marala_model.pkl")
OUTPUTS_DIR = ML_DIR / "outputs"
PREDICTIONS_FILE = str(OUTPUTS_DIR / "floodshield_2026_predictions.csv")
FEATURE_IMPORTANCE_FILE = str(
    OUTPUTS_DIR / "floodshield_feature_importance.csv"
)

# Flood thresholds in THOUSANDS OF CUSECS
# Marala / Chenab thresholds supplied from FFD
LOW_FLOOD = 100.0
MEDIUM_FLOOD = 150.0
HIGH_FLOOD = 200.0
VERY_HIGH_FLOOD = 400.0
EXCEPTIONAL_FLOOD = 600.0

# Design capacity = 11 lac cusecs
DESIGN_CAPACITY = 1100.0

RISK_CLASSES = [
    "Normal",
    "Low",
    "Medium",
    "High",
    "Very High",
    "Exceptional"
]


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def normalize_column_name(name):
    """
    Convert column names into a simple standardized form.

    Example:
    'Inflow_Thousands of Cusecs'
        -> 'inflow_thousands_of_cusecs'
    """
    name = str(name).strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")


def clean_numeric(series):
    """
    Convert messy numerical data into floats.

    Handles values such as:
        '125.5'
        '125,500'
        ' 125 '
        '-'
        'N/A'
    """
    series = series.astype(str).str.strip()

    # Remove commas
    series = series.str.replace(",", "", regex=False)

    # Common missing-value text
    series = series.replace({
        "": np.nan,
        "-": np.nan,
        "--": np.nan,
        "nan": np.nan,
        "none": np.nan,
        "n/a": np.nan,
        "na": np.nan
    })

    # Extract first numeric value if text is also present
    series = series.str.extract(
        r"([-+]?\d*\.?\d+)",
        expand=False
    )

    return pd.to_numeric(series, errors="coerce")


def find_column(df, possible_names, required=True):
    """
    Find a dataframe column from several possible names.

    This makes the code tolerant of slightly different
    column naming in the CSV.
    """
    columns = list(df.columns)

    # Exact match first
    for name in possible_names:
        if name in columns:
            return name

    # Partial/fuzzy match
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
    """
    Convert inflow (thousand cusecs) into FFD flood category.
    """
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


# ============================================================
# 3. LOAD DATA
# ============================================================

if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(
        f"\n'{DATA_FILE}' was not found.\n"
        "Place the CSV in the same folder as this Python script."
    )

df = pd.read_csv(DATA_FILE)

print("=" * 70)
print("AI FLOODSHIELD PAK - MARALA FLOOD-RISK MODEL")
print("=" * 70)

print(f"\nOriginal rows: {len(df)}")
print(f"Original columns: {len(df.columns)}")


# ============================================================
# 4. STANDARDIZE COLUMN NAMES
# ============================================================

df.columns = [normalize_column_name(c) for c in df.columns]

print("\nStandardized columns:")
for c in df.columns:
    print("  -", c)


# ============================================================
# 5. FIND IMPORTANT COLUMNS
# ============================================================

date_col = find_column(
    df,
    [
        "date",
        "observation_date",
        "bulletin_date"
    ]
)

inflow_col = find_column(
    df,
    [
        "inflow_thousands_of_cusecs",
        "inflow_thousand_cusecs",
        "inflow",
        "in_flow"
    ]
)

outflow_col = find_column(
    df,
    [
        "outflow_thousands_of_cusecs",
        "outflow_thousand_cusecs",
        "outflow",
        "out_flow"
    ],
    required=False
)

forecast_col = find_column(
    df,
    [
        # Exact column in chenab_marala_dataset.csv
        "forecast_24h_inflow",

        # Other possible variants
        "forecast_24hr_inflow",
        "forecast_24hrs_inflow",
        "forecast_next_24h_inflow",
        "forecast_next_24hrs_inflow",
        "forecast_next_24_hrs_inflow",
        "quantitative_forecast_for_next_24_hrs_inflow",
        "quantitative_forecast_for_next_24_hours_inflow",
        "quantitative_forecast_next_24_hrs_inflow",
        "forecast_inflow",
        "quantitative_forecast"
    ],
    required=False
)

print("\nDetected important columns:")
print("Date     :", date_col)
print("Inflow   :", inflow_col)
print("Outflow  :", outflow_col)
print("Forecast :", forecast_col)


# ============================================================
# 6. CLEAN DATE
# ============================================================

# Try normal date parsing first
df[date_col] = pd.to_datetime(
    df[date_col],
    errors="coerce",
    dayfirst=True
)

# Remove rows with invalid dates
invalid_dates = df[date_col].isna().sum()

if invalid_dates:
    print(f"\nRemoving {invalid_dates} row(s) with invalid dates.")

df = df.dropna(subset=[date_col]).copy()

# Sort chronologically - IMPORTANT for time-series prediction
df = df.sort_values(date_col).reset_index(drop=True)


# ============================================================
# 7. CLEAN NUMERIC COLUMNS
# ============================================================

df[inflow_col] = clean_numeric(df[inflow_col])

if outflow_col:
    df[outflow_col] = clean_numeric(df[outflow_col])

if forecast_col:
    df[forecast_col] = clean_numeric(df[forecast_col])
    # Check whether the FFD 24-hour forecast was loaded correctly
if forecast_col:
    print("\n24-hour forecast data check:")
    print("Available values :", df[forecast_col].notna().sum())
    print("Missing values   :", df[forecast_col].isna().sum())
    print("Minimum forecast :", df[forecast_col].min())
    print("Maximum forecast :", df[forecast_col].max())


# Remove rows where current inflow is unavailable
df = df.dropna(subset=[inflow_col]).copy()
df = df.sort_values(date_col).reset_index(drop=True)


# ============================================================
# 8. CHECK DUPLICATE DATES
# ============================================================

duplicate_dates = df[date_col].duplicated().sum()

if duplicate_dates > 0:
    print(
        f"\nWARNING: Found {duplicate_dates} duplicate date(s)."
    )
    print(
        "Keeping the last record for each date because this "
        "dataset represents one station (Marala)."
    )

    df = (
        df.sort_values(date_col)
          .drop_duplicates(subset=[date_col], keep="last")
          .reset_index(drop=True)
    )


# ============================================================
# 9. BASIC DATE FEATURES
# ============================================================

df["year"] = df[date_col].dt.year
df["month"] = df[date_col].dt.month
df["day"] = df[date_col].dt.day
df["day_of_year"] = df[date_col].dt.dayofyear
df["day_of_week"] = df[date_col].dt.dayofweek

# Monsoon/flood season indicator.
# Can be adjusted depending on your final project definition.
df["flood_season"] = df["month"].isin([6, 7, 8, 9]).astype(int)


# ============================================================
# 10. CYCLICAL DATE FEATURES
# ============================================================
#
# December and January are chronologically close even though
# numerically month 12 and month 1 look far apart.
#
# Sine/cosine features solve this problem.
# ============================================================

df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

df["doy_sin"] = np.sin(
    2 * np.pi * df["day_of_year"] / 365.25
)

df["doy_cos"] = np.cos(
    2 * np.pi * df["day_of_year"] / 365.25
)


# ============================================================
# 11. HYDROLOGICAL FEATURES
# ============================================================

# Current inflow
df["inflow_current"] = df[inflow_col]

# Fraction of design capacity currently being used
df["capacity_utilization"] = (
    df["inflow_current"] / DESIGN_CAPACITY
)

# Difference from low-flood threshold
df["distance_from_low_flood"] = (
    df["inflow_current"] - LOW_FLOOD
)


# ------------------------------------------------------------
# Outflow-based features
# ------------------------------------------------------------

if outflow_col:

    df["outflow_current"] = df[outflow_col]

    # Inflow minus outflow:
    # positive value means more water entering than leaving.
    df["inflow_outflow_difference"] = (
        df["inflow_current"] -
        df["outflow_current"]
    )

    # Inflow / outflow ratio
    df["inflow_outflow_ratio"] = (
        df["inflow_current"] /
        df["outflow_current"].replace(0, np.nan)
    )


# ------------------------------------------------------------
# FFD 24-hour forecast feature
# ------------------------------------------------------------

if forecast_col:

    df["forecast_24h"] = df[forecast_col]

    # Difference between forecast next inflow and current inflow
    df["forecast_change"] = (
        df["forecast_24h"] -
        df["inflow_current"]
    )

    # Percentage forecast increase/decrease
    df["forecast_change_pct"] = (
        df["forecast_change"] /
        df["inflow_current"].replace(0, np.nan)
    )

    # How close FFD forecast is to flood thresholds
    df["forecast_low_margin"] = (
        df["forecast_24h"] - LOW_FLOOD
    )

    df["forecast_high_margin"] = (
        df["forecast_24h"] - HIGH_FLOOD
    )

if forecast_col:

    df["forecast_risk_numeric"] = pd.cut(
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
        labels=[0, 1, 2, 3, 4, 5],
        right=False
    ).astype(float)

# ============================================================
# 12. LAG FEATURES
# ============================================================
#
# Only PAST values are used.
#
# This is important:
# Using future values would cause DATA LEAKAGE.
# ============================================================

# Previous observations.
# These represent previous available records, not necessarily
# exact calendar-day lags if some dates are missing.
df["inflow_lag_1"] = df["inflow_current"].shift(1)
df["inflow_lag_2"] = df["inflow_current"].shift(2)
df["inflow_lag_3"] = df["inflow_current"].shift(3)
df["inflow_lag_7"] = df["inflow_current"].shift(7)


if outflow_col:
    df["outflow_lag_1"] = df["outflow_current"].shift(1)
    df["outflow_lag_3"] = df["outflow_current"].shift(3)


# ============================================================
# 13. INFLOW CHANGE / TREND FEATURES
# ============================================================

# Change compared with previous observation
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

# Percentage change
df["inflow_pct_change_1"] = (
    df["inflow_change_1"] /
    df["inflow_lag_1"].replace(0, np.nan)
)

df["inflow_pct_change_3"] = (
    df["inflow_change_3"] /
    df["inflow_lag_3"].replace(0, np.nan)
)


# ============================================================
# 14. ROLLING FEATURES
# ============================================================
#
# shift(1) is deliberately used BEFORE rolling().
#
# Therefore today's rolling feature is based only on
# PREVIOUS observations and does not peek into the future.
# ============================================================

past_inflow = df["inflow_current"].shift(1)

df["inflow_mean_3d"] = (
    past_inflow.rolling(window=3, min_periods=1).mean()
)

df["inflow_mean_7d"] = (
    past_inflow.rolling(window=7, min_periods=1).mean()
)

df["inflow_max_3d"] = (
    past_inflow.rolling(window=3, min_periods=1).max()
)

df["inflow_max_7d"] = (
    past_inflow.rolling(window=7, min_periods=1).max()
)

df["inflow_std_3d"] = (
    past_inflow.rolling(window=3, min_periods=2).std()
)

df["inflow_std_7d"] = (
    past_inflow.rolling(window=7, min_periods=2).std()
)


# ============================================================
# 15. TREND RELATIVE TO RECENT HISTORY
# ============================================================

df["inflow_vs_3d_mean"] = (
    df["inflow_current"] -
    df["inflow_mean_3d"]
)

df["inflow_vs_7d_mean"] = (
    df["inflow_current"] -
    df["inflow_mean_7d"]
)

# ============================================================
# 16. CREATE NEXT-DAY TARGET
# ============================================================

# Calculate number of calendar days to the next observation
df["days_to_next_observation"] = (
    df[date_col].shift(-1) - df[date_col]
).dt.days

print("\nGap between observations:")
print(
    df["days_to_next_observation"]
    .value_counts()
    .sort_index()
)

# IMPORTANT:
# Create next_inflow BEFORE using it to create flood-risk target
df["next_inflow"] = df["inflow_current"].shift(-1)

# Convert next day's inflow into flood-risk category
df["target_flood_risk"] = (
    df["next_inflow"].apply(flood_risk_from_inflow)
)

# Only keep records where the next observation is exactly
# the next calendar day.
model_df = df[
    (df["target_flood_risk"].notna()) &
    (df["days_to_next_observation"] == 1)
].copy()

print("\nValid next-day ML records:", len(model_df))

# ============================================================
# 16. CREATE THE PREDICTION TARGET
# ============================================================
#
# IMPORTANT:
#
# We are NOT predicting today's risk from today's inflow.
# That would simply teach the model the flood thresholds.
#
# Instead:
#
# Today's conditions
#       ↓
# Model
#       ↓
# NEXT observation/day flood risk
#
# This is much more useful for FloodShield.
# ============================================================

# df["next_inflow"] = df["inflow_current"].shift(-1)
# Number of calendar days until the next available observation
#df["days_to_next_observation"] = (
#    df[date_col].shift(-1) - df[date_col]
#).dt.days

#print("\nGap between observations:")
#print(df["days_to_next_observation"].value_counts().sort_index())

#df["target_flood_risk"] = (
#    df["next_inflow"].apply(flood_risk_from_inflow)
#)

#df["next_inflow"] = df["inflow_current"].shift(-1)

#df["target_flood_risk"] = (
#    df["next_inflow"].apply(flood_risk_from_inflow)
#)

# Keep only true next-day examples.
# This makes the model genuinely a next-day prediction model.
#model_df = df[
#    (df["target_flood_risk"].notna()) &
#    (df["days_to_next_observation"] == 1)
#].copy()
# Last row has no future observation, so it cannot be used
# during supervised training/testing.
#model_df = df.dropna(subset=["target_flood_risk"]).copy()


# ============================================================
# 17. CREATE FEATURE LIST
# ============================================================

features = [
    # Current water state
    "inflow_current",

    # Date / seasonal behavior
    "month",
    "day_of_year",
    "day_of_week",
    "flood_season",
    "month_sin",
    "month_cos",
    "doy_sin",
    "doy_cos",

    # Capacity / flood threshold relationship
    "capacity_utilization",
    "distance_from_low_flood",

    # Historical inflows
    "inflow_lag_1",
    "inflow_lag_2",
    "inflow_lag_3",
    "inflow_lag_7",

    # Rate of change
    "inflow_change_1",
    "inflow_change_3",
    "inflow_change_7",
    "inflow_pct_change_1",
    "inflow_pct_change_3",

    # Rolling trends
    "inflow_mean_3d",
    "inflow_mean_7d",
    "inflow_max_3d",
    "inflow_max_7d",
    "inflow_std_3d",
    "inflow_std_7d",
    "inflow_vs_3d_mean",
    "inflow_vs_7d_mean",
]


# Add outflow features only if available
if outflow_col:
    features += [
        "outflow_current",
        "outflow_lag_1",
        "outflow_lag_3",
        "inflow_outflow_difference",
        "inflow_outflow_ratio",
    ]


# Add FFD forecast features only if available
if forecast_col:
    features += [
        "forecast_24h",
        "forecast_change",
        "forecast_change_pct",
        "forecast_low_margin",
        "forecast_high_margin",
        "forecast_risk_numeric",
    ]


# ============================================================
# 18. REMOVE COMPLETELY EMPTY FEATURES
# ============================================================

valid_features = []

for feature in features:

    if feature not in model_df.columns:
        continue

    if model_df[feature].notna().sum() == 0:
        print(
            f"Removing empty feature: {feature}"
        )
        continue

    valid_features.append(feature)

features = valid_features

print("\nNumber of ML features:", len(features))

print("\nFeatures used:")
for feature in features:
    print("  -", feature)


# ============================================================
# 19. TRAIN / TEST SPLIT BY YEAR
# ============================================================
#
# DO NOT use train_test_split(random_state=...)
#
# Random splitting would mix earlier and later dates and would
# give an unrealistically optimistic result.
#
# Requested setup:
# 2024 + 2025 = training
# 2026        = testing
# ============================================================

train_df = model_df[
    model_df["year"].isin([2024, 2025])
].copy()

test_df = model_df[
    model_df["year"] == 2026
].copy()


if len(train_df) == 0:
    raise ValueError(
        "No 2024/2025 rows were found for training."
    )

if len(test_df) == 0:
    raise ValueError(
        "No 2026 rows were found for testing."
    )


X_train = train_df[features]
y_train = train_df["target_flood_risk"]

X_test = test_df[features]
y_test = test_df["target_flood_risk"]


print("\n" + "=" * 70)
print("DATA SPLIT")
print("=" * 70)

print(
    f"Training period: "
    f"{train_df[date_col].min().date()} "
    f"to {train_df[date_col].max().date()}"
)

print(
    f"Testing period : "
    f"{test_df[date_col].min().date()} "
    f"to {test_df[date_col].max().date()}"
)

print("\nTraining rows:", len(train_df))
print("Testing rows :", len(test_df))


# ============================================================
# 20. DISPLAY CLASS DISTRIBUTION
# ============================================================

print("\nTraining target distribution:")
print(
    y_train.value_counts()
           .reindex(RISK_CLASSES, fill_value=0)
)

print("\n2026 target distribution:")
print(
    y_test.value_counts()
          .reindex(RISK_CLASSES, fill_value=0)
)


# Warn about categories absent from training
training_classes = set(y_train.unique())

missing_training_classes = [
    c for c in RISK_CLASSES
    if c not in training_classes
]

if missing_training_classes:

    print("\nWARNING:")
    print(
        "The following risk classes do not occur in the "
        "2024/2025 training data:"
    )

    for c in missing_training_classes:
        print("  -", c)

    print(
        "\nA supervised classifier cannot properly learn a "
        "class it has never seen."
    )


# ============================================================
# 21. BUILD CANDIDATE MODELS
# ============================================================
#
# Both are strong for:
# - nonlinear hydrological relationships
# - small/medium datasets
# - mixed-scale numerical features
# - fast training
#
# StandardScaler is NOT necessary for tree models.
#
# Median imputation handles missing lag/rolling values.
# ============================================================

models = {

    "Random Forest": Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "model",
            RandomForestClassifier(
                n_estimators=400,
                max_depth=None,
                min_samples_split=4,
                min_samples_leaf=2,
                max_features="sqrt",

                # Helps with rare flood classes
                class_weight="balanced_subsample",

                random_state=42,
                n_jobs=-1
            )
        )
    ]),

    "Extra Trees": Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "model",
            ExtraTreesClassifier(
                n_estimators=400,
                max_depth=None,
                min_samples_split=4,
                min_samples_leaf=2,
                max_features="sqrt",

                # Important because severe floods may be rare
                class_weight="balanced",

                random_state=42,
                n_jobs=-1
            )
        )
    ])
}


# ============================================================
# 22. TIME-SERIES CROSS VALIDATION
# ============================================================
#
# Model selection is performed ONLY using 2024/2025.
# 2026 remains completely untouched until final testing.
#
# Macro F1 is used because normal days will probably greatly
# outnumber serious flood days.
# ============================================================

print("\n" + "=" * 70)
print("TIME-SERIES CROSS VALIDATION")
print("=" * 70)

# Number of splits depends on dataset size
n_splits = min(5, max(2, len(train_df) // 60))

tscv = TimeSeriesSplit(n_splits=n_splits)

cv_results = {}

for name, model in models.items():

    try:

        scores = cross_val_score(
            model,
            X_train,
            y_train,
            cv=tscv,
            scoring="f1_macro",
            n_jobs=-1
        )

        cv_results[name] = np.nanmean(scores)

        print(f"\n{name}")
        print(
            "Fold Macro-F1:",
            np.round(scores, 4)
        )
        print(
            "Mean Macro-F1:",
            round(np.nanmean(scores), 4)
        )

    except Exception as e:

        print(
            f"\nCould not cross-validate {name}: {e}"
        )

        cv_results[name] = -1


# ============================================================
# 23. SELECT BEST MODEL
# ============================================================

best_model_name = max(
    cv_results,
    key=cv_results.get
)

best_model = models[best_model_name]

print("\n" + "=" * 70)
print("SELECTED MODEL")
print("=" * 70)

print(best_model_name)


# ============================================================
# 24. TRAIN FINAL MODEL ON ALL 2024 + 2025 DATA
# ============================================================

best_model.fit(
    X_train,
    y_train
)
# Training predictions - diagnostic only
y_train_pred = best_model.predict(X_train)

training_accuracy = accuracy_score(
    y_train,
    y_train_pred
)

training_balanced_accuracy = balanced_accuracy_score(
    y_train,
    y_train_pred
)

training_macro_f1 = f1_score(
    y_train,
    y_train_pred,
    average="macro"
)

print("\nTraining-set diagnostics:")
print(f"Training Accuracy          : {training_accuracy:.4f}")
print(f"Training Balanced Accuracy : {training_balanced_accuracy:.4f}")
print(f"Training Macro F1          : {training_macro_f1:.4f}")

# Using this  mainly to detect overfitting.

# ============================================================
# 25. TEST ONLY ON UNSEEN 2026 DATA
# ============================================================

y_pred = best_model.predict(X_test)


# ============================================================
# 26. MODEL PERFORMANCE
# ============================================================

accuracy = accuracy_score(
    y_test,
    y_pred
)

balanced_accuracy = balanced_accuracy_score(
    y_test,
    y_pred
)

macro_f1 = f1_score(
    y_test,
    y_pred,
    average="macro"
)

weighted_f1 = f1_score(
    y_test,
    y_pred,
    average="weighted"
)


print("\n" + "=" * 70)
print("2026 TEST RESULTS")
print("=" * 70)

print(
    f"Accuracy          : {accuracy:.4f}"
)

print(
    f"Balanced Accuracy : {balanced_accuracy:.4f}"
)

print(
    f"Macro F1          : {macro_f1:.4f}"
)

print(
    f"Weighted F1       : {weighted_f1:.4f}"
)


# Detailed class performance
print("\nClassification Report:\n")

print(
    classification_report(
        y_test,
        y_pred,
        labels=RISK_CLASSES,
        zero_division=0
    )
)


# ============================================================
# 27. CONFUSION MATRIX
# ============================================================

cm = confusion_matrix(
    y_test,
    y_pred,
    labels=RISK_CLASSES
)

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=RISK_CLASSES
)

fig, ax = plt.subplots(figsize=(10, 7))

disp.plot(
    ax=ax,
    xticks_rotation=45,
    cmap="Blues",
    values_format="d"
)

plt.title(
    "FloodShield PAK - 2026 Flood Risk Confusion Matrix"
)

plt.tight_layout()
plt.show()


# ============================================================
# 28. CREATE 2026 PREDICTION RESULTS CSV
# ============================================================

results = pd.DataFrame({
    "date": test_df[date_col].values,
    "current_inflow": test_df["inflow_current"].values,
    "actual_next_inflow": test_df["next_inflow"].values,
    "actual_flood_risk": y_test.values,
    "predicted_flood_risk": y_pred
})


# Add prediction confidence
if hasattr(
    best_model.named_steps["model"],
    "predict_proba"
):

    probabilities = best_model.predict_proba(X_test)

    results["prediction_confidence"] = (
        probabilities.max(axis=1)
    )


OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

results.to_csv(
    PREDICTIONS_FILE,
    index=False
)

print(
    "\nSaved 2026 predictions to:"
    f"\n{PREDICTIONS_FILE}"
)


# ============================================================
# 29. FEATURE IMPORTANCE
# ============================================================

tree_model = best_model.named_steps["model"]

if hasattr(tree_model, "feature_importances_"):

    importance_df = pd.DataFrame({
        "feature": features,
        "importance": tree_model.feature_importances_
    })

    importance_df = importance_df.sort_values(
        "importance",
        ascending=False
    )

    print("\n" + "=" * 70)
    print("TOP FEATURE IMPORTANCE")
    print("=" * 70)

    print(
        importance_df.head(20).to_string(index=False)
    )

    importance_df.to_csv(
        FEATURE_IMPORTANCE_FILE,
        index=False
    )


# ============================================================
# 30. SAVE TRAINED MODEL + METADATA
# ============================================================
#
# Saving metadata together with the model is useful later when
# integrating it into FloodShield Engine / API / mobile app.
# ============================================================

model_package = {

    "model": best_model,

    "model_name": best_model_name,

    "features": features,

    "risk_classes": RISK_CLASSES,

    "thresholds_thousand_cusecs": {
        "Low": LOW_FLOOD,
        "Medium": MEDIUM_FLOOD,
        "High": HIGH_FLOOD,
        "Very High": VERY_HIGH_FLOOD,
        "Exceptional": EXCEPTIONAL_FLOOD
    },

    "design_capacity_thousand_cusecs":
        DESIGN_CAPACITY,

    "training_years": [2024, 2025],

    "test_year": 2026,

    "metrics_2026": {
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1
    }
}


OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
(ML_DIR / "models").mkdir(parents=True, exist_ok=True)

joblib.dump(
    model_package,
    MODEL_FILE
)

print("\n" + "=" * 70)
print("MODEL SAVED SUCCESSFULLY")
print("=" * 70)

print(f"\nModel file: {MODEL_FILE}")


# ============================================================
# 31. SHOW SAMPLE PREDICTIONS
# ============================================================

print("\nSample 2026 predictions:\n")

print(
    results[
        [
            "date",
            "current_inflow",
            "actual_next_inflow",
            "actual_flood_risk",
            "predicted_flood_risk"
        ]
    ].head(20).to_string(index=False)
)


print("\n" + "=" * 70)
print("FLOODSHIELD TRAINING COMPLETE")
print("=" * 70)