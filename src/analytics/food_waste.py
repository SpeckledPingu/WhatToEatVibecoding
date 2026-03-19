"""
food_waste.py — Estimate food waste risk and suggest recipes to reduce it.

WHY FOOD WASTE MATTERS
About 30-40% of food in the US is wasted — that's roughly $1,500 per household
per year. The biggest cause at home? Forgetting what's in your fridge until it
expires. This script tackles that by:

  1. Finding items that are already expired
  2. Identifying items about to expire with no matching recipe
  3. Suggesting recipes that would use at-risk ingredients
  4. Calculating an overall "waste risk" score

REAL-WORLD APPLICATIONS
This same analysis pattern is used by:
  - Grocery stores: Markdown pricing for items nearing expiration
  - Restaurants: Daily specials built around what needs to be used
  - Food banks: Prioritizing distribution of soon-to-expire donations
  - Meal kit companies: Selecting recipes based on ingredient shelf life
  - Smart fridges: Tracking contents and suggesting meals (the future!)

RUN IT:
    uv run python -m src.analytics.food_waste
"""

from datetime import date, timedelta

import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.inventory import ActiveInventory
from src.models.receipt import Receipt
from src.models.recipe_matching import RecipeIngredientMatch, RecipeMatchSummary


def load_inventory() -> pd.DataFrame:
    """Load all inventory items into a DataFrame."""
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        rows = session.exec(select(ActiveInventory)).all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in rows])


def load_receipts() -> pd.DataFrame:
    """Load all receipts into a DataFrame (for price lookups)."""
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        rows = session.exec(select(Receipt)).all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in rows])


def load_match_detail() -> pd.DataFrame:
    """Load recipe ingredient match detail into a DataFrame."""
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        rows = session.exec(select(RecipeIngredientMatch)).all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in rows])


def load_match_summary() -> pd.DataFrame:
    """Load recipe match summaries into a DataFrame."""
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        rows = session.exec(select(RecipeMatchSummary)).all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in rows])


def estimate_item_value(item_name: str, receipts_df: pd.DataFrame) -> float:
    """
    Estimate the value of an inventory item based on receipt prices.

    HOW THIS WORKS
    We look up the item in receipt data to find what we paid for it.
    If the item appears multiple times, we use the average price.
    If no receipt match is found, we return 0 (unknown value).

    This is a rough estimate — the receipt price might not match the
    exact item in inventory, but it gives a ballpark for waste cost.
    """
    if receipts_df.empty:
        return 0.0

    # Try matching by normalized_name first, then item_name
    name_col = "normalized_name" if "normalized_name" in receipts_df.columns else "item_name"
    matches = receipts_df[
        receipts_df[name_col].str.lower().str.strip() == item_name.lower().strip()
    ]

    if matches.empty:
        return 0.0

    # Use average total_price from matching receipt entries
    prices = matches["total_price"].dropna()
    if prices.empty:
        return 0.0

    return prices.mean()


def analyze_waste():
    """
    Run the full food waste analysis and print a formatted report.

    ANALYSIS STEPS
    1. Find expired items and estimate their value
    2. Find items expiring in 3 days with no recipe match
    3. Find items expiring in 7 days WITH a recipe match (cook these!)
    4. Calculate an overall waste risk score
    5. Suggest recipes to reduce waste
    """
    inventory_df = load_inventory()
    receipts_df = load_receipts()
    match_detail_df = load_match_detail()
    match_summary_df = load_match_summary()

    if inventory_df.empty:
        print("No inventory data found. Run the normalization pipeline first:")
        print("  uv run python -m src.normalization.build_inventory")
        return

    today = date.today()

    print("=" * 70)
    print("       WASTE RISK ANALYSIS")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Already expired items
    # ------------------------------------------------------------------
    # Boolean filter: select rows where is_expired is True
    expired_df = inventory_df[inventory_df["is_expired"] == True]  # noqa: E712

    expired_value = 0.0
    if not expired_df.empty:
        for _, item in expired_df.iterrows():
            expired_value += estimate_item_value(item["item_name"], receipts_df)

    print(f"\n  Items expired: {len(expired_df)}", end="")
    if expired_value > 0:
        print(f" (estimated value: ${expired_value:.2f} based on receipt prices)")
    else:
        print(" (no price data available to estimate value)")

    if not expired_df.empty:
        for _, item in expired_df.iterrows():
            print(f"    - {item['item_name']} ({item['category']})")

    # ------------------------------------------------------------------
    # 2. Items expiring in 3 days with no matching recipe
    # ------------------------------------------------------------------
    # First, find items expiring within 3 days (but not yet expired)
    cutoff_3 = today + timedelta(days=3)
    active_df = inventory_df[inventory_df["is_expired"] == False]  # noqa: E712

    # Convert expiration_date for comparison
    has_expiry = active_df.dropna(subset=["expiration_date"]).copy()
    has_expiry["expiration_date"] = pd.to_datetime(
        has_expiry["expiration_date"]
    ).dt.date

    expiring_3d = has_expiry[has_expiry["expiration_date"] <= cutoff_3]

    # Check which of these have matching recipes
    expiring_3d_no_recipe = []
    if not expiring_3d.empty and not match_detail_df.empty:
        # Get join keys that appear in recipes and are available
        recipe_item_keys = set(
            match_detail_df[
                match_detail_df["is_available"] == True  # noqa: E712
            ]["ingredient_join_key"].unique()
        )

        for _, item in expiring_3d.iterrows():
            if item["join_key"] not in recipe_item_keys:
                expiring_3d_no_recipe.append(item)
    elif not expiring_3d.empty:
        # No match data — all expiring items have no known recipe
        expiring_3d_no_recipe = [row for _, row in expiring_3d.iterrows()]

    print(f"\n  Items expiring in 3 days with no matching recipe: {len(expiring_3d_no_recipe)}")
    for item in expiring_3d_no_recipe:
        days_left = (item["expiration_date"] - today).days
        print(f"    - {item['item_name']} (expires in {days_left} day(s))")

    # ------------------------------------------------------------------
    # 3. Items expiring in 7 days WITH a matching recipe
    # ------------------------------------------------------------------
    cutoff_7 = today + timedelta(days=7)
    expiring_7d = has_expiry[
        (has_expiry["expiration_date"] <= cutoff_7)
        & (has_expiry["expiration_date"] > cutoff_3)
    ]

    expiring_7d_with_recipe = []
    if not expiring_7d.empty and not match_detail_df.empty:
        recipe_item_keys = set(
            match_detail_df[
                match_detail_df["is_available"] == True  # noqa: E712
            ]["ingredient_join_key"].unique()
        )

        for _, item in expiring_7d.iterrows():
            if item["join_key"] in recipe_item_keys:
                expiring_7d_with_recipe.append(item)

    print(f"\n  Items expiring in 7 days with a matching recipe: {len(expiring_7d_with_recipe)}")
    if expiring_7d_with_recipe:
        print("    (make these recipes!)")
        for item in expiring_7d_with_recipe:
            days_left = (item["expiration_date"] - today).days
            print(f"    - {item['item_name']} (expires in {days_left} day(s))")

    # ------------------------------------------------------------------
    # 4. Overall waste risk score
    # ------------------------------------------------------------------
    # Score based on: expired items, items about to expire, and whether
    # there are recipes to use them up.
    risk_score = 0
    risk_score += len(expired_df) * 3        # 3 points per expired item
    risk_score += len(expiring_3d_no_recipe) * 2  # 2 points per 3-day no-recipe
    risk_score += len(expiring_7d_with_recipe) * 1  # 1 point per 7-day with recipe

    if risk_score == 0:
        risk_level = "LOW"
        risk_msg = "Your kitchen is in great shape! Minimal waste risk."
    elif risk_score <= 5:
        risk_level = "LOW-MEDIUM"
        risk_msg = "A few items to watch — consider cooking them soon."
    elif risk_score <= 10:
        risk_level = "MEDIUM"
        risk_msg = "Several items need attention. Check the suggestions below."
    elif risk_score <= 20:
        risk_level = "HIGH"
        risk_msg = "Multiple items at risk. Prioritize cooking or using them today."
    else:
        risk_level = "CRITICAL"
        risk_msg = "Significant waste risk! Take action immediately."

    print(f"\n  Overall waste risk: {risk_level} (score: {risk_score})")
    print(f"  {risk_msg}")

    # ------------------------------------------------------------------
    # 5. Recipe suggestions to reduce waste
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("  SUGGESTED RECIPES TO REDUCE WASTE")
    print("=" * 70)

    if match_summary_df.empty:
        print("\n  No recipe matching data available.")
        print("  Run: uv run python -m src.normalization.build_recipe_matching")
        return

    # Find recipes that use any expiring ingredients
    # Collect all expiring item names (within 7 days)
    all_expiring = has_expiry[has_expiry["expiration_date"] <= cutoff_7]
    if all_expiring.empty:
        print("\n  No expiring items — no urgent recipes to suggest!")
        return

    expiring_names = set(all_expiring["item_name"].tolist())

    if match_detail_df.empty:
        print("\n  No match detail data available.")
        return

    # Find recipes that use expiring items (via the match detail table)
    uses_expiring = match_detail_df[
        (match_detail_df["is_available"] == True)  # noqa: E712
        & (match_detail_df["inventory_item_name"].isin(expiring_names))
    ]

    if uses_expiring.empty:
        print("\n  No recipes found that use your expiring ingredients.")
        return

    # Group by recipe — count how many expiring ingredients each recipe uses
    # groupby().agg() lets us compute multiple stats per group
    recipe_scores = (
        uses_expiring.groupby(["recipe_id", "recipe_name"])
        .agg(
            expiring_used=("ingredient_name", "count"),
            expiring_items=("inventory_item_name", lambda x: ", ".join(sorted(set(x)))),
        )
        .reset_index()
        .sort_values("expiring_used", ascending=False)
    )

    # Merge with summary to get makeability info
    # pd.merge() combines two DataFrames like a SQL JOIN.
    # on="recipe_id" means "match rows where recipe_id is the same in both tables."
    # how="left" means "keep all rows from the left DataFrame, even if no match."
    recipe_scores = pd.merge(
        recipe_scores,
        match_summary_df[["recipe_id", "is_fully_makeable", "missing_ingredients"]],
        on="recipe_id",
        how="left",
    )

    # Split into fully makeable and needs shopping
    makeable = recipe_scores[recipe_scores["is_fully_makeable"] == True]  # noqa: E712
    needs_shopping = recipe_scores[recipe_scores["is_fully_makeable"] == False]  # noqa: E712

    if not makeable.empty:
        print("\n  COOK THESE NOW (fully makeable, uses expiring ingredients):")
        for _, row in makeable.iterrows():
            print(f"    ★ {row['recipe_name']} (uses: {row['expiring_items']})")

    if not needs_shopping.empty:
        print("\n  WITH A QUICK SHOPPING TRIP:")
        for _, row in needs_shopping.head(5).iterrows():
            print(
                f"    → {row['recipe_name']} "
                f"(uses: {row['expiring_items']}, "
                f"missing {int(row['missing_ingredients'])} ingredient(s))"
            )

    print(f"\n{'=' * 70}")
    print("Tip: Run this script weekly to stay ahead of food waste!")
    print("Real restaurants run this kind of analysis DAILY.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    analyze_waste()
