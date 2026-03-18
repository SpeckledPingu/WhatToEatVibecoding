"""
build_inventory.py — Main normalization pipeline: build the unified ActiveInventory.

WHAT THIS SCRIPT DOES
This is the heart of the data normalization workstream. It:
  1. Reads ALL raw data from the Receipt and PantryItem tables
  2. Normalizes every food name using the rules in config/normalization_mappings.json
  3. Assigns categories and creates join keys for cross-source matching
  4. Looks up shelf life to calculate expiration dates
  5. Writes everything into the unified ActiveInventory table
  6. Prints a detailed report showing every transformation

THE TRANSFORMATION PIPELINE
  raw data → cleaned → normalized → categorized → keyed → enriched → stored

This follows the ETL pattern (Extract, Transform, Load) used in professional
data engineering:
  - EXTRACT: Read from Receipt and PantryItem tables
  - TRANSFORM: Normalize names, assign categories, create join keys, calc expiration
  - LOAD: Write into ActiveInventory table

WHY WE REBUILD INSTEAD OF INCREMENTALLY UPDATE
Every time this script runs, it drops and recreates the ActiveInventory table.
This might seem wasteful, but it has important advantages:
  - SIMPLICITY: No complex "what changed?" logic needed
  - CORRECTNESS: Impossible for stale or orphaned records to accumulate
  - REPRODUCIBILITY: Same inputs always produce the same output
  - DEBUGGABILITY: If results look wrong, fix the config and re-run
For a personal food inventory (hundreds of items), the full rebuild takes
under a second. In larger systems, you'd use incremental updates for
performance, but the trade-off isn't worth the complexity here.

THIS PATTERN APPLIES BEYOND FOOD DATA
Any time you combine data from multiple sources, you face the same challenges:
different names for the same thing, different formats, missing fields. The
normalization pipeline pattern — clean → standardize → enrich → store — works
for customer records, product catalogs, medical data, and many other domains.

RUN IT:
    uv run python -m src.normalization.build_inventory
"""

from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select, SQLModel

from src.database import create_db_and_tables, get_engine
from src.models.inventory import ActiveInventory
from src.models.normalization import NormalizationMapping
from src.models.receipt import Receipt
from src.models.pantry import PantryItem
from src.models.shelf_life import FoodShelfLife
from src.normalization.food_names import (
    normalize_food_name,
    extract_food_category,
    load_config_to_sql,
)
from src.normalization.join_keys import create_join_key


def _lookup_shelf_life(
    session: Session,
    normalized_name: str,
    category: str,
) -> tuple[int, bool]:
    """
    Look up how many weeks a food item lasts, using the FoodShelfLife table.

    LOOKUP STRATEGY (most specific → least specific):
    1. Check for an exact match on the normalized food name.
    2. If no match, check for a category default (e.g., "protein (default)").
    3. If still no match, use a hardcoded fallback of 4 weeks.

    This layered approach means specific foods (like "chicken breast" = 1 week)
    get precise shelf lives, while unknown foods still get a reasonable estimate
    based on their category (like "protein" = 1 week for fridge).

    Parameters:
        session: Active database session.
        normalized_name: The canonical food name to look up.
        category: The food category (used for default fallback).

    Returns:
        A tuple of (shelf_life_weeks, used_fallback). used_fallback is True
        when no specific or category match was found and the 4-week default
        was used. This helps the report distinguish genuine 4-week items
        from items with missing shelf life data.
    """
    # Try exact match first
    result = session.exec(
        select(FoodShelfLife).where(FoodShelfLife.food_name == normalized_name)
    ).first()
    if result:
        return result.shelf_life_weeks, False

    # Try category default
    default_name = f"{category} (default)"
    result = session.exec(
        select(FoodShelfLife).where(FoodShelfLife.food_name == default_name)
    ).first()
    if result:
        return result.shelf_life_weeks, False

    # Ultimate fallback — 4 weeks is a conservative general estimate
    return 4, True


def build_active_inventory():
    """
    Build the unified ActiveInventory table from Receipt and PantryItem data.

    This is the main function that orchestrates the entire normalization pipeline.
    It processes every record from both source tables, normalizes them, and
    produces a single unified view with consistent naming, categories, join keys,
    and expiration dates.

    The function prints a detailed report showing every transformation, which
    is invaluable for debugging and understanding what the normalization did.
    """
    print("=" * 70)
    print("BUILDING UNIFIED ACTIVE INVENTORY")
    print("=" * 70)

    engine = get_engine()
    create_db_and_tables(engine)

    # ------------------------------------------------------------------
    # Step 0: Load normalization config into SQL table
    # ------------------------------------------------------------------
    # This ensures the NormalizationMapping table reflects the latest
    # config file before we start building the inventory.
    print("\nStep 0: Syncing normalization config to SQL table...")
    load_config_to_sql()

    # ------------------------------------------------------------------
    # Step 1: Drop and recreate the ActiveInventory table
    # ------------------------------------------------------------------
    # This is the REBUILD pattern — start fresh every time.
    # We drop the table and recreate it rather than deleting rows, which
    # also handles any schema changes to the model.
    print("\nStep 1: Dropping and recreating ActiveInventory table...")
    ActiveInventory.metadata.drop_all(engine, tables=[ActiveInventory.__table__])
    ActiveInventory.metadata.create_all(engine, tables=[ActiveInventory.__table__])
    print("  Table recreated (clean slate)")

    today = date.today()
    inventory_records = []
    normalization_log = []  # Track transformations for the report

    with Session(engine) as session:
        # ------------------------------------------------------------------
        # Step 2: Process all Receipt records
        # ------------------------------------------------------------------
        print("\nStep 2: Processing receipt records...")
        receipts = session.exec(select(Receipt)).all()
        print(f"  Found {len(receipts)} receipt records")

        receipt_no_shelf_life = []

        for receipt in receipts:
            # --- Normalize the food name ---
            # Receipts have a pre-normalized name from AI extraction.
            # We use that as a head start, then run through our pipeline
            # for consistency with canonical names.
            normalized = normalize_food_name(
                receipt.item_name,
                pre_normalized=receipt.normalized_name,
            )

            # --- Determine category ---
            # Use the receipt's category if valid, otherwise look it up
            category = extract_food_category(normalized, receipt.category)

            # --- Create join key ---
            join_key = create_join_key(normalized, category)

            # --- Look up shelf life and calculate expiration ---
            shelf_life_weeks, used_fallback = _lookup_shelf_life(
                session, normalized, category
            )
            acquired = receipt.purchase_date or today
            expiration = acquired + timedelta(weeks=shelf_life_weeks)
            is_expired = expiration < today

            if used_fallback:
                receipt_no_shelf_life.append(normalized)

            # --- Build the unified record ---
            record = ActiveInventory(
                item_name=normalized,
                original_name=receipt.item_name,
                category=category,
                join_key=join_key,
                quantity=float(receipt.quantity),
                unit="whole",  # Receipts typically count items
                source="receipt",
                source_id=receipt.id,
                source_table="receipt",
                date_acquired=acquired,
                expiration_date=expiration,
                is_expired=is_expired,
            )
            inventory_records.append(record)

            # Log the transformation
            normalization_log.append({
                "source": "receipt",
                "original": receipt.item_name,
                "pre_normalized": receipt.normalized_name or "",
                "normalized": normalized,
                "category": category,
                "join_key": join_key,
                "shelf_life_weeks": shelf_life_weeks,
                "is_expired": is_expired,
            })

        # ------------------------------------------------------------------
        # Step 3: Process all Pantry records
        # ------------------------------------------------------------------
        print("\nStep 3: Processing pantry records...")
        pantry_items = session.exec(select(PantryItem)).all()
        print(f"  Found {len(pantry_items)} pantry records")

        pantry_no_shelf_life = []

        for item in pantry_items:
            # --- Normalize the food name ---
            # Pantry items are already fairly clean (from AI extraction),
            # but we still run normalization for alias resolution.
            # Pantry has no separate normalized_name column — item_name
            # IS already the normalized form.
            normalized = normalize_food_name(item.item_name)

            # --- Determine category ---
            category = extract_food_category(normalized, item.category)

            # --- Create join key ---
            join_key = create_join_key(normalized, category)

            # --- Look up shelf life and calculate expiration ---
            shelf_life_weeks, used_fallback = _lookup_shelf_life(
                session, normalized, category
            )
            acquired = item.date_inventoried or today
            expiration = acquired + timedelta(weeks=shelf_life_weeks)
            is_expired = expiration < today

            if used_fallback:
                pantry_no_shelf_life.append(normalized)

            # --- Build the unified record ---
            record = ActiveInventory(
                item_name=normalized,
                original_name=item.item_name,
                category=category,
                join_key=join_key,
                quantity=item.quantity,
                unit=item.unit or "whole",
                source="pantry",
                source_id=item.id,
                source_table="pantryitem",
                date_acquired=acquired,
                expiration_date=expiration,
                is_expired=is_expired,
            )
            inventory_records.append(record)

            # Log the transformation
            normalization_log.append({
                "source": "pantry",
                "original": item.item_name,
                "pre_normalized": "",
                "normalized": normalized,
                "category": category,
                "join_key": join_key,
                "shelf_life_weeks": shelf_life_weeks,
                "is_expired": is_expired,
            })

        # ------------------------------------------------------------------
        # Step 4: Insert all records into ActiveInventory
        # ------------------------------------------------------------------
        print("\nStep 4: Inserting unified inventory records...")
        for record in inventory_records:
            session.add(record)
        session.commit()
        print(f"  Inserted {len(inventory_records)} records")

    # ------------------------------------------------------------------
    # Step 5: Print the normalization report
    # ------------------------------------------------------------------
    _print_normalization_report(
        normalization_log,
        receipt_no_shelf_life,
        pantry_no_shelf_life,
        len(receipts),
        len(pantry_items),
    )


def _print_normalization_report(
    log: list[dict],
    receipt_missing_shelf: list[str],
    pantry_missing_shelf: list[str],
    receipt_count: int,
    pantry_count: int,
):
    """
    Print a detailed report of the normalization results.

    This report is the primary way to understand and debug the normalization
    pipeline. It shows every transformation, highlights potential issues,
    and provides actionable suggestions for improving the config.
    """
    print()
    print("=" * 70)
    print("NORMALIZATION REPORT")
    print("=" * 70)

    # --- Source summary ---
    print(f"\nRecords processed:")
    print(f"  Receipts: {receipt_count}")
    print(f"  Pantry:   {pantry_count}")
    print(f"  Total:    {receipt_count + pantry_count}")

    # --- Transformation table ---
    # Show unique transformations (deduplicate by original name)
    print(f"\nName transformations (original → normalized → join key):")
    print(f"  {'Source':<8} {'Original Name':<35} {'Normalized':<20} {'Join Key'}")
    print(f"  {'-'*8} {'-'*35} {'-'*20} {'-'*30}")

    seen = set()
    for entry in log:
        key = (entry["source"], entry["original"])
        if key in seen:
            continue
        seen.add(key)

        original_display = entry["original"][:33]
        if len(entry["original"]) > 33:
            original_display += ".."

        print(
            f"  {entry['source']:<8} "
            f"{original_display:<35} "
            f"{entry['normalized']:<20} "
            f"{entry['join_key']}"
        )

    # --- Missing shelf life ---
    all_missing = set(receipt_missing_shelf + pantry_missing_shelf)
    if all_missing:
        print(f"\nItems using DEFAULT shelf life (4 weeks) — consider adding to config:")
        print("  (Add these to config/normalization_mappings.json > shelf_life_overrides)")
        for name in sorted(all_missing):
            print(f"    - {name}")

    # --- Expired items ---
    expired = [e for e in log if e["is_expired"]]
    if expired:
        print(f"\nExpired items ({len(expired)}):")
        for entry in expired:
            print(f"  {entry['normalized']} (from {entry['source']}: {entry['original'][:40]})")
    else:
        print(f"\nNo expired items found.")

    # --- Unique join keys ---
    unique_keys = set(e["join_key"] for e in log)
    print(f"\nUnique join keys: {len(unique_keys)} distinct food items")
    print("  (Items from different sources with the same join key represent the same food)")

    # --- Active vs expired ---
    active = [e for e in log if not e["is_expired"]]
    print(f"\nInventory summary:")
    print(f"  Active (not expired): {len(active)} records")
    print(f"  Expired:              {len(expired)} records")
    print(f"  Total:                {len(log)} records")

    # --- Join key overlaps (items in BOTH sources) ---
    receipt_keys = set(e["join_key"] for e in log if e["source"] == "receipt")
    pantry_keys = set(e["join_key"] for e in log if e["source"] == "pantry")
    overlap = receipt_keys & pantry_keys

    if overlap:
        print(f"\nItems in BOTH receipt AND pantry ({len(overlap)}):")
        print("  (These items were both purchased recently and found in inventory)")
        for key in sorted(overlap):
            print(f"    {key}")

    print(f"\n{'=' * 70}")
    print("Build complete. Run the normalization quality report for deeper analysis:")
    print("  uv run python -m src.analytics.normalization_report")


if __name__ == "__main__":
    build_active_inventory()
