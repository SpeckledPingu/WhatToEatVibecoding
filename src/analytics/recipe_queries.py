"""
recipe_queries.py — Query helper functions for recipe matching results.

WHY HELPER FUNCTIONS?
The recipe matching tables contain rich data, but raw SQL queries can be
verbose and hard to reuse. These helper functions wrap common queries into
clean Python functions that return pandas DataFrames — ready for display,
analysis, or API responses.

Each function encapsulates a specific question:
  - get_makeable_recipes(): "What can I cook right now?"
  - get_recipes_missing_n(n): "What am I close to being able to make?"
  - get_recipes_with_substitutes(): "What if I swap similar ingredients?"
  - get_expiring_recipes(): "What should I cook before ingredients go bad?"
  - get_shopping_list(recipe_ids): "What do I need to buy?"
  - get_ingredient_detail(recipe_id): "Show me every ingredient for this recipe"

THE DATAFRAME PATTERN
All functions return pandas DataFrames because:
  - DataFrames display nicely in notebooks, terminals, and Streamlit
  - They support filtering, sorting, and grouping without more SQL
  - The API layer can easily convert them to JSON responses
  - Analytics scripts can chain operations (df.groupby, df.plot, etc.)

RUN IT:
    uv run python -m src.analytics.recipe_queries
"""

import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.recipe_matching import RecipeIngredientMatch, RecipeMatchSummary


def get_makeable_recipes() -> pd.DataFrame:
    """
    Get all recipes that can be made right now (all ingredients in stock).

    QUERY LOGIC:
    Select from RecipeMatchSummary where is_fully_makeable = True.
    This is the simplest query — the matching builder already computed
    whether each recipe is fully makeable.

    Returns:
        DataFrame with columns: recipe_id, recipe_name, total_ingredients,
        weather_temp, weather_condition
    """
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        results = session.exec(
            select(RecipeMatchSummary).where(
                RecipeMatchSummary.is_fully_makeable == True  # noqa: E712
            )
        ).all()

        data = [
            {
                "recipe_id": r.recipe_id,
                "recipe_name": r.recipe_name,
                "total_ingredients": r.total_ingredients,
                "weather_temp": r.weather_temp,
                "weather_condition": r.weather_condition,
            }
            for r in results
        ]

    return pd.DataFrame(data)


def get_recipes_missing_n(n: int) -> pd.DataFrame:
    """
    Get recipes missing N or fewer ingredients, sorted by fewest missing first.

    QUERY LOGIC:
    Select from RecipeMatchSummary where missing_ingredients <= n AND
    missing_ingredients > 0 (exclude fully makeable — use get_makeable_recipes
    for those). Sorted so "almost there" recipes appear first.

    This answers: "What am I just 1 or 2 ingredients away from making?"
    Great for generating a focused shopping list.

    Parameters:
        n: Maximum number of missing ingredients to include.

    Returns:
        DataFrame with columns: recipe_id, recipe_name, missing_ingredients,
        missing_ingredient_list, has_category_substitutes
    """
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        results = session.exec(
            select(RecipeMatchSummary).where(
                RecipeMatchSummary.missing_ingredients <= n,
                RecipeMatchSummary.missing_ingredients > 0,
            )
        ).all()

        data = [
            {
                "recipe_id": r.recipe_id,
                "recipe_name": r.recipe_name,
                "total_ingredients": r.total_ingredients,
                "available_ingredients": r.available_ingredients,
                "missing_ingredients": r.missing_ingredients,
                "missing_ingredient_list": r.missing_ingredient_list,
                "has_category_substitutes": r.has_category_substitutes,
            }
            for r in results
        ]

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("missing_ingredients").reset_index(drop=True)
    return df


def get_recipes_with_substitutes() -> pd.DataFrame:
    """
    Get recipes where missing ingredients have category-level substitutes.

    QUERY LOGIC:
    Select from RecipeMatchSummary where has_category_substitutes = True.
    These are recipes that aren't fully makeable, but you COULD make them
    by swapping a similar ingredient (e.g., cheddar → mozzarella).

    The substitute_details JSON field contains specifics about what could
    be swapped — check the category_substitution_rules in the config to
    understand how reliable each suggestion is.

    Returns:
        DataFrame with columns: recipe_id, recipe_name, missing_ingredients,
        missing_ingredient_list, substitute_details
    """
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        results = session.exec(
            select(RecipeMatchSummary).where(
                RecipeMatchSummary.has_category_substitutes == True  # noqa: E712
            )
        ).all()

        data = [
            {
                "recipe_id": r.recipe_id,
                "recipe_name": r.recipe_name,
                "missing_ingredients": r.missing_ingredients,
                "missing_ingredient_list": r.missing_ingredient_list,
                "substitute_details": r.substitute_details,
            }
            for r in results
        ]

    return pd.DataFrame(data)


def get_expiring_recipes() -> pd.DataFrame:
    """
    Get recipes that use ingredients expiring within 7 days.

    QUERY LOGIC:
    Select from RecipeMatchSummary where uses_expiring_ingredients = True.
    Sorted by the soonest-expiring ingredient so the most urgent recipes
    appear first.

    These are the "cook it or lose it" recipes — prioritize them to reduce
    food waste. This is the same logic grocery stores use for clearance
    pricing and food banks use for distribution prioritization.

    Returns:
        DataFrame with columns: recipe_id, recipe_name, is_fully_makeable,
        missing_ingredients, expiring_ingredient_list
    """
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        results = session.exec(
            select(RecipeMatchSummary).where(
                RecipeMatchSummary.uses_expiring_ingredients == True  # noqa: E712
            )
        ).all()

        data = []
        for r in results:
            # Find the soonest expiration for sorting
            min_days = 999
            if r.expiring_ingredient_list:
                for item in r.expiring_ingredient_list:
                    days = item.get("days_until_expiry", 999)
                    if days < min_days:
                        min_days = days

            data.append({
                "recipe_id": r.recipe_id,
                "recipe_name": r.recipe_name,
                "is_fully_makeable": r.is_fully_makeable,
                "missing_ingredients": r.missing_ingredients,
                "expiring_ingredient_list": r.expiring_ingredient_list,
                "soonest_expiry_days": min_days,
            })

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("soonest_expiry_days").reset_index(drop=True)
    return df


def get_shopping_list(recipe_ids: list[int]) -> pd.DataFrame:
    """
    Get a consolidated, deduplicated shopping list for the specified recipes.

    QUERY LOGIC:
    Select from RecipeIngredientMatch where recipe_id is in the list AND
    is_available = False. Group by ingredient to deduplicate (if multiple
    recipes need the same ingredient, list it once).

    This is the practical output: "I want to make these recipes, what do
    I need to buy?" The deduplication is important — if 3 recipes need
    garlic, you only need to buy garlic once.

    Parameters:
        recipe_ids: List of recipe IDs to generate a shopping list for.

    Returns:
        DataFrame with columns: ingredient_name, category, needed_by_recipes,
        recipe_count
    """
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        results = session.exec(
            select(RecipeIngredientMatch).where(
                RecipeIngredientMatch.recipe_id.in_(recipe_ids),  # type: ignore
                RecipeIngredientMatch.is_available == False,  # noqa: E712
            )
        ).all()

        # Deduplicate by ingredient, collecting which recipes need it
        ingredient_map: dict[str, dict] = {}
        for r in results:
            if r.ingredient_name not in ingredient_map:
                ingredient_map[r.ingredient_name] = {
                    "ingredient_name": r.ingredient_name,
                    "category": r.ingredient_category,
                    "needed_by_recipes": [],
                }
            ingredient_map[r.ingredient_name]["needed_by_recipes"].append(
                r.recipe_name
            )

        data = []
        for item in ingredient_map.values():
            data.append({
                "ingredient_name": item["ingredient_name"],
                "category": item["category"],
                "needed_by_recipes": ", ".join(set(item["needed_by_recipes"])),
                "recipe_count": len(set(item["needed_by_recipes"])),
            })

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values("recipe_count", ascending=False).reset_index(drop=True)
    return df


def get_ingredient_detail(recipe_id: int) -> pd.DataFrame:
    """
    Get the full ingredient match breakdown for a single recipe.

    QUERY LOGIC:
    Select all RecipeIngredientMatch rows for the given recipe_id. This
    shows every ingredient with its match status, availability, and
    substitution info.

    This is the most detailed view — useful for understanding exactly why
    a recipe is or isn't makeable, and what substitutions are possible.

    Parameters:
        recipe_id: The ID of the recipe to examine.

    Returns:
        DataFrame with all ingredient match fields for this recipe.
    """
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        results = session.exec(
            select(RecipeIngredientMatch).where(
                RecipeIngredientMatch.recipe_id == recipe_id
            )
        ).all()

        data = [
            {
                "ingredient_name": r.ingredient_name,
                "join_key": r.ingredient_join_key,
                "category": r.ingredient_category,
                "is_available": r.is_available,
                "inventory_item": r.inventory_item_name,
                "available_qty": r.available_quantity,
                "required_qty": r.required_quantity,
                "required_unit": r.required_unit,
                "has_substitute": r.category_substitute_available,
                "substitute": r.substitute_item_name,
            }
            for r in results
        ]

    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Demo — run all query helpers with formatted output
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("RECIPE QUERY HELPERS — DEMO")
    print("=" * 70)

    # --- Fully makeable ---
    print("\n1. FULLY MAKEABLE RECIPES")
    print("-" * 40)
    df = get_makeable_recipes()
    if df.empty:
        print("  No fully makeable recipes found.")
    else:
        for _, row in df.iterrows():
            print(f"  ✓ {row['recipe_name']} ({row['total_ingredients']} ingredients)")
    print(f"  Total: {len(df)}")

    # --- Missing 1-2 ---
    print("\n2. RECIPES MISSING 1-2 INGREDIENTS")
    print("-" * 40)
    df = get_recipes_missing_n(2)
    if df.empty:
        print("  No recipes are just 1-2 ingredients away.")
    else:
        for _, row in df.iterrows():
            missing = row["missing_ingredient_list"]
            if isinstance(missing, list):
                missing_str = ", ".join(missing)
            else:
                missing_str = str(missing)
            print(f"  ~ {row['recipe_name']} (missing {row['missing_ingredients']}: {missing_str})")
    print(f"  Total: {len(df)}")

    # --- With substitutes ---
    print("\n3. RECIPES WITH CATEGORY SUBSTITUTES")
    print("-" * 40)
    df = get_recipes_with_substitutes()
    if df.empty:
        print("  No substitution opportunities found.")
    else:
        for _, row in df.iterrows():
            subs = row["substitute_details"]
            if isinstance(subs, list):
                for s in subs:
                    print(f"  {row['recipe_name']}: {s['missing']} → {s['substitute']} ({s['category']})")
    print(f"  Total: {len(df)}")

    # --- Expiring ---
    print("\n4. RECIPES USING EXPIRING INGREDIENTS")
    print("-" * 40)
    df = get_expiring_recipes()
    if df.empty:
        print("  No recipes use soon-to-expire ingredients.")
    else:
        for _, row in df.iterrows():
            items = row["expiring_ingredient_list"]
            if isinstance(items, list):
                names = [i["name"] for i in items]
                print(f"  ! {row['recipe_name']} (expires: {', '.join(names)})")
    print(f"  Total: {len(df)}")

    # --- Shopping list for first 3 almost-makeable ---
    print("\n5. SHOPPING LIST (for recipes missing 1-3 ingredients)")
    print("-" * 40)
    almost = get_recipes_missing_n(3)
    if almost.empty:
        print("  No almost-makeable recipes to generate a shopping list for.")
    else:
        recipe_ids = almost["recipe_id"].tolist()[:5]
        df = get_shopping_list(recipe_ids)
        if df.empty:
            print("  Shopping list is empty (nothing to buy).")
        else:
            print(f"  {'Ingredient':<25} {'Category':<12} {'Needed By'}")
            print(f"  {'-'*25} {'-'*12} {'-'*30}")
            for _, row in df.iterrows():
                print(
                    f"  {row['ingredient_name']:<25} "
                    f"{row['category']:<12} "
                    f"{row['needed_by_recipes']}"
                )
        print(f"  Total items to buy: {len(df)}")

    # --- Ingredient detail for first recipe ---
    print("\n6. INGREDIENT DETAIL (first recipe)")
    print("-" * 40)
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        first_summary = session.exec(select(RecipeMatchSummary)).first()

    if first_summary:
        print(f"  Recipe: {first_summary.recipe_name}")
        df = get_ingredient_detail(first_summary.recipe_id)
        if not df.empty:
            print(f"  {'Ingredient':<20} {'Available':<10} {'Inventory Item':<20} {'Substitute'}")
            print(f"  {'-'*20} {'-'*10} {'-'*20} {'-'*20}")
            for _, row in df.iterrows():
                avail = "YES" if row["is_available"] else "NO"
                inv = row["inventory_item"] or "-"
                sub = row["substitute"] or "-"
                print(
                    f"  {row['ingredient_name']:<20} "
                    f"{avail:<10} "
                    f"{str(inv):<20} "
                    f"{sub}"
                )
    else:
        print("  No recipe match data found. Run the builder first.")

    print(f"\n{'=' * 70}")
