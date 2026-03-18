"""
build_recipe_matching.py — Build recipe-to-inventory matching tables.

WHAT THIS SCRIPT DOES
This is the recipe recommendation engine. It connects recipes to your inventory
to answer: "What can I cook with what I have?" For each recipe, it checks every
ingredient against your active (non-expired) inventory, records matches and
misses, and builds summary tables for easy querying.

THE RIGHT JOIN CONCEPT
In SQL, a RIGHT JOIN returns ALL rows from the right table and matched rows from
the left table. Where there's no match on the left, you get NULL:

    SELECT inventory.item_name, recipe_ingredients.name
    FROM inventory
    RIGHT JOIN recipe_ingredients
      ON inventory.join_key = recipe_ingredients.join_key

    Result:
    inventory_item  | recipe_ingredient
    ─────────────── | ─────────────────
    butter          | butter            ← MATCH (you have it)
    NULL            | saffron           ← MISS (NULL = missing ingredient)
    chicken breast  | chicken breast    ← MATCH

Since SQLite doesn't support RIGHT JOIN directly, and our recipe ingredients
live inside JSON fields (not in their own table), we implement this logic in
Python. But the CONCEPT is identical: iterate through recipe ingredients (right
side) and look for matches in inventory (left side).

THE MATCH, SCORE, RANK PATTERN
This pipeline follows a pattern used throughout recommendation systems:
  1. MATCH: Find connections between items (ingredient ↔ inventory)
  2. SCORE: Rate how good each match is (exact match > category substitute > missing)
  3. RANK: Order results by score (fully makeable > missing 1 > missing 2 > ...)

Netflix uses this for movie recommendations, Amazon for product suggestions,
and Spotify for playlist generation. The data is different, but the pattern
is the same.

WHY REBUILD INSTEAD OF A DATABASE VIEW?
  - SQLite views can't easily parse JSON arrays and join each element
  - The rebuild pattern lets us do complex Python logic (normalization,
    category substitution lookup) that SQL can't express
  - Educational value: students see the matching algorithm step by step
  - Same rebuild pattern as ActiveInventory — consistency in the codebase

RUN IT:
    uv run python -m src.normalization.build_recipe_matching
"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select, SQLModel

from src.database import create_db_and_tables, get_engine
from src.models.recipe import Recipe
from src.models.inventory import ActiveInventory
from src.models.recipe_matching import RecipeIngredientMatch, RecipeMatchSummary
from src.normalization.recipe_ingredients import extract_recipe_ingredients
from src.normalization.food_names import load_normalization_config


def _find_category_substitute(
    ingredient_name: str,
    ingredient_category: str,
    inventory_by_category: dict[str, list[dict]],
    config: dict,
) -> tuple[bool, str | None]:
    """
    Check if a category-level substitute exists in inventory for a missing ingredient.

    SUBSTITUTION LOGIC
    Not all categories support substitution. The category_substitution_rules in
    the config define which categories allow swaps and organize foods into
    sub-categories for smarter matching:

      - protein: poultry sub-category (chicken ↔ turkey), but NOT poultry ↔ tofu
      - dairy: cheese_hard sub-category (cheddar ↔ swiss), but NOT hard ↔ soft cheese
      - grain: pasta sub-category (spaghetti ↔ penne)
      - vegetable, fruit, spice, condiment: NOT substitutable

    Parameters:
        ingredient_name: The normalized name of the missing ingredient.
        ingredient_category: The food category of the missing ingredient.
        inventory_by_category: Dict mapping category → list of inventory item dicts.
        config: The normalization config containing substitution rules.

    Returns:
        A tuple of (substitute_available, substitute_name).
    """
    sub_rules = config.get("category_substitution_rules", {})
    category_rule = sub_rules.get(ingredient_category, {})

    # If this category doesn't support substitution, no substitute
    if not category_rule.get("substitutable_within_subcategory", False):
        return False, None

    sub_categories = category_rule.get("sub_categories", {})

    # Find which sub-category the missing ingredient belongs to
    ingredient_sub = None
    for sub_name, members in sub_categories.items():
        if ingredient_name in [m.lower() for m in members]:
            ingredient_sub = sub_name
            break

    if ingredient_sub is None:
        # Ingredient not in any sub-category — can't do smart matching
        return False, None

    # Get all inventory items in the same category
    category_inventory = inventory_by_category.get(ingredient_category, [])

    # Look for an inventory item in the SAME sub-category
    sub_members = [m.lower() for m in sub_categories.get(ingredient_sub, [])]
    for inv_item in category_inventory:
        if (
            inv_item["item_name"] != ingredient_name
            and inv_item["item_name"] in sub_members
        ):
            return True, inv_item["item_name"]

    return False, None


def _analyze_current_state(
    session: Session,
    recipes: list[Recipe],
    active_inventory: list[ActiveInventory],
):
    """
    Print an analysis of recipe ingredients vs. inventory BEFORE building matches.

    This is Step 1 from the workstream — understanding data alignment before
    trying to match. It reveals how many ingredients can match, how many gaps
    exist, and what's in inventory but unused by any recipe.
    """
    print("\n" + "=" * 70)
    print("MATCH ANALYSIS — Recipe Ingredients vs. Active Inventory")
    print("=" * 70)

    # Extract all unique recipe ingredient join keys
    recipe_join_keys = {}  # join_key → ingredient_name
    for recipe in recipes:
        ingredients = extract_recipe_ingredients(recipe)
        for ing in ingredients:
            recipe_join_keys[ing["join_key"]] = ing["normalized_name"]

    # Extract all unique inventory join keys
    inventory_join_keys = {}  # join_key → item_name
    for item in active_inventory:
        inventory_join_keys[item.join_key] = item.item_name

    # Compute matches and gaps
    recipe_keys = set(recipe_join_keys.keys())
    inventory_keys = set(inventory_join_keys.keys())
    matched_keys = recipe_keys & inventory_keys
    unmatched_recipe = recipe_keys - inventory_keys
    unused_inventory = inventory_keys - recipe_keys

    print(f"\n  Unique recipe ingredients:    {len(recipe_keys)}")
    print(f"  Unique inventory items:       {len(inventory_keys)}")
    print(f"  Exact join key matches:       {len(matched_keys)}")
    print(f"  Recipe ingredients NOT in inventory: {len(unmatched_recipe)} (gaps)")
    print(f"  Inventory items NOT in any recipe:   {len(unused_inventory)}")

    if unmatched_recipe:
        print(f"\n  UNMATCHED recipe ingredients (you'd need to buy these):")
        for key in sorted(unmatched_recipe):
            print(f"    - {recipe_join_keys[key]} ({key})")

    if unused_inventory:
        print(f"\n  UNUSED inventory items (not in any recipe):")
        for key in sorted(unused_inventory):
            print(f"    - {inventory_join_keys[key]} ({key})")

    print()


def build_recipe_matching():
    """
    Build the RecipeIngredientMatch and RecipeMatchSummary tables.

    This is the main function that implements the recipe matching algorithm.
    It processes every recipe, checks each ingredient against inventory, and
    produces both detail and summary tables for querying.
    """
    print("=" * 70)
    print("BUILDING RECIPE MATCHING TABLES")
    print("=" * 70)

    engine = get_engine()
    create_db_and_tables(engine)

    config = load_normalization_config()
    today = date.today()
    expiry_window = today + timedelta(days=7)

    # ------------------------------------------------------------------
    # Step 1: Drop and rebuild both matching tables
    # ------------------------------------------------------------------
    # Same REBUILD pattern as ActiveInventory — start fresh every time.
    # This ensures the matching tables always reflect the current state
    # of recipes and inventory.
    print("\nStep 1: Dropping and recreating matching tables...")
    RecipeIngredientMatch.metadata.drop_all(
        engine, tables=[RecipeIngredientMatch.__table__]
    )
    RecipeMatchSummary.metadata.drop_all(
        engine, tables=[RecipeMatchSummary.__table__]
    )
    RecipeIngredientMatch.metadata.create_all(
        engine, tables=[RecipeIngredientMatch.__table__]
    )
    RecipeMatchSummary.metadata.create_all(
        engine, tables=[RecipeMatchSummary.__table__]
    )
    print("  Tables recreated (clean slate)")

    with Session(engine) as session:
        # ------------------------------------------------------------------
        # Step 2: Load recipes and active inventory
        # ------------------------------------------------------------------
        print("\nStep 2: Loading recipes and active inventory...")
        recipes = session.exec(select(Recipe)).all()
        print(f"  Found {len(recipes)} recipes")

        # Only consider non-expired inventory items
        active_inventory = session.exec(
            select(ActiveInventory).where(ActiveInventory.is_expired == False)  # noqa: E712
        ).all()
        print(f"  Found {len(active_inventory)} active (non-expired) inventory items")

        if not recipes:
            print("\n  No recipes found. Run recipe ingestion first:")
            print("    uv run python -m src.ingestion.recipes")
            return

        # ------------------------------------------------------------------
        # Step 3: Pre-analysis — understand data alignment
        # ------------------------------------------------------------------
        _analyze_current_state(session, recipes, active_inventory)

        # ------------------------------------------------------------------
        # Step 4: Build lookup structures for fast matching
        # ------------------------------------------------------------------
        # Instead of querying the database for each ingredient, build in-memory
        # lookups. This is MUCH faster for the O(recipes × ingredients) matching.
        print("Step 4: Building inventory lookup structures...")

        # join_key → list of inventory items (there may be multiple, e.g.,
        # butter from both receipt and pantry)
        inventory_by_key: dict[str, list[ActiveInventory]] = {}
        inventory_by_category: dict[str, list[dict]] = {}

        for item in active_inventory:
            inventory_by_key.setdefault(item.join_key, []).append(item)
            inventory_by_category.setdefault(item.category, []).append({
                "item_name": item.item_name,
                "join_key": item.join_key,
                "id": item.id,
                "quantity": item.quantity,
                "expiration_date": item.expiration_date,
            })

        print(f"  {len(inventory_by_key)} unique inventory join keys indexed")

        # ------------------------------------------------------------------
        # Step 5: Match each recipe's ingredients against inventory
        # ------------------------------------------------------------------
        # This is the RIGHT JOIN implementation in Python:
        # For each recipe ingredient (right side), look for a match in
        # inventory (left side). No match → NULL (missing ingredient).
        print("\nStep 5: Matching recipe ingredients against inventory...")

        all_match_rows = []
        all_summary_rows = []

        # Track stats for the report
        fully_makeable = []
        almost_makeable = []  # missing 1-2 ingredients
        all_missing = Counter()  # most common missing ingredients
        substitution_opportunities = []
        expiring_recipes = []

        for recipe in recipes:
            ingredients = extract_recipe_ingredients(recipe)

            match_rows = []
            available_count = 0
            missing_count = 0
            missing_names = []
            sub_details = []
            uses_expiring = False
            expiring_list = []

            for ing in ingredients:
                # --- Attempt exact join key match ---
                matched_items = inventory_by_key.get(ing["join_key"], [])

                if matched_items:
                    # MATCH FOUND — this ingredient is in inventory
                    # Use the first match (there may be multiples from different sources)
                    best_match = matched_items[0]

                    # Check if this matched item is expiring soon
                    is_expiring = (
                        best_match.expiration_date is not None
                        and best_match.expiration_date <= expiry_window
                    )
                    if is_expiring:
                        uses_expiring = True
                        days_left = (best_match.expiration_date - today).days
                        expiring_list.append({
                            "name": best_match.item_name,
                            "expiration_date": str(best_match.expiration_date),
                            "days_until_expiry": days_left,
                        })

                    match_row = RecipeIngredientMatch(
                        recipe_id=recipe.id,
                        recipe_name=recipe.name,
                        ingredient_name=ing["normalized_name"],
                        ingredient_join_key=ing["join_key"],
                        ingredient_category=ing["category"],
                        required_quantity=ing["quantity"],
                        required_unit=ing["unit"],
                        inventory_item_id=best_match.id,
                        inventory_item_name=best_match.item_name,
                        available_quantity=best_match.quantity,
                        is_available=True,
                        category_substitute_available=False,
                        substitute_item_name=None,
                    )
                    available_count += 1

                else:
                    # NO MATCH — this ingredient is missing from inventory
                    # This is the NULL in the left side of our RIGHT JOIN
                    missing_count += 1
                    missing_names.append(ing["normalized_name"])
                    all_missing[ing["normalized_name"]] += 1

                    # --- Check for category substitute ---
                    sub_available, sub_name = _find_category_substitute(
                        ing["normalized_name"],
                        ing["category"],
                        inventory_by_category,
                        config,
                    )

                    if sub_available:
                        sub_details.append({
                            "missing": ing["normalized_name"],
                            "substitute": sub_name,
                            "category": ing["category"],
                        })
                        substitution_opportunities.append({
                            "recipe": recipe.name,
                            "missing": ing["normalized_name"],
                            "substitute": sub_name,
                            "category": ing["category"],
                        })

                    match_row = RecipeIngredientMatch(
                        recipe_id=recipe.id,
                        recipe_name=recipe.name,
                        ingredient_name=ing["normalized_name"],
                        ingredient_join_key=ing["join_key"],
                        ingredient_category=ing["category"],
                        required_quantity=ing["quantity"],
                        required_unit=ing["unit"],
                        inventory_item_id=None,
                        inventory_item_name=None,
                        available_quantity=None,
                        is_available=False,
                        category_substitute_available=sub_available,
                        substitute_item_name=sub_name,
                    )

                match_rows.append(match_row)

            # --- Build the summary row for this recipe ---
            is_makeable = missing_count == 0

            summary = RecipeMatchSummary(
                recipe_id=recipe.id,
                recipe_name=recipe.name,
                total_ingredients=len(ingredients),
                available_ingredients=available_count,
                missing_ingredients=missing_count,
                missing_ingredient_list=missing_names,
                has_category_substitutes=len(sub_details) > 0,
                substitute_details=sub_details,
                is_fully_makeable=is_makeable,
                weather_temp=recipe.weather_temp,
                weather_condition=recipe.weather_condition,
                uses_expiring_ingredients=uses_expiring,
                expiring_ingredient_list=expiring_list if expiring_list else None,
            )

            all_match_rows.extend(match_rows)
            all_summary_rows.append(summary)

            # Track for report
            if is_makeable:
                fully_makeable.append(recipe.name)
            elif missing_count <= 2:
                almost_makeable.append({
                    "name": recipe.name,
                    "missing": missing_names,
                })
            if uses_expiring:
                expiring_recipes.append({
                    "name": recipe.name,
                    "expiring": expiring_list,
                })

        # ------------------------------------------------------------------
        # Step 6: Insert all records
        # ------------------------------------------------------------------
        print(f"\nStep 6: Inserting matching records...")
        for row in all_match_rows:
            session.add(row)
        for row in all_summary_rows:
            session.add(row)
        session.commit()
        print(f"  Inserted {len(all_match_rows)} ingredient match records")
        print(f"  Inserted {len(all_summary_rows)} recipe summary records")

    # ------------------------------------------------------------------
    # Step 7: Print comprehensive report
    # ------------------------------------------------------------------
    _print_matching_report(
        total_recipes=len(recipes),
        fully_makeable=fully_makeable,
        almost_makeable=almost_makeable,
        all_missing=all_missing,
        substitution_opportunities=substitution_opportunities,
        expiring_recipes=expiring_recipes,
    )


def _print_matching_report(
    total_recipes: int,
    fully_makeable: list[str],
    almost_makeable: list[dict],
    all_missing: Counter,
    substitution_opportunities: list[dict],
    expiring_recipes: list[dict],
):
    """Print a comprehensive report of recipe matching results."""
    print()
    print("=" * 70)
    print("RECIPE MATCHING REPORT")
    print("=" * 70)

    # --- Overview ---
    print(f"\nTotal recipes evaluated: {total_recipes}")

    # --- Fully makeable ---
    print(f"\nFULLY MAKEABLE recipes ({len(fully_makeable)}):")
    if fully_makeable:
        for name in fully_makeable:
            print(f"  ✓ {name}")
    else:
        print("  (none — you need to go shopping!)")

    # --- Almost makeable (1-2 ingredients missing) ---
    print(f"\nALMOST MAKEABLE recipes (missing 1-2 ingredients): {len(almost_makeable)}")
    if almost_makeable:
        for recipe in almost_makeable:
            missing_str = ", ".join(recipe["missing"])
            print(f"  ~ {recipe['name']} (needs: {missing_str})")
    else:
        print("  (none)")

    # --- Most common missing ingredients (shopping list) ---
    print(f"\nMOST COMMON MISSING INGREDIENTS (your shopping list!):")
    if all_missing:
        for ingredient, count in all_missing.most_common(15):
            print(f"  {count:>3}x  {ingredient}")
    else:
        print("  (none — you have everything!)")

    # --- Substitution opportunities ---
    print(f"\nSUBSTITUTION OPPORTUNITIES ({len(substitution_opportunities)}):")
    if substitution_opportunities:
        for sub in substitution_opportunities:
            print(
                f"  {sub['recipe']}: needs {sub['missing']}, "
                f"you have {sub['substitute']} (both {sub['category']})"
            )
    else:
        print("  (none found)")

    # --- Expiring ingredient recipes ---
    print(f"\nRECIPES USING EXPIRING INGREDIENTS ({len(expiring_recipes)}):")
    if expiring_recipes:
        print("  (Cook these first to avoid waste!)")
        for recipe in expiring_recipes:
            expiring_names = [e["name"] for e in recipe["expiring"]]
            print(f"  ! {recipe['name']} (uses: {', '.join(expiring_names)})")
    else:
        print("  (no ingredients expiring within 7 days)")

    print(f"\n{'=' * 70}")
    print("Run query helpers for more analysis:")
    print("  uv run python -m src.analytics.recipe_queries")
    print("  uv run python -m src.analytics.expiration_priority")


if __name__ == "__main__":
    build_recipe_matching()
