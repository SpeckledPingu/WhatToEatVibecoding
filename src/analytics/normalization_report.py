"""
normalization_report.py — Validate and visualize the normalization results.

WHY DATA QUALITY MONITORING MATTERS
Normalization is only as good as your rules. If an alias is missing from the
config, a food item won't normalize correctly and won't match recipes or shelf
life data. This report helps you:
  - Verify that normalization is working as expected (before/after comparison)
  - Find items that might be duplicates (same join key from different names)
  - Identify gaps between inventory and recipes (what recipes can't you make?)
  - See when your food is expiring (what should you cook this week?)

HOW TO INTERPRET THE RESULTS
  - Before/After table: Check that transformations make sense. If "olive oil"
    became "oil", you might need to adjust the stripping rules.
  - Gap analysis: Items in inventory but NOT in any recipe = foods you bought
    but have no recipes for. Items in recipes but NOT in inventory = ingredients
    you'd need to buy.
  - Data quality score: Higher is better. A low score means many items are
    missing categories or shelf life data — time to update the config.

WHAT TO DO WHEN ITEMS DON'T NORMALIZE WELL
1. Open config/normalization_mappings.json
2. Add the problematic name to the appropriate section:
   - name_aliases: if it's a variation of an existing food
   - food_categories: if the food is uncategorized
   - abbreviations: if it's a receipt abbreviation
   - qualifiers_to_strip: if it includes a marketing term not yet listed
3. Re-run the normalization pipeline and check this report again

RUN IT:
    uv run python -m src.analytics.normalization_report
"""

from datetime import date, timedelta

import pandas as pd
from sqlmodel import Session, select

from src.database import get_engine
from src.models.inventory import ActiveInventory
from src.models.recipe import Recipe


def load_inventory_dataframe() -> pd.DataFrame:
    """
    Load the ActiveInventory table into a pandas DataFrame.

    HOW SQL → DATAFRAME WORKS
    1. Open a database session
    2. Query all ActiveInventory rows (SELECT *)
    3. Convert each SQLModel object to a dict with model_dump()
    4. Pass the list of dicts to pd.DataFrame()
    """
    engine = get_engine()
    with Session(engine) as session:
        items = session.exec(select(ActiveInventory)).all()
        if not items:
            return pd.DataFrame()
        return pd.DataFrame([item.model_dump() for item in items])


def load_recipe_ingredients() -> set[str]:
    """
    Extract all unique ingredient names from recipes.

    We need this for gap analysis: comparing what's in inventory against
    what recipes call for.
    """
    engine = get_engine()
    ingredient_names = set()
    with Session(engine) as session:
        recipes = session.exec(select(Recipe)).all()
        for recipe in recipes:
            if isinstance(recipe.ingredients, list):
                for ing in recipe.ingredients:
                    if isinstance(ing, dict) and "name" in ing:
                        ingredient_names.add(ing["name"].lower())
    return ingredient_names


def run_normalization_report():
    """
    Generate a comprehensive quality report for the normalization results.
    """
    df = load_inventory_dataframe()

    if df.empty:
        print("No inventory data found. Run the build pipeline first:")
        print("  uv run python -m src.normalization.build_inventory")
        return

    print("=" * 70)
    print("NORMALIZATION QUALITY REPORT")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Before/After table: original vs normalized names
    # ------------------------------------------------------------------
    print("\n1. NAME TRANSFORMATIONS (Before → After)")
    print("-" * 60)

    # Deduplicate by original_name to show unique transformations
    transforms = (
        df[["original_name", "item_name", "category", "join_key", "source"]]
        .drop_duplicates(subset=["original_name"])
        .sort_values(["source", "original_name"])
    )

    for source in ["receipt", "pantry"]:
        source_df = transforms[transforms["source"] == source]
        if source_df.empty:
            continue
        print(f"\n  {source.upper()} ({len(source_df)} unique items):")
        for _, row in source_df.iterrows():
            orig = row["original_name"][:35]
            if len(row["original_name"]) > 35:
                orig += ".."
            print(f"    {orig:<37} → {row['item_name']:<20} [{row['category']}]")

    # ------------------------------------------------------------------
    # 2. Join key analysis
    # ------------------------------------------------------------------
    print(f"\n\n2. JOIN KEY ANALYSIS")
    print("-" * 60)

    key_counts = df.groupby("join_key").agg(
        record_count=("id", "count"),
        sources=("source", lambda x: ", ".join(sorted(set(x)))),
        names=("original_name", lambda x: " | ".join(sorted(set(x))[:3])),
    ).sort_values("record_count", ascending=False)

    print(f"  Total unique join keys: {len(key_counts)}")
    print(f"\n  {'Join Key':<30} {'Records':>8} {'Sources':<15} {'Original Names'}")
    print(f"  {'-'*30} {'-'*8} {'-'*15} {'-'*40}")

    for key, row in key_counts.iterrows():
        names_display = row["names"][:38]
        if len(row["names"]) > 38:
            names_display += ".."
        print(
            f"  {str(key):<30} {row['record_count']:>8} "
            f"{row['sources']:<15} {names_display}"
        )

    # ------------------------------------------------------------------
    # 3. Duplicate detection (same join key from different original names)
    # ------------------------------------------------------------------
    print(f"\n\n3. POTENTIAL DUPLICATES (same join key, different source names)")
    print("-" * 60)

    # Items with the same join key but different original names might be
    # genuine duplicates (bought AND in pantry) or normalization issues
    multi_name_keys = df.groupby("join_key").filter(
        lambda g: g["original_name"].nunique() > 1
    )

    if multi_name_keys.empty:
        print("  No potential duplicates found.")
    else:
        dup_groups = multi_name_keys.groupby("join_key")["original_name"].unique()
        for key, names in dup_groups.items():
            print(f"  {key}:")
            for name in sorted(names):
                print(f"    - {name}")

    # ------------------------------------------------------------------
    # 4. Gap analysis (inventory vs recipes)
    # ------------------------------------------------------------------
    print(f"\n\n4. GAP ANALYSIS (Inventory ↔ Recipes)")
    print("-" * 60)

    recipe_ingredients = load_recipe_ingredients()
    inventory_names = set(df["item_name"].unique())

    in_inventory_not_recipes = sorted(inventory_names - recipe_ingredients)
    in_recipes_not_inventory = sorted(recipe_ingredients - inventory_names)

    print(f"  Unique inventory items:       {len(inventory_names)}")
    print(f"  Unique recipe ingredients:    {len(recipe_ingredients)}")

    # Items you have but no recipe uses
    if in_inventory_not_recipes:
        print(f"\n  Items in INVENTORY but not in any recipe ({len(in_inventory_not_recipes)}):")
        print("  (Foods you have but no recipe calls for)")
        for name in in_inventory_not_recipes:
            print(f"    - {name}")

    # Items recipes need but you don't have
    if in_recipes_not_inventory:
        print(f"\n  Items in RECIPES but not in inventory ({len(in_recipes_not_inventory)}):")
        print("  (Ingredients you'd need to buy)")
        for name in in_recipes_not_inventory:
            print(f"    - {name}")

    overlap = inventory_names & recipe_ingredients
    print(f"\n  Matching items (in both): {len(overlap)}")
    if overlap:
        for name in sorted(overlap):
            print(f"    - {name}")

    # ------------------------------------------------------------------
    # 5. Category distribution
    # ------------------------------------------------------------------
    print(f"\n\n5. CATEGORY DISTRIBUTION")
    print("-" * 60)

    cat_counts = df["category"].value_counts()
    max_bar_width = 40

    print(f"\n  {'Category':<15} {'Count':>6} {'Bar'}")
    print(f"  {'-'*15} {'-'*6} {'-'*max_bar_width}")

    max_count = cat_counts.max()
    for category, count in cat_counts.items():
        bar_length = int((count / max_count) * max_bar_width)
        bar = "#" * bar_length
        print(f"  {category:<15} {count:>6} {bar}")

    # ------------------------------------------------------------------
    # 6. Expiration timeline
    # ------------------------------------------------------------------
    print(f"\n\n6. EXPIRATION TIMELINE (next 4 weeks)")
    print("-" * 60)

    today = date.today()
    # Convert expiration_date column to date objects for comparison
    df["exp_date"] = pd.to_datetime(df["expiration_date"]).dt.date

    for week in range(4):
        week_start = today + timedelta(weeks=week)
        week_end = today + timedelta(weeks=week + 1)
        expiring = df[
            (df["exp_date"] >= week_start) & (df["exp_date"] < week_end)
            & (~df["is_expired"])
        ]

        label = "THIS WEEK" if week == 0 else f"Week {week + 1}"
        print(f"\n  {label} ({week_start} to {week_end}):")

        if expiring.empty:
            print("    (nothing expiring)")
        else:
            for _, row in expiring.iterrows():
                print(f"    - {row['item_name']} ({row['source']}: {row['original_name'][:30]})")

    # Already expired
    expired_df = df[df["is_expired"]]
    if not expired_df.empty:
        print(f"\n  ALREADY EXPIRED ({len(expired_df)} items):")
        for _, row in expired_df.iterrows():
            print(f"    - {row['item_name']} (expired {row['exp_date']})")

    # ------------------------------------------------------------------
    # 7. Data quality score
    # ------------------------------------------------------------------
    print(f"\n\n7. DATA QUALITY SCORE")
    print("-" * 60)

    total = len(df)

    # (a) Items with a non-'other' category
    has_category = (df["category"] != "other").sum()
    cat_pct = (has_category / total * 100) if total > 0 else 0

    # (b) Items that matched a specific shelf life (not the 4-week default)
    # We can infer this: if shelf life led to a reasonable expiration date
    # (not exactly 4 weeks from acquisition), it matched something specific.
    # Simpler: check if item_name appears in FoodShelfLife table
    has_expiration = df["expiration_date"].notna().sum()
    exp_pct = (has_expiration / total * 100) if total > 0 else 0

    # (c) Items with a valid join key (should be all of them)
    has_join_key = (df["join_key"].str.len() > 0).sum()
    key_pct = (has_join_key / total * 100) if total > 0 else 0

    overall_score = (cat_pct + exp_pct + key_pct) / 3

    print(f"  Items with specific category:    {has_category}/{total} ({cat_pct:.0f}%)")
    print(f"  Items with expiration date:      {has_expiration}/{total} ({exp_pct:.0f}%)")
    print(f"  Items with valid join key:        {has_join_key}/{total} ({key_pct:.0f}%)")
    print(f"\n  Overall data quality score:       {overall_score:.0f}%")

    if overall_score >= 90:
        print("  Excellent! Your normalization rules cover the data well.")
    elif overall_score >= 70:
        print("  Good, but some items could use better config coverage.")
    else:
        print("  Consider adding more rules to config/normalization_mappings.json")

    print(f"\n{'=' * 70}")
    print("Report complete.")


# ---------------------------------------------------------------------------
# Optional: Save charts to files using matplotlib
# ---------------------------------------------------------------------------
def save_charts():
    """
    Generate and save visualization charts as PNG files.

    This creates two charts:
      1. Category distribution bar chart
      2. Expiration timeline chart

    Charts are saved to the project root for easy viewing.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend for file output
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not available — skipping chart generation")
        print("  Install it with: uv add matplotlib")
        return

    df = load_inventory_dataframe()
    if df.empty:
        return

    from pathlib import Path
    charts_dir = Path(__file__).parent.parent.parent / "docs" / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    # --- Chart 1: Category distribution ---
    fig, ax = plt.subplots(figsize=(10, 6))
    cat_counts = df["category"].value_counts()
    cat_counts.plot(kind="barh", ax=ax, color="steelblue")
    ax.set_xlabel("Number of Items")
    ax.set_title("Inventory by Food Category")
    ax.invert_yaxis()
    plt.tight_layout()
    chart_path = charts_dir / "category_distribution.png"
    fig.savefig(chart_path)
    plt.close(fig)
    print(f"  Saved: {chart_path}")

    # --- Chart 2: Expiration timeline ---
    today = date.today()
    df["exp_date"] = pd.to_datetime(df["expiration_date"]).dt.date
    active = df[~df["is_expired"]].copy()

    if not active.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        # Bucket by week
        active["weeks_until_expiry"] = active["exp_date"].apply(
            lambda d: max(0, (d - today).days // 7) if d else 0
        )
        week_counts = active["weeks_until_expiry"].value_counts().sort_index()
        # Limit to 12 weeks
        week_counts = week_counts[week_counts.index <= 12]
        week_counts.plot(kind="bar", ax=ax, color="coral")
        ax.set_xlabel("Weeks Until Expiration")
        ax.set_ylabel("Number of Items")
        ax.set_title("Expiration Timeline — Items Expiring by Week")
        plt.tight_layout()
        chart_path = charts_dir / "expiration_timeline.png"
        fig.savefig(chart_path)
        plt.close(fig)
        print(f"  Saved: {chart_path}")


if __name__ == "__main__":
    run_normalization_report()

    print("\n\nGenerating charts...")
    save_charts()
