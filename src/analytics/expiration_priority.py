"""
expiration_priority.py — Identify expiring inventory and recommend recipes.

FOOD WASTE IS A REAL PROBLEM
About 30-40% of food in the US goes to waste. One major cause: people forget
what's in their fridge until it expires. This script tackles that by:
  1. Finding items expiring in the next 7 days
  2. Cross-referencing with recipes that use those items
  3. Ranking recipes by how many expiring ingredients they use
  4. Visualizing the expiration timeline

This is the same logic used by:
  - Grocery delivery apps (suggesting "use it up" recipes)
  - Restaurant inventory systems (daily specials based on what needs to move)
  - Food banks (prioritizing distribution of soon-to-expire donations)

RUN IT:
    uv run python -m src.analytics.expiration_priority
"""

from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for script use
import matplotlib.pyplot as plt
import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.inventory import ActiveInventory
from src.models.recipe_matching import RecipeIngredientMatch, RecipeMatchSummary


def get_expiring_items(days: int = 7) -> pd.DataFrame:
    """
    Find all inventory items expiring within the specified number of days.

    Parameters:
        days: Number of days to look ahead (default: 7).

    Returns:
        DataFrame with columns: item_name, category, expiration_date,
        days_until_expiry, quantity, unit
    """
    engine = get_engine()
    create_db_and_tables(engine)
    today = date.today()
    cutoff = today + timedelta(days=days)

    with Session(engine) as session:
        results = session.exec(
            select(ActiveInventory).where(
                ActiveInventory.is_expired == False,  # noqa: E712
                ActiveInventory.expiration_date != None,  # noqa: E711
                ActiveInventory.expiration_date <= cutoff,
            )
        ).all()

        data = []
        for item in results:
            days_left = (item.expiration_date - today).days
            data.append({
                "item_name": item.item_name,
                "category": item.category,
                "expiration_date": item.expiration_date,
                "days_until_expiry": days_left,
                "quantity": item.quantity,
                "unit": item.unit,
            })

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("days_until_expiry").reset_index(drop=True)
    return df


def get_use_it_up_recipes(expiring_items: pd.DataFrame) -> pd.DataFrame:
    """
    Find recipes that use expiring ingredients, ranked by how many they use.

    This cross-references expiring inventory items with the recipe matching
    tables to find recipes that would help use up ingredients before they
    expire. Recipes using more expiring ingredients are ranked higher.

    Parameters:
        expiring_items: DataFrame from get_expiring_items().

    Returns:
        DataFrame with columns: recipe_name, recipe_id, is_fully_makeable,
        missing_ingredients, expiring_items_used, expiring_item_names
    """
    if expiring_items.empty:
        return pd.DataFrame()

    engine = get_engine()
    create_db_and_tables(engine)
    expiring_names = set(expiring_items["item_name"].tolist())

    with Session(engine) as session:
        # Find all ingredient matches that involve expiring items
        matches = session.exec(
            select(RecipeIngredientMatch).where(
                RecipeIngredientMatch.is_available == True,  # noqa: E712
            )
        ).all()

        # Group by recipe, counting expiring ingredient uses
        recipe_expiring: dict[int, dict] = {}
        for match in matches:
            if match.inventory_item_name in expiring_names:
                if match.recipe_id not in recipe_expiring:
                    # Look up the summary for this recipe
                    summary = session.exec(
                        select(RecipeMatchSummary).where(
                            RecipeMatchSummary.recipe_id == match.recipe_id
                        )
                    ).first()

                    recipe_expiring[match.recipe_id] = {
                        "recipe_name": match.recipe_name,
                        "recipe_id": match.recipe_id,
                        "is_fully_makeable": summary.is_fully_makeable if summary else False,
                        "missing_ingredients": summary.missing_ingredients if summary else 0,
                        "expiring_items_used": 0,
                        "expiring_item_names": [],
                    }

                recipe_expiring[match.recipe_id]["expiring_items_used"] += 1
                recipe_expiring[match.recipe_id]["expiring_item_names"].append(
                    match.inventory_item_name
                )

    data = list(recipe_expiring.values())
    for item in data:
        item["expiring_item_names"] = ", ".join(sorted(set(item["expiring_item_names"])))

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(
            ["expiring_items_used", "missing_ingredients"],
            ascending=[False, True],
        ).reset_index(drop=True)
    return df


def plot_expiration_timeline(expiring_items: pd.DataFrame, output_path: str = None):
    """
    Create a horizontal bar chart showing when inventory items expire.

    The chart visualizes the urgency: items closer to expiration appear in
    red/orange, items with more time appear in yellow/green.

    Parameters:
        expiring_items: DataFrame from get_expiring_items().
        output_path: File path to save the chart. If None, saves to
                     db/expiration_timeline.png.
    """
    if expiring_items.empty:
        print("  No expiring items to chart.")
        return

    if output_path is None:
        from pathlib import Path
        output_dir = Path(__file__).parent.parent.parent / "db"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / "expiration_timeline.png")

    # Deduplicate by item name (keep the soonest expiration)
    chart_data = (
        expiring_items.groupby("item_name")["days_until_expiry"]
        .min()
        .sort_values()
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(10, max(4, len(chart_data) * 0.4)))

    # Color by urgency
    colors = []
    for days in chart_data["days_until_expiry"]:
        if days <= 1:
            colors.append("#e74c3c")   # Red — expires today/tomorrow
        elif days <= 3:
            colors.append("#e67e22")   # Orange — very soon
        elif days <= 5:
            colors.append("#f39c12")   # Yellow — soon
        else:
            colors.append("#27ae60")   # Green — some time left

    bars = ax.barh(
        chart_data["item_name"],
        chart_data["days_until_expiry"],
        color=colors,
        edgecolor="white",
    )

    # Add day count labels on bars
    for bar, days in zip(bars, chart_data["days_until_expiry"]):
        ax.text(
            bar.get_width() + 0.1,
            bar.get_y() + bar.get_height() / 2,
            f"{days}d",
            va="center",
            fontsize=9,
        )

    ax.set_xlabel("Days Until Expiration")
    ax.set_title("Inventory Expiration Timeline")
    ax.set_xlim(0, max(chart_data["days_until_expiry"]) + 1.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved to: {output_path}")


# ---------------------------------------------------------------------------
# Main — run the full expiration priority analysis
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("EXPIRATION PRIORITY ANALYSIS")
    print("=" * 70)

    # --- Step 1: Find expiring items ---
    print("\nStep 1: Finding items expiring within 7 days...")
    expiring = get_expiring_items(days=7)

    if expiring.empty:
        print("  No items expiring in the next 7 days. Your inventory is fresh!")
        print()
        # Still check for items expiring in 14 days for awareness
        expiring_14 = get_expiring_items(days=14)
        if not expiring_14.empty:
            print("  Items expiring in the next 14 days:")
            for _, row in expiring_14.iterrows():
                print(f"    - {row['item_name']} (expires in {row['days_until_expiry']} days)")
    else:
        print(f"\n  EXPIRING SOON:")
        for _, row in expiring.iterrows():
            urgency = "!!" if row["days_until_expiry"] <= 2 else "!"
            print(
                f"    {urgency} {row['item_name']} "
                f"(expires in {row['days_until_expiry']} day(s), "
                f"{row['quantity']} {row['unit']})"
            )

    # --- Step 2: Find "use it up" recipes ---
    print(f"\nStep 2: Finding recipes that use expiring ingredients...")
    recipes = get_use_it_up_recipes(expiring)

    if recipes.empty:
        print("  No recipes found that use expiring ingredients.")
    else:
        # Split into makeable and needs-shopping
        makeable = recipes[recipes["is_fully_makeable"] == True]
        needs_shopping = recipes[recipes["is_fully_makeable"] == False]

        if not makeable.empty:
            print(f"\n  MAKE THESE FIRST (fully makeable, uses expiring ingredients):")
            for i, (_, row) in enumerate(makeable.iterrows(), 1):
                print(
                    f"    {i}. {row['recipe_name']} "
                    f"(uses: {row['expiring_item_names']})"
                )

        if not needs_shopping.empty:
            print(f"\n  COULD MAKE WITH SHOPPING (uses expiring ingredients):")
            for i, (_, row) in enumerate(needs_shopping.iterrows(), 1):
                print(
                    f"    {i}. {row['recipe_name']} "
                    f"(uses: {row['expiring_item_names']}, "
                    f"missing {row['missing_ingredients']} ingredient(s))"
                )

    # --- Step 3: Generate expiration timeline chart ---
    print(f"\nStep 3: Generating expiration timeline chart...")
    # Use 14-day window for the chart to give more context
    expiring_chart = get_expiring_items(days=14)
    plot_expiration_timeline(expiring_chart)

    print(f"\n{'=' * 70}")
    print("Tip: Re-run this script periodically to stay on top of expiring food.")
    print("Add it to your weekly routine or automate it with a cron job!")
