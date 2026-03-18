"""
recipe_ingredients.py — Extract and normalize ingredients from Recipe JSON fields.

WHY THIS MODULE EXISTS
Recipes store their ingredients as a JSON list inside the Recipe table:
    [{"name": "chicken breast", "quantity": 2, "unit": "lbs", "category": "protein"}, ...]

To match recipe ingredients against inventory, we need to normalize them using
the EXACT SAME pipeline that normalizes receipt and pantry data. If recipe
normalization diverges from inventory normalization — even slightly — matches
will silently fail.

THE SHARED VOCABULARY CONCEPT
Think of normalization as creating a shared language. A receipt says "BNLS SKNLS
CHKN BRST", the pantry says "boneless chicken breast", and a recipe says
"chicken breast". After normalization, ALL three become "chicken breast" with
join key "protein:chicken breast". This shared vocabulary (also called an
"ontology" in data science) is what makes cross-source matching possible.

If you changed the normalization for just ONE source (say, recipes started
lowercasing differently), the vocabulary would fracture and matches would break.
That's why all sources use the same normalize_food_name() → extract_food_category()
→ create_join_key() pipeline defined in this project's normalization modules.

RUN IT:
    uv run python -m src.normalization.recipe_ingredients
"""

from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.recipe import Recipe
from src.normalization.food_names import normalize_food_name, extract_food_category
from src.normalization.join_keys import create_join_key


def extract_recipe_ingredients(recipe: Recipe) -> list[dict]:
    """
    Extract and normalize all ingredients from a single Recipe model instance.

    This function bridges the gap between the recipe's JSON ingredient data and
    the normalized world of join keys. Each ingredient goes through the same
    normalization pipeline used for receipts and pantry items, ensuring that
    "chicken breast" in a recipe matches "chicken breast" in the inventory.

    Parameters:
        recipe: A Recipe model instance with a populated `ingredients` JSON field.

    Returns:
        A list of dicts, one per ingredient, each containing:
          - name: the original ingredient name from the recipe JSON
          - normalized_name: the canonical name after normalization
          - join_key: the matching key (e.g., "protein:chicken breast")
          - category: the standardized food category
          - quantity: how much the recipe requires (float or None)
          - unit: the measurement unit (str or None)

    Example:
        >>> recipe = Recipe(name="Stir Fry", ingredients=[
        ...     {"name": "chicken breast", "quantity": 1, "unit": "lb", "category": "protein"}
        ... ])
        >>> result = extract_recipe_ingredients(recipe)
        >>> result[0]["join_key"]
        'protein:chicken breast'
    """
    extracted = []

    for ingredient in recipe.ingredients:
        # --- Get the raw ingredient name ---
        # The JSON field should have a "name" key, but we guard against
        # malformed data with a fallback to "unknown"
        raw_name = ingredient.get("name", "unknown")

        # --- Normalize using the SAME pipeline as inventory ---
        # This is the critical consistency point: normalize_food_name() applies
        # the same abbreviation expansion, qualifier stripping, and alias
        # resolution that receipts and pantry items go through.
        normalized_name = normalize_food_name(raw_name)

        # --- Determine category ---
        # Use the recipe's provided category if available (the recipe JSON
        # often includes a category from the data creation prompt), then
        # fall back to config-based lookup.
        existing_category = ingredient.get("category")
        category = extract_food_category(normalized_name, existing_category)

        # --- Create the join key ---
        # This is the shared identifier that connects recipe ingredients to
        # inventory items. Same format as inventory: "category:normalized_name"
        join_key = create_join_key(normalized_name, category)

        # --- Extract quantity and unit ---
        quantity = ingredient.get("quantity")
        unit = ingredient.get("unit")

        # Convert quantity to float if possible (recipes may store as int or string)
        if quantity is not None:
            try:
                quantity = float(quantity)
            except (ValueError, TypeError):
                quantity = None

        extracted.append({
            "name": raw_name,
            "normalized_name": normalized_name,
            "join_key": join_key,
            "category": category,
            "quantity": quantity,
            "unit": unit,
        })

    return extracted


# ---------------------------------------------------------------------------
# Demo — show how recipe ingredients normalize and get join keys
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("RECIPE INGREDIENT EXTRACTION — DEMO")
    print("=" * 70)

    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        recipes = session.exec(select(Recipe)).all()

        if not recipes:
            print("\nNo recipes found in the database.")
            print("Run recipe ingestion first: uv run python -m src.ingestion.recipes")
        else:
            print(f"\nFound {len(recipes)} recipes in the database.")
            print()

            all_ingredients = []

            for recipe in recipes:
                ingredients = extract_recipe_ingredients(recipe)
                all_ingredients.extend(ingredients)

                print(f"Recipe: {recipe.name}")
                print(f"  {'Ingredient':<25} {'Normalized':<20} {'Category':<12} {'Join Key'}")
                print(f"  {'-'*25} {'-'*20} {'-'*12} {'-'*30}")

                for ing in ingredients:
                    print(
                        f"  {ing['name']:<25} "
                        f"{ing['normalized_name']:<20} "
                        f"{ing['category']:<12} "
                        f"{ing['join_key']}"
                    )
                print()

            # Summary stats
            unique_keys = set(ing["join_key"] for ing in all_ingredients)
            print(f"Total ingredients across all recipes: {len(all_ingredients)}")
            print(f"Unique ingredient join keys: {len(unique_keys)}")
