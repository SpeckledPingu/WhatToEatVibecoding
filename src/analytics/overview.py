"""
overview.py — "State of the Kitchen" report using pandas.

WHAT THIS SCRIPT DOES
This is a comprehensive overview of everything in your food database — recipes,
inventory, and recipe matching results — presented as a formatted report. It
demonstrates many core pandas operations:

  - Loading SQL data into DataFrames (pd.read_sql / model_dump)
  - Filtering with boolean conditions (df[df["column"] == value])
  - value_counts() for frequency analysis
  - groupby() for aggregation
  - merge() for combining DataFrames
  - Working with JSON fields stored in columns (explode, json.loads)

Think of this as the "dashboard" version of your data — a quick glance at the
state of your kitchen, what you can cook, and what you might want to buy.

RUN IT:
    uv run python -m src.analytics.overview
"""

import json
from datetime import date, timedelta

import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.inventory import ActiveInventory
from src.models.recipe import Recipe
from src.models.recipe_matching import RecipeIngredientMatch, RecipeMatchSummary
from src.models.receipt import Receipt


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_table_to_dataframe(model_class) -> pd.DataFrame:
    """
    Load all rows from a SQLModel table into a pandas DataFrame.

    HOW THIS WORKS
    1. Open a database session (a conversation with the database).
    2. Run a SELECT * query using SQLModel's select() function.
    3. Convert each row object to a dictionary with model_dump().
    4. Create a DataFrame from the list of dictionaries.

    This pattern works for ANY SQLModel table — just pass the class.

    Parameters:
        model_class: The SQLModel class (e.g., Recipe, Receipt).

    Returns:
        A pandas DataFrame with one row per database record.
    """
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        rows = session.exec(select(model_class)).all()
        if not rows:
            return pd.DataFrame()
        # model_dump() converts a SQLModel object to a plain dict
        # pd.DataFrame() turns a list of dicts into a table
        return pd.DataFrame([row.model_dump() for row in rows])


def run_overview():
    """
    Print a comprehensive "State of the Kitchen" report.

    This function loads data from all major tables, computes summary statistics
    using pandas, and prints a formatted report. Each section demonstrates a
    different pandas technique.
    """
    # ------------------------------------------------------------------
    # Load all data into DataFrames
    # ------------------------------------------------------------------
    # Each load_table_to_dataframe call runs a SELECT * and converts the
    # results into a DataFrame. We load all tables upfront so the rest of
    # the script works with in-memory DataFrames (fast!) rather than making
    # repeated database queries.
    recipes_df = load_table_to_dataframe(Recipe)
    inventory_df = load_table_to_dataframe(ActiveInventory)
    match_detail_df = load_table_to_dataframe(RecipeIngredientMatch)
    match_summary_df = load_table_to_dataframe(RecipeMatchSummary)
    receipts_df = load_table_to_dataframe(Receipt)

    print("=" * 70)
    print("       WHAT TO EAT: Kitchen Overview")
    print("=" * 70)

    # ==================================================================
    # RECIPES SECTION
    # ==================================================================
    print("\n📖 RECIPES")

    if recipes_df.empty:
        print("  No recipes found. Run: uv run python -m src.ingestion.recipes")
    else:
        # len(df) returns the number of rows — one row per recipe
        print(f"  Total: {len(recipes_df)} recipes")

        # value_counts() counts occurrences of each unique value in a column.
        # It returns a Series sorted by frequency (most common first).
        format_counts = recipes_df["source_format"].value_counts()
        format_str = ", ".join(
            f"{count} {fmt}" for fmt, count in format_counts.items()
        )
        print(f"  By format: {format_str}")

        # fillna() replaces NaN (missing/null values) with a default string.
        # Without it, recipes missing weather tags would be silently excluded
        # from the count.
        temp_counts = recipes_df["weather_temp"].fillna("(unset)").value_counts()
        temp_str = " | ".join(
            f"{count} {temp}" for temp, count in temp_counts.items()
        )
        print(f"  By weather temp: {temp_str}")

        cond_counts = recipes_df["weather_condition"].fillna("(unset)").value_counts()
        cond_str = " | ".join(
            f"{count} {cond}" for cond, count in cond_counts.items()
        )
        print(f"  By weather condition: {cond_str}")

        # .apply() runs a function on every value in a column.
        # Here we count the number of ingredients per recipe (len of each list),
        # then take the mean across all recipes.
        recipes_df["ingredient_count"] = recipes_df["ingredients"].apply(
            lambda x: len(x) if isinstance(x, list) else 0
        )
        avg_ing = recipes_df["ingredient_count"].mean()
        print(f"  Average ingredients per recipe: {avg_ing:.1f}")

    # ==================================================================
    # INVENTORY SECTION
    # ==================================================================
    print("\n📦 INVENTORY")

    if inventory_df.empty:
        print("  No inventory found. Run normalization pipeline first:")
        print("  uv run python -m src.normalization.build_inventory")
    else:
        # Filter active items: not expired
        # Boolean indexing: df[condition] returns only rows where condition is True.
        # The ~ operator negates: ~df["is_expired"] means "NOT expired".
        active_df = inventory_df[~inventory_df["is_expired"]]
        print(f"  Total active items: {len(active_df)}")

        # value_counts() on the category column shows the distribution.
        # .head(8) limits output to the top 8 categories.
        cat_counts = active_df["category"].value_counts()
        cat_parts = [f"{count} {cat}" for cat, count in cat_counts.head(8).items()]
        print(f"  By category: {', '.join(cat_parts)}")
        if len(cat_counts) > 8:
            print(f"    ... and {len(cat_counts) - 8} more categories")

        # Find items expiring within 7 days
        # We compare the expiration_date column against today + 7 days.
        # pandas automatically handles date comparison when the column is a date type.
        today = date.today()
        week_from_now = today + timedelta(days=7)

        # dropna() removes rows where expiration_date is null (can't compare null dates)
        has_expiry = active_df.dropna(subset=["expiration_date"]).copy()
        # Ensure expiration_date is a date type for comparison
        has_expiry["expiration_date"] = pd.to_datetime(
            has_expiry["expiration_date"]
        ).dt.date

        expiring_soon = has_expiry[has_expiry["expiration_date"] <= week_from_now]
        print(f"  Expiring this week: {len(expiring_soon)} items")

        # Count already-expired items
        expired_df = inventory_df[inventory_df["is_expired"]]
        print(f"  Already expired: {len(expired_df)} items")

    # ==================================================================
    # RECIPE MATCHING SECTION
    # ==================================================================
    print("\n🍳 RECIPE MATCHING")

    if match_summary_df.empty:
        print("  No matching data found. Run:")
        print("  uv run python -m src.normalization.build_recipe_matching")
    else:
        total_recipes = len(match_summary_df)

        # Boolean filtering: select rows where is_fully_makeable is True
        fully_makeable = match_summary_df[
            match_summary_df["is_fully_makeable"] == True  # noqa: E712
        ]
        makeable_count = len(fully_makeable)
        makeable_pct = (makeable_count / total_recipes * 100) if total_recipes > 0 else 0
        print(f"  Fully makeable: {makeable_count} recipes ({makeable_pct:.0f}%)")

        # Filter for recipes missing 1-2 ingredients using between()
        # between(1, 2) is shorthand for (col >= 1) & (col <= 2)
        close_df = match_summary_df[
            match_summary_df["missing_ingredients"].between(1, 2)
        ]
        close_count = len(close_df)
        close_pct = (close_count / total_recipes * 100) if total_recipes > 0 else 0
        print(f"  Missing 1-2 ingredients: {close_count} recipes ({close_pct:.0f}%)")

        # Filter for recipes missing 3+ ingredients
        far_df = match_summary_df[match_summary_df["missing_ingredients"] >= 3]
        far_count = len(far_df)
        far_pct = (far_count / total_recipes * 100) if total_recipes > 0 else 0
        print(f"  Missing 3+: {far_count} recipes ({far_pct:.0f}%)")

    # ==================================================================
    # TOP 10 MOST COMMON RECIPE INGREDIENTS
    # ==================================================================
    print("\n🔝 TOP 10 MOST COMMON RECIPE INGREDIENTS")

    if not recipes_df.empty:
        # STEP 1: Extract ingredient names from JSON lists.
        # Each recipe's "ingredients" column is a list of dicts like:
        #   [{"name": "flour", "quantity": 2, ...}, {"name": "sugar", ...}]
        # We use .apply() to extract just the names into a list of strings.
        ingredient_names = recipes_df["ingredients"].apply(
            lambda ings: [
                ing["name"] for ing in ings
                if isinstance(ing, dict) and "name" in ing
            ]
        )

        # STEP 2: explode() the lists into individual rows.
        # Before: one row per recipe, each containing a list of ingredient names
        # After:  one row per ingredient, linked back to the recipe index
        # This is like "unzipping" a nested structure into flat rows.
        exploded = ingredient_names.explode()

        # STEP 3: value_counts() counts how many recipes each ingredient appears in.
        # .head(10) limits to the top 10.
        top_ingredients = exploded.value_counts().head(10)

        for rank, (ingredient, count) in enumerate(top_ingredients.items(), 1):
            print(f"  {rank:2d}. {ingredient} (appears in {count} recipes)")
    else:
        print("  No recipe data available.")

    # ==================================================================
    # MOST COMMONLY MISSING INGREDIENTS
    # ==================================================================
    print("\n🛒 MOST COMMONLY MISSING INGREDIENTS")

    if not match_detail_df.empty:
        # Filter to ingredients that are NOT available (missing from inventory).
        # Then count how many recipes each missing ingredient appears in.
        missing_df = match_detail_df[
            match_detail_df["is_available"] == False  # noqa: E712
        ]

        if not missing_df.empty:
            # value_counts() on the ingredient name tells us which ingredients
            # are missing most frequently across recipes.
            missing_counts = missing_df["ingredient_name"].value_counts().head(10)
            for rank, (ingredient, count) in enumerate(missing_counts.items(), 1):
                print(f"  {rank:2d}. {ingredient} (missing for {count} recipes)")
        else:
            print("  No missing ingredients — you can make everything!")
    else:
        print("  No matching data available.")

    # ==================================================================
    # INVENTORY ITEMS NOT IN ANY RECIPE
    # ==================================================================
    print("\n⚠️  INVENTORY NOT IN ANY RECIPE")

    if not inventory_df.empty and not match_detail_df.empty:
        # Get all unique join keys from inventory (what you have)
        inventory_keys = set(inventory_df["join_key"].unique())

        # Get all unique join keys from recipe ingredients (what recipes need)
        recipe_keys = set(match_detail_df["ingredient_join_key"].unique())

        # Set difference: items you have that NO recipe uses
        unused_keys = inventory_keys - recipe_keys

        if unused_keys:
            # Map join keys back to item names for display
            # We filter inventory_df to rows with unused keys and get unique names
            unused_items = inventory_df[
                inventory_df["join_key"].isin(unused_keys)
            ]["item_name"].unique()
            unused_sorted = sorted(unused_items)
            print(f"  {', '.join(unused_sorted)}")
            print(f"  ({len(unused_sorted)} items aren't used by any of your recipes)")
        else:
            print("  All inventory items are used in at least one recipe!")
    else:
        print("  Need both inventory and matching data for this analysis.")

    # ==================================================================
    # RECIPE INGREDIENTS NOT IN INVENTORY
    # ==================================================================
    print("\n🔍 RECIPE INGREDIENTS NOT IN INVENTORY")

    if not match_detail_df.empty:
        # Find ingredients that appear in recipes but are NOT in inventory
        missing_df = match_detail_df[
            match_detail_df["is_available"] == False  # noqa: E712
        ]
        if not missing_df.empty:
            # Get unique missing ingredient names and sort them
            missing_names = sorted(missing_df["ingredient_name"].unique())
            print(f"  {', '.join(missing_names)}")
            print(f"  ({len(missing_names)} ingredients — consider buying these to unlock more recipes)")
        else:
            print("  You have everything! All recipe ingredients are in stock.")
    else:
        print("  No matching data available.")

    print(f"\n{'=' * 70}")
    print("Run individual analytics for deeper analysis:")
    print("  uv run python -m src.analytics.purchase_patterns")
    print("  uv run python -m src.analytics.food_waste")
    print("  uv run python -m src.analytics.expiration_priority")


# ---------------------------------------------------------------------------
# Main entry point — run the overview when executed directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_overview()
