import pandas as pd
from pathlib import Path


# --------------------------------------------------
# File paths
# --------------------------------------------------

ML_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = str(ML_DIR / "data" / "processed" / "extracted_data.csv")
OUTPUT_FILE = str(ML_DIR / "data" / "processed" / "chenab_marala_dataset.csv")


# --------------------------------------------------
# Load CSV
# --------------------------------------------------

df = pd.read_csv(INPUT_FILE)


# --------------------------------------------------
# Validate required columns
# --------------------------------------------------

required_columns = {"river", "station"}

missing_columns = required_columns - set(df.columns)

if missing_columns:
    raise ValueError(
        f"Missing required column(s): {', '.join(missing_columns)}"
    )


# --------------------------------------------------
# Clean river and station values
# --------------------------------------------------

# Convert to string, remove extra spaces, and make lowercase
river_clean = (
    df["river"]
    .astype(str)
    .str.strip()
    .str.lower()
)

station_clean = (
    df["station"]
    .astype(str)
    .str.strip()
    .str.lower()
)


# --------------------------------------------------
# Filter Chenab + Marala rows
# --------------------------------------------------

filtered_df = df[
    (river_clean == "chenab") &
    (station_clean == "marala")
].copy()


# --------------------------------------------------
# Remove completely duplicated rows
# --------------------------------------------------

filtered_df = filtered_df.drop_duplicates()


# --------------------------------------------------
# Reset row index
# --------------------------------------------------

filtered_df.reset_index(drop=True, inplace=True)


# --------------------------------------------------
# Save output CSV
# --------------------------------------------------

filtered_df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("Extraction completed successfully.")
print(f"Total rows in original dataset : {len(df)}")
print(f"Chenab-Marala rows extracted   : {len(filtered_df)}")
print(f"Output file created            : {Path(OUTPUT_FILE).resolve()}")