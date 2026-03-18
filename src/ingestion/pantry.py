"""
pantry.py — Ingest pantry inventory data from CSV files into the database.

HOW THIS SCRIPT WORKS
1. Scans data/pantry/ for CSV files
2. For each file, reads it with pandas and cleans the data:
   - Normalizes column names (strips whitespace, lowercases)
   - Parses inventory dates
   - Handles missing values for optional fields
3. Checks for duplicates (same item name + date inventoried) and skips them
4. Inserts new rows into the PantryItem table
5. Prints a detailed report

HOW PANTRY DATA DIFFERS FROM RECEIPT DATA
Pantry data is a STATE SNAPSHOT — it describes what you have right now.
Receipt data is TRANSACTIONAL — it describes what happened (a purchase).

This means:
  - Pantry has location/condition fields; receipts have price/store fields
  - Pantry quantities are often fractional (0.75 of a bottle); receipts are whole units
  - Pantry item names are pre-normalized (clean); receipt names are messy abbreviations
  - A new pantry scan replaces the old picture; receipts accumulate over time

RUN IT:
    uv run python -m src.ingestion.pantry
"""

from datetime import date
from pathlib import Path

import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.pantry import PantryItem

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent
PANTRY_DIR = PROJECT_ROOT / "data" / "pantry"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean up column names for consistency.

    Same approach as receipt ingestion — strip whitespace, lowercase,
    replace spaces with underscores.
    """
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df


def parse_date(value) -> date | None:
    """
    Try to parse a date value, handling multiple formats.

    Same multi-format parsing as receipt ingestion — dates from different
    data sources use different formats, so we try several.
    """
    if pd.isna(value):
        return None

    try:
        return pd.to_datetime(value).date()
    except (ValueError, TypeError):
        pass

    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d-%b-%Y"]:
        try:
            return pd.to_datetime(value, format=fmt).date()
        except (ValueError, TypeError):
            continue

    return None


def safe_float(value, default: float = 1.0) -> float:
    """
    Convert a value to float, returning a default if conversion fails.

    WHY float FOR PANTRY QUANTITIES?
    Pantry quantities are often fractional: "about 0.75 of a bag" or
    "0.5 bottle remaining." Using float (vs int for receipts) reflects
    this real-world difference in how inventory is measured.
    """
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def is_duplicate(session: Session, item_name: str, date_inventoried: date) -> bool:
    """
    Check if a matching pantry item already exists in the database.

    DUPLICATE DETECTION FOR PANTRY DATA
    We use item_name + date_inventoried as the duplicate key. This is different
    from receipt duplicates (which also check store and price) because pantry
    data doesn't have those fields.

    The assumption: you wouldn't log the same item twice on the same
    inventory date. If you re-run ingestion on the same file, duplicates
    are skipped.
    """
    existing = session.exec(
        select(PantryItem).where(
            PantryItem.item_name == item_name,
            PantryItem.date_inventoried == date_inventoried,
        )
    ).first()

    return existing is not None


def ingest_pantry():
    """
    Main ingestion function — scan, clean, and load all pantry CSV files.

    Like receipt ingestion, this is designed to be re-runnable safely.
    Duplicates are detected and skipped, so running it twice on the same
    data won't create duplicate rows.
    """
    print("=" * 70)
    print("PANTRY INGESTION")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Discover CSV files
    # ------------------------------------------------------------------
    if not PANTRY_DIR.exists():
        print(f"\nERROR: Pantry directory not found: {PANTRY_DIR}")
        print("Please add pantry CSV files to data/pantry/ before running.")
        return

    csv_files = sorted(PANTRY_DIR.glob("*.csv"))
    print(f"\nFound {len(csv_files)} CSV file(s) in {PANTRY_DIR}")

    if not csv_files:
        print("No CSV files found. Nothing to ingest.")
        return

    # ------------------------------------------------------------------
    # Step 2: Set up database
    # ------------------------------------------------------------------
    engine = get_engine()
    create_db_and_tables(engine)

    # ------------------------------------------------------------------
    # Step 3: Process each CSV file
    # ------------------------------------------------------------------
    total_stats = {"files": 0, "rows_added": 0, "duplicates_skipped": 0, "errors": 0}

    with Session(engine) as session:
        for csv_file in csv_files:
            print(f"\n--- Processing: {csv_file.name} ---")
            total_stats["files"] += 1

            try:
                df = pd.read_csv(csv_file)
            except Exception as e:
                print(f"  ERROR reading file: {e}")
                total_stats["errors"] += 1
                continue

            # Normalize column names
            df = normalize_columns(df)

            print(f"  Columns: {list(df.columns)}")
            print(f"  Rows: {len(df)}")

            # Report null values
            nulls = df.isnull().sum()
            null_cols = nulls[nulls > 0]
            if not null_cols.empty:
                print(f"  Null values:")
                for col, count in null_cols.items():
                    print(f"    {col}: {count} missing")

            # Report unique values for categorical columns
            # value_counts() shows the distribution of values in a column —
            # useful for understanding what categories exist in the data
            for cat_col in ["location", "condition", "category"]:
                if cat_col in df.columns:
                    unique = df[cat_col].dropna().unique()
                    print(f"  Unique {cat_col}s: {sorted(unique)}")

            file_added = 0
            file_skipped = 0

            # Process each row
            for idx, row in df.iterrows():
                item_name = str(row.get("item_name", "")).strip()
                if not item_name:
                    print(f"  Row {idx + 1}: Skipping — no item_name")
                    total_stats["errors"] += 1
                    continue

                date_inventoried = parse_date(row.get("date_inventoried"))
                if date_inventoried is None:
                    print(f"  Row {idx + 1}: Skipping '{item_name}' — invalid date")
                    total_stats["errors"] += 1
                    continue

                # Check for duplicates
                if is_duplicate(session, item_name, date_inventoried):
                    file_skipped += 1
                    continue

                # Extract optional fields with safe defaults
                quantity = safe_float(row.get("quantity"))
                unit = str(row.get("unit", "whole")).strip() if pd.notna(row.get("unit")) else "whole"
                location = (
                    str(row["location"]).strip().lower()
                    if pd.notna(row.get("location"))
                    else None
                )
                condition = (
                    str(row["condition"]).strip().lower()
                    if pd.notna(row.get("condition"))
                    else None
                )
                category = (
                    str(row["category"]).strip().lower()
                    if pd.notna(row.get("category"))
                    else None
                )
                notes = (
                    str(row["notes"]).strip()
                    if pd.notna(row.get("notes"))
                    else None
                )

                # Create the PantryItem record
                pantry_item = PantryItem(
                    item_name=item_name,
                    quantity=quantity,
                    unit=unit,
                    location=location,
                    condition=condition,
                    category=category,
                    date_inventoried=date_inventoried,
                    notes=notes,
                    source_file=csv_file.name,
                )
                session.add(pantry_item)
                file_added += 1

            # Commit after each file
            session.commit()

            total_stats["rows_added"] += file_added
            total_stats["duplicates_skipped"] += file_skipped
            print(f"  Added: {file_added} rows")
            if file_skipped:
                print(f"  Skipped (duplicates): {file_skipped} rows")

    # ------------------------------------------------------------------
    # Step 4: Print summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("PANTRY INGESTION SUMMARY")
    print("=" * 70)
    print(f"  Files processed:      {total_stats['files']}")
    print(f"  Total rows added:     {total_stats['rows_added']}")
    print(f"  Duplicates skipped:   {total_stats['duplicates_skipped']}")
    print(f"  Errors:               {total_stats['errors']}")
    print(f"\nDatabase: {engine.url}")
    print("Done!")


if __name__ == "__main__":
    ingest_pantry()
