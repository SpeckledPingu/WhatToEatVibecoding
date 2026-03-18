"""
data_comparison.py — Compare receipt and pantry data side by side.

HOW THIS SCRIPT WORKS
This script loads both receipt and pantry data from the database into pandas
DataFrames and produces a detailed comparison report. It highlights the
differences between these two data sources and previews why normalization
(WS04) is needed to combine them.

WHY THIS COMPARISON MATTERS
Receipts and pantry scans capture the SAME food but describe it VERY differently:
  - Receipt: "Greenwise Hmstyle Meatbal Ft" (store abbreviation, brand, codes)
  - Pantry:  "meatball" (simple, human-readable name)

This mismatch is THE fundamental challenge in combining real-world data sources.
Without normalization (cleaning and aligning names), you can't join these tables
or answer questions like "did I already buy the ingredients for this recipe?"

RUN IT:
    uv run python -m src.analytics.data_comparison
"""

import pandas as pd
from sqlmodel import Session, select

from src.database import get_engine
from src.models.pantry import PantryItem
from src.models.receipt import Receipt


def load_receipts_to_dataframe() -> pd.DataFrame:
    """
    Load all receipt records from the database into a pandas DataFrame.

    HOW model_dump() WORKS
    SQLModel objects have a method called model_dump() (inherited from Pydantic)
    that converts the object into a plain Python dictionary. pd.DataFrame() then
    turns a list of dictionaries into a table — each dict key becomes a column.
    """
    engine = get_engine()
    with Session(engine) as session:
        receipts = session.exec(select(Receipt)).all()
        if not receipts:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in receipts])


def load_pantry_to_dataframe() -> pd.DataFrame:
    """Load all pantry records from the database into a pandas DataFrame."""
    engine = get_engine()
    with Session(engine) as session:
        items = session.exec(select(PantryItem)).all()
        if not items:
            return pd.DataFrame()
        return pd.DataFrame([item.model_dump() for item in items])


def compare_data():
    """
    Produce a formatted side-by-side comparison of receipt and pantry data.
    """
    receipt_df = load_receipts_to_dataframe()
    pantry_df = load_pantry_to_dataframe()

    if receipt_df.empty and pantry_df.empty:
        print("No data found. Run ingestion first:")
        print("  uv run python -m src.ingestion.receipts")
        print("  uv run python -m src.ingestion.pantry")
        return

    print("=" * 70)
    print("DATA COMPARISON: Receipts vs. Pantry")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Schema comparison — what columns does each table have?
    # ------------------------------------------------------------------
    print("\n--- SCHEMA COMPARISON ---")
    print(f"\nReceipt columns ({len(receipt_df.columns)}):")
    for col in receipt_df.columns:
        dtype = receipt_df[col].dtype
        print(f"  {col:25s} {str(dtype):15s}")

    print(f"\nPantry columns ({len(pantry_df.columns)}):")
    for col in pantry_df.columns:
        dtype = pantry_df[col].dtype
        print(f"  {col:25s} {str(dtype):15s}")

    # Column overlap analysis
    # set() creates a collection of unique values — perfect for finding
    # which columns are shared vs. unique to each source
    receipt_cols = set(receipt_df.columns)
    pantry_cols = set(pantry_df.columns)
    shared_cols = receipt_cols & pantry_cols  # & is set intersection
    receipt_only = receipt_cols - pantry_cols  # - is set difference
    pantry_only = pantry_cols - receipt_cols

    print(f"\nShared columns: {sorted(shared_cols)}")
    print(f"Receipt-only columns: {sorted(receipt_only)}")
    print(f"Pantry-only columns: {sorted(pantry_only)}")

    # ------------------------------------------------------------------
    # 2. Record counts
    # ------------------------------------------------------------------
    print(f"\n--- RECORD COUNTS ---")
    print(f"  Receipt rows:  {len(receipt_df)}")
    print(f"  Pantry rows:   {len(pantry_df)}")

    # ------------------------------------------------------------------
    # 3. Unique item names from each source
    # ------------------------------------------------------------------
    print(f"\n--- ITEM NAMES ---")

    if not receipt_df.empty:
        receipt_items = sorted(receipt_df["item_name"].unique())
        print(f"\nReceipt item names ({len(receipt_items)} unique):")
        for name in receipt_items[:20]:
            print(f"  '{name}'")
        if len(receipt_items) > 20:
            print(f"  ... and {len(receipt_items) - 20} more")

        # Also show normalized names if available
        if "normalized_name" in receipt_df.columns:
            norm_items = sorted(
                receipt_df["normalized_name"].dropna().unique()
            )
            print(f"\nReceipt NORMALIZED names ({len(norm_items)} unique):")
            for name in norm_items[:20]:
                print(f"  '{name}'")
            if len(norm_items) > 20:
                print(f"  ... and {len(norm_items) - 20} more")

    if not pantry_df.empty:
        pantry_items = sorted(pantry_df["item_name"].unique())
        print(f"\nPantry item names ({len(pantry_items)} unique):")
        for name in pantry_items[:20]:
            print(f"  '{name}'")
        if len(pantry_items) > 20:
            print(f"  ... and {len(pantry_items) - 20} more")

    # ------------------------------------------------------------------
    # 4. Same food, different descriptions
    # ------------------------------------------------------------------
    # This is the KEY insight — the same physical food appears in both
    # sources but with very different names. Finding these matches
    # manually demonstrates why automated normalization is needed.
    print(f"\n--- SAME FOOD, DIFFERENT DESCRIPTIONS ---")
    print("(Examples of how the same food appears in each data source)\n")

    if not receipt_df.empty and not pantry_df.empty:
        # Use normalized_name from receipts to find matches with pantry item_name
        if "normalized_name" in receipt_df.columns:
            receipt_names = set(
                receipt_df["normalized_name"].dropna().str.lower().str.strip()
            )
        else:
            receipt_names = set(receipt_df["item_name"].str.lower().str.strip())

        pantry_names = set(pantry_df["item_name"].str.lower().str.strip())

        # Find items that appear in BOTH sources
        overlap = sorted(receipt_names & pantry_names)
        if overlap:
            print(f"Items found in BOTH sources ({len(overlap)} matches):")
            for name in overlap:
                # Find the raw receipt name for this normalized name
                if "normalized_name" in receipt_df.columns:
                    receipt_rows = receipt_df[
                        receipt_df["normalized_name"].str.lower().str.strip() == name
                    ]
                else:
                    receipt_rows = receipt_df[
                        receipt_df["item_name"].str.lower().str.strip() == name
                    ]

                pantry_rows = pantry_df[
                    pantry_df["item_name"].str.lower().str.strip() == name
                ]

                if not receipt_rows.empty and not pantry_rows.empty:
                    raw_receipt = receipt_rows.iloc[0]["item_name"]
                    pantry_name = pantry_rows.iloc[0]["item_name"]
                    print(f"  Receipt: '{raw_receipt}' -> Pantry: '{pantry_name}'")
        else:
            print("No exact matches found between receipt and pantry items.")
            print("This is expected — normalization (WS04) will bridge the gap.")

        # Items only in receipts (purchased but not in pantry scan)
        receipt_only_items = sorted(receipt_names - pantry_names)
        if receipt_only_items:
            print(f"\nPurchased but NOT in pantry ({len(receipt_only_items)}):")
            for name in receipt_only_items[:15]:
                print(f"  {name}")
            if len(receipt_only_items) > 15:
                print(f"  ... and {len(receipt_only_items) - 15} more")

        # Items only in pantry (in pantry but not recently purchased)
        pantry_only_items = sorted(pantry_names - receipt_names)
        if pantry_only_items:
            print(f"\nIn pantry but NOT recently purchased ({len(pantry_only_items)}):")
            for name in pantry_only_items[:15]:
                print(f"  {name}")
            if len(pantry_only_items) > 15:
                print(f"  ... and {len(pantry_only_items) - 15} more")

    # ------------------------------------------------------------------
    # 5. Category comparison
    # ------------------------------------------------------------------
    print(f"\n--- CATEGORY COMPARISON ---")

    receipt_cats = set()
    pantry_cats = set()

    if not receipt_df.empty and "category" in receipt_df.columns:
        receipt_cats = set(receipt_df["category"].dropna().unique())
        print(f"\nReceipt categories ({len(receipt_cats)}):")
        # value_counts() shows how many items fall into each category
        cat_counts = receipt_df["category"].value_counts()
        for cat, count in cat_counts.items():
            print(f"  {cat}: {count} items")

    if not pantry_df.empty and "category" in pantry_df.columns:
        pantry_cats = set(pantry_df["category"].dropna().unique())
        print(f"\nPantry categories ({len(pantry_cats)}):")
        cat_counts = pantry_df["category"].value_counts()
        for cat, count in cat_counts.items():
            print(f"  {cat}: {count} items")

    shared_cats = receipt_cats & pantry_cats
    print(f"\nShared categories: {sorted(shared_cats)}")
    if receipt_cats - pantry_cats:
        print(f"Receipt-only categories: {sorted(receipt_cats - pantry_cats)}")
    if pantry_cats - receipt_cats:
        print(f"Pantry-only categories: {sorted(pantry_cats - receipt_cats)}")

    # ------------------------------------------------------------------
    # 6. Educational commentary — the normalization challenge
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("WHY THESE DIFFERENCES EXIST")
    print("=" * 70)
    print("""
These two data sources describe the same real-world food, but they come from
different collection methods:

  RECEIPTS are captured from store POS systems. Names are abbreviated store
  codes (e.g., 'Greenwise Hmstyle Meatbal Ft'). They include purchase prices
  and store info, but no storage details.

  PANTRY SCANS are captured by photographing your kitchen. Names are clean and
  human-readable (e.g., 'meatball'). They include storage location and
  condition, but no price info.

THE NORMALIZATION CHALLENGE (coming in WS04):
  To answer "do I have the ingredients for this recipe?", we need to match
  receipt and pantry items to recipe ingredients. But:
  - 'Greenwise Hmstyle Meatbal Ft' (receipt)
  - 'meatball' (pantry)
  - 'meatballs' (recipe ingredient)
  ...are all the SAME food described three different ways!

  WS04 will solve this by building a normalization pipeline that maps all
  these variations to a single canonical name, creating a unified view
  across all data sources.
""")

    print("=" * 70)
    print("Comparison complete.")


if __name__ == "__main__":
    compare_data()
