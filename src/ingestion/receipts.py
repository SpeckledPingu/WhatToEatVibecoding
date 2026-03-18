"""
receipts.py — Ingest store receipt data from CSV files into the database.

HOW THIS SCRIPT WORKS
1. Scans data/receipts/ for CSV files
2. For each file, reads it with pandas and cleans the data:
   - Normalizes column names (strips whitespace, lowercases)
   - Parses dates (tries multiple formats)
   - Converts numeric fields (prices, quantities)
   - Handles missing values gracefully
3. Checks for duplicates (same item, store, date, price) and skips them
4. Inserts new rows into the Receipt table
5. Prints a detailed report of what was processed

WHAT IS PANDAS?
Pandas is Python's most popular library for working with tabular data (rows and
columns, like a spreadsheet). A DataFrame is the core pandas object — think of
it as a programmable spreadsheet where you can filter, transform, and aggregate
data with Python code instead of clicking.

RUN IT:
    uv run python -m src.ingestion.receipts
"""

from datetime import date
from pathlib import Path

import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.receipt import Receipt

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent
RECEIPTS_DIR = PROJECT_ROOT / "data" / "receipts"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean up column names for consistency.

    WHY NORMALIZE COLUMN NAMES?
    CSV files from different sources may have inconsistent column naming:
    - 'Item Name' vs 'item_name' vs ' item_name '
    Normalizing to lowercase with underscores and no whitespace means our
    code can reliably access columns by name regardless of how the CSV
    author formatted them.

    HOW str.strip() AND str.lower() WORK
    - strip() removes leading/trailing whitespace: ' item_name ' -> 'item_name'
    - lower() converts to lowercase: 'Item_Name' -> 'item_name'
    - replace(' ', '_') converts spaces to underscores: 'item name' -> 'item_name'
    """
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df


def parse_date(value) -> date | None:
    """
    Try to parse a date value in multiple formats.

    WHY MULTIPLE FORMATS?
    Different stores and data sources format dates differently:
    - 2026-03-17 (ISO format — most common in tech)
    - 03/17/2026 (US format — common on receipts)
    - 17-Mar-2026 (mixed format)

    pd.to_datetime() is pandas' Swiss Army knife for date parsing. With
    format=None (or using infer_datetime_format), it tries to figure out
    the format automatically. We provide explicit formats as fallbacks.
    """
    if pd.isna(value):
        return None

    # Try pandas automatic parsing first (handles most formats)
    try:
        return pd.to_datetime(value).date()
    except (ValueError, TypeError):
        pass

    # Try common date formats explicitly
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d-%b-%Y"]:
        try:
            return pd.to_datetime(value, format=fmt).date()
        except (ValueError, TypeError):
            continue

    return None


def safe_float(value) -> float | None:
    """
    Convert a value to float, returning None if conversion fails.

    WHY A SAFE CONVERTER?
    CSV data is all text — pandas tries to infer types, but sometimes gets it
    wrong (especially with currency symbols, commas in numbers, or blank cells).
    This function handles those edge cases gracefully instead of crashing.
    """
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value, default: int = 1) -> int:
    """
    Convert a value to int, returning a default if conversion fails.

    Quantities default to 1 — if we can't read the quantity, it's safest
    to assume one unit was purchased.
    """
    if pd.isna(value):
        return default
    try:
        return int(float(value))  # float() first handles "2.0" -> 2
    except (ValueError, TypeError):
        return default


def is_duplicate(session: Session, item_name: str, store_name: str,
                 purchase_date: date, total_price: float | None) -> bool:
    """
    Check if a matching receipt row already exists in the database.

    DUPLICATE DETECTION STRATEGY
    We consider a row a duplicate if it matches on item_name + store_name +
    purchase_date + total_price. This isn't perfect — you might genuinely buy
    the same item at the same price twice on the same day — but it catches
    the most common case: accidentally running ingestion twice on the same file.

    A more sophisticated approach would track which source_file rows have been
    ingested, but this simple check works well for our educational purpose.
    """
    query = select(Receipt).where(
        Receipt.item_name == item_name,
        Receipt.store_name == store_name,
        Receipt.purchase_date == purchase_date,
    )

    if total_price is not None:
        query = query.where(Receipt.total_price == total_price)

    return session.exec(query).first() is not None


def ingest_receipts():
    """
    Main ingestion function — scan, clean, and load all receipt CSV files.

    This function is designed to be RE-RUNNABLE. Running it multiple times
    on the same data won't create duplicates (it checks before inserting).
    This is important because data ingestion scripts are often run repeatedly
    as new data arrives or bugs are fixed.
    """
    print("=" * 70)
    print("RECEIPT INGESTION")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Discover CSV files
    # ------------------------------------------------------------------
    if not RECEIPTS_DIR.exists():
        print(f"\nERROR: Receipts directory not found: {RECEIPTS_DIR}")
        print("Please add receipt CSV files to data/receipts/ before running.")
        return

    csv_files = sorted(RECEIPTS_DIR.glob("*.csv"))
    print(f"\nFound {len(csv_files)} CSV file(s) in {RECEIPTS_DIR}")

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

            # Read the CSV into a pandas DataFrame
            # HOW pd.read_csv() WORKS
            # It reads the CSV file and creates a DataFrame where:
            #   - The first row becomes column headers
            #   - Each subsequent row becomes a data row
            #   - Pandas infers data types (numbers, strings, dates)
            try:
                df = pd.read_csv(csv_file)
            except Exception as e:
                print(f"  ERROR reading file: {e}")
                total_stats["errors"] += 1
                continue

            # Normalize column names for consistent access
            df = normalize_columns(df)

            print(f"  Columns: {list(df.columns)}")
            print(f"  Rows: {len(df)}")

            # Report any null values
            # isnull().sum() counts NaN values per column
            nulls = df.isnull().sum()
            null_cols = nulls[nulls > 0]
            if not null_cols.empty:
                print(f"  Null values:")
                for col, count in null_cols.items():
                    print(f"    {col}: {count} missing")

            file_added = 0
            file_skipped = 0

            # Process each row
            for idx, row in df.iterrows():
                # Extract and clean fields from the CSV row
                item_name = str(row.get("item_name", "")).strip()
                if not item_name:
                    print(f"  Row {idx + 1}: Skipping — no item_name")
                    total_stats["errors"] += 1
                    continue

                normalized_name = (
                    str(row["normalized_name"]).strip()
                    if pd.notna(row.get("normalized_name"))
                    else None
                )
                quantity = safe_int(row.get("quantity"))
                unit_price = safe_float(row.get("unit_price"))
                total_price = safe_float(row.get("total_price"))
                category = (
                    str(row["category"]).strip().lower()
                    if pd.notna(row.get("category"))
                    else None
                )
                store_name = str(row.get("store_name", "")).strip()
                purchase_date = parse_date(row.get("purchase_date"))

                if purchase_date is None:
                    print(f"  Row {idx + 1}: Skipping '{item_name}' — invalid date")
                    total_stats["errors"] += 1
                    continue

                # Check for duplicates before inserting
                if is_duplicate(session, item_name, store_name, purchase_date, total_price):
                    file_skipped += 1
                    continue

                # Create the Receipt record
                receipt = Receipt(
                    item_name=item_name,
                    normalized_name=normalized_name,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                    category=category,
                    store_name=store_name,
                    purchase_date=purchase_date,
                    source_file=csv_file.name,
                )
                session.add(receipt)
                file_added += 1

            # Commit after each file for safety
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
    print("RECEIPT INGESTION SUMMARY")
    print("=" * 70)
    print(f"  Files processed:      {total_stats['files']}")
    print(f"  Total rows added:     {total_stats['rows_added']}")
    print(f"  Duplicates skipped:   {total_stats['duplicates_skipped']}")
    print(f"  Errors:               {total_stats['errors']}")
    print(f"\nDatabase: {engine.url}")
    print("Done!")


if __name__ == "__main__":
    ingest_receipts()
