"""
seed_shelf_life.py — Populate the FoodShelfLife reference table from config.

HOW THIS SCRIPT WORKS
1. Reads shelf life data from config/normalization_mappings.json:
   - shelf_life_defaults: default shelf life by category and storage type
   - shelf_life_overrides: specific shelf life for individual food items
2. Also scans actual receipt and pantry CSV files to find food items that
   aren't yet covered in the config
3. Inserts shelf life records into the database (upserts — safe to re-run)
4. Prints a report of what was seeded and what's missing from config

WHY SHELF LIFE DATA LIVES IN A CONFIG FILE
This is the "configuration over code" pattern. By putting shelf life values in
a JSON file instead of hardcoding them in Python:
  - Students can customize values by editing JSON (no Python knowledge needed)
  - The same data can serve as both a config file AND a SQL table
  - Adding new foods doesn't require code changes
  - Values are visible and auditable in one place

THE SEED DATA PATTERN
"Seeding" a database means populating it with initial reference data that the
application needs to function. Unlike user data (which grows organically through
usage), seed data is predefined and loaded programmatically. This script is
designed to be re-run safely — if a record already exists, it's updated rather
than duplicated.

RUN IT:
    uv run python scripts/seed_shelf_life.py
"""

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Add project root to sys.path so we can import src modules
# ---------------------------------------------------------------------------
# When running a script from the scripts/ directory, Python doesn't
# automatically know about the src/ package. Adding the project root to
# sys.path fixes this. There are fancier ways to handle this (package
# installation, pyproject.toml configuration), but this is the simplest
# approach for a learning project.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.shelf_life import FoodShelfLife

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
CONFIG_PATH = PROJECT_ROOT / "config" / "normalization_mappings.json"
RECEIPTS_DIR = PROJECT_ROOT / "data" / "receipts"
PANTRY_DIR = PROJECT_ROOT / "data" / "pantry"


def load_config() -> dict:
    """Load the normalization configuration file."""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def find_category_for_food(food_name: str, food_categories: dict) -> str:
    """
    Look up which category a food item belongs to.

    HOW THIS WORKS
    The config's food_categories maps each category to a list of example foods.
    We search through all categories looking for the food name. If not found,
    we return 'other' as a fallback.

    Parameters:
        food_name: The normalized food name to look up
        food_categories: The food_categories dict from config

    Returns:
        The category name, or 'other' if not found.
    """
    food_lower = food_name.lower()
    for category, foods in food_categories.items():
        if category.startswith("_"):
            continue
        if isinstance(foods, list) and food_lower in [f.lower() for f in foods]:
            return category
    return "other"


def seed_from_defaults(config: dict, session: Session, stats: dict):
    """
    Create shelf life records from the category defaults in config.

    These are broad defaults: "protein in the fridge lasts 1 week." They serve
    as a fallback when a specific food item isn't in the overrides table.

    We create one record per category-storage combination, using the category
    name as the food_name with a "(default)" suffix so it's clear these are
    fallback values, not specific foods.
    """
    defaults = config.get("shelf_life_defaults", {})
    if not defaults:
        print("  No shelf_life_defaults found in config.")
        return

    for category, storage_map in defaults.items():
        if category.startswith("_"):
            continue

        for storage_type, weeks in storage_map.items():
            # Skip null values (e.g., protein has no pantry shelf life)
            if weeks is None:
                continue

            food_name = f"{category} (default)"

            # Check if this default already exists
            existing = session.exec(
                select(FoodShelfLife).where(
                    FoodShelfLife.food_name == food_name,
                    FoodShelfLife.storage_type == storage_type,
                )
            ).first()

            if existing:
                # Update if values changed
                existing.shelf_life_weeks = weeks
                existing.category = category
                session.add(existing)
                stats["updated"] += 1
            else:
                record = FoodShelfLife(
                    food_name=food_name,
                    category=category,
                    shelf_life_weeks=weeks,
                    storage_type=storage_type,
                    notes=f"Default for all {category} items in {storage_type}",
                )
                session.add(record)
                stats["new"] += 1

            print(f"    {food_name} ({storage_type}): {weeks} weeks")


def seed_from_overrides(config: dict, session: Session, stats: dict):
    """
    Create shelf life records from the per-item overrides in config.

    These are specific: "chicken breast in the fridge lasts 1 week." They
    take precedence over category defaults when looking up a specific food.
    """
    overrides = config.get("shelf_life_overrides", {})
    food_categories = config.get("food_categories", {})

    if not overrides:
        print("  No shelf_life_overrides found in config.")
        return

    for food_name, info in overrides.items():
        if food_name.startswith("_"):
            continue

        weeks = info["weeks"]
        storage_type = info["storage"]
        category = find_category_for_food(food_name, food_categories)

        # Check if this override already exists
        existing = session.exec(
            select(FoodShelfLife).where(
                FoodShelfLife.food_name == food_name,
                FoodShelfLife.storage_type == storage_type,
            )
        ).first()

        if existing:
            existing.shelf_life_weeks = weeks
            existing.category = category
            session.add(existing)
            stats["updated"] += 1
        else:
            record = FoodShelfLife(
                food_name=food_name,
                category=category,
                shelf_life_weeks=weeks,
                storage_type=storage_type,
                notes=f"Specific override for {food_name}",
            )
            session.add(record)
            stats["new"] += 1

        print(f"    {food_name} ({storage_type}): {weeks} weeks [{category}]")


def find_foods_in_data() -> set[str]:
    """
    Scan receipt and pantry CSV files to find all unique food names.

    This lets us report which foods in the actual data don't have shelf life
    entries in the config — a hint for students about what to add.

    Returns:
        A set of lowercase food names found across all data files.
    """
    food_names = set()

    # Scan receipt files — use normalized_name if available, else item_name
    if RECEIPTS_DIR.exists():
        for csv_file in RECEIPTS_DIR.glob("*.csv"):
            try:
                df = pd.read_csv(csv_file)
                if "normalized_name" in df.columns:
                    names = df["normalized_name"].dropna().str.lower().str.strip()
                elif "item_name" in df.columns:
                    names = df["item_name"].dropna().str.lower().str.strip()
                else:
                    continue
                food_names.update(names.unique())
            except Exception as e:
                print(f"  Warning: Could not read {csv_file.name}: {e}")

    # Scan pantry files
    if PANTRY_DIR.exists():
        for csv_file in PANTRY_DIR.glob("*.csv"):
            try:
                df = pd.read_csv(csv_file)
                if "item_name" in df.columns:
                    names = df["item_name"].dropna().str.lower().str.strip()
                    food_names.update(names.unique())
            except Exception as e:
                print(f"  Warning: Could not read {csv_file.name}: {e}")

    return food_names


def seed_shelf_life():
    """
    Main function — seed the FoodShelfLife table from config and report gaps.
    """
    print("=" * 70)
    print("SHELF LIFE TABLE SEEDING")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Load config
    # ------------------------------------------------------------------
    config = load_config()
    print(f"\nLoaded config from: {CONFIG_PATH}")

    # ------------------------------------------------------------------
    # Step 2: Set up database
    # ------------------------------------------------------------------
    engine = get_engine()
    create_db_and_tables(engine)

    stats = {"new": 0, "updated": 0}

    with Session(engine) as session:
        # ------------------------------------------------------------------
        # Step 3: Seed category defaults
        # ------------------------------------------------------------------
        print("\nSeeding category defaults:")
        seed_from_defaults(config, session, stats)

        # ------------------------------------------------------------------
        # Step 4: Seed per-item overrides
        # ------------------------------------------------------------------
        print("\nSeeding per-item overrides:")
        seed_from_overrides(config, session, stats)

        session.commit()

    # ------------------------------------------------------------------
    # Step 5: Find foods in data that lack config entries
    # ------------------------------------------------------------------
    print("\nScanning data files for food items...")
    data_foods = find_foods_in_data()
    print(f"  Found {len(data_foods)} unique food names in data files")

    # Check which data foods have shelf life overrides
    overrides = config.get("shelf_life_overrides", {})
    override_names = {k.lower() for k in overrides.keys() if not k.startswith("_")}

    missing = sorted(data_foods - override_names)
    if missing:
        print(f"\n  Foods in your data WITHOUT specific shelf life overrides ({len(missing)}):")
        print("  (These will use category defaults. Add them to")
        print("  config/normalization_mappings.json > shelf_life_overrides for precision.)")
        for name in missing:
            print(f"    - {name}")
    else:
        print("\n  All foods in your data have specific shelf life overrides!")

    # ------------------------------------------------------------------
    # Step 6: Summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("SEEDING SUMMARY")
    print("=" * 70)
    print(f"  New records added:  {stats['new']}")
    print(f"  Existing updated:   {stats['updated']}")
    print(f"  Foods in data:      {len(data_foods)}")
    print(f"  Missing overrides:  {len(missing)}")
    print(f"\nDatabase: {engine.url}")
    print("Done!")


if __name__ == "__main__":
    seed_shelf_life()
