# Workstream 05: Recipe Matching, Views & Expiration Tracking

Build the core intelligence of the application: determining which recipes can be made with current inventory, which need a few more ingredients, and which have viable substitutions. This uses JOIN operations — one of the most powerful concepts in relational databases.

## Context

With recipes in one table and active inventory in another, we need to connect them. The key technique is a **RIGHT JOIN** (conceptually): start from the recipe ingredients (right side) and look for matches in inventory (left side). Where there's no match in inventory, we have a **missing ingredient** — the NULL in the left side of the join tells us what we don't have.

We also build derived tables for:
- Recipes that are **fully makeable** right now (all ingredients available)
- Recipes missing **N or fewer** ingredients (almost makeable)
- Recipes where missing ingredients have a **category-level substitute** in inventory (e.g., missing cheddar but have mozzarella — both dairy)

## Instructions

1. **Analyze the current state** of recipe ingredients and active inventory:
   - Extract all unique ingredient names and their join keys from the Recipe table's JSON ingredient fields
   - Extract all unique item names and join keys from the ActiveInventory table
   - Print a **match analysis**:
     - How many unique recipe ingredients exist
     - How many unique inventory items exist
     - How many recipe ingredients have an exact join key match in inventory
     - How many recipe ingredients have NO match (these are the gaps)
     - List the unmatched ingredients (these are things you'd need to buy)
     - How many inventory items don't appear in any recipe (items you have but no recipe uses)
   - This analysis informs the matching logic and shows students how to evaluate data alignment

2. **Create ingredient extraction and normalization** at `src/normalization/recipe_ingredients.py`:
   - A function `extract_recipe_ingredients(recipe) -> list[dict]` that:
     - Takes a Recipe model instance
     - Extracts individual ingredients from the JSON `ingredients` field
     - For each ingredient, applies the SAME normalization used for inventory:
       - `normalize_food_name()` on the ingredient name
       - `extract_food_category()` on the ingredient
       - `create_join_key()` to make the matching key
     - Returns a list of dicts with: `name`, `normalized_name`, `join_key`, `category`, `quantity`, `unit`
   - Educational comments explaining:
     - Why consistent normalization across ALL data sources is critical (if recipe says "chicken" and inventory says "chicken" but they normalize differently, the match fails)
     - The concept of a shared vocabulary/ontology across datasets

3. **Create the recipe matching models** in `src/models/recipe_matching.py`:

   **Model 1: `RecipeIngredientMatch`** — one row per ingredient per recipe:
   - `id`: Integer primary key
   - `recipe_id`: Integer — foreign key to Recipe table
   - `recipe_name`: String — denormalized for convenient display
   - `ingredient_name`: String — the normalized ingredient name
   - `ingredient_join_key`: String — the join key for this ingredient
   - `ingredient_category`: String — the food category
   - `required_quantity`: Optional float — how much the recipe needs
   - `required_unit`: Optional string — unit needed
   - `inventory_item_id`: Optional integer — FK to ActiveInventory (NULL if not in stock)
   - `inventory_item_name`: Optional string — what's actually in inventory (NULL if missing)
   - `available_quantity`: Optional float — how much is in stock
   - `is_available`: Boolean — True if this ingredient is in stock (inventory match found)
   - `category_substitute_available`: Boolean — True if a same-category item exists in inventory
   - `substitute_item_name`: Optional string — name of the potential substitute
   - `created_at`: DateTime

   **Model 2: `RecipeMatchSummary`** — one row per recipe, aggregating the ingredient matches:
   - `id`: Integer primary key
   - `recipe_id`: Integer — foreign key to Recipe table
   - `recipe_name`: String
   - `total_ingredients`: Integer — total ingredients in the recipe
   - `available_ingredients`: Integer — how many are in stock
   - `missing_ingredients`: Integer — how many are NOT in stock
   - `missing_ingredient_list`: JSON field — list of missing ingredient names
   - `has_category_substitutes`: Boolean — any missing ingredient has a same-category substitute
   - `substitute_details`: JSON field — details about available substitutions
   - `is_fully_makeable`: Boolean — True if missing_ingredients == 0
   - `weather_temp`: Optional string — from the recipe (for weather filtering)
   - `weather_condition`: Optional string — from the recipe
   - `uses_expiring_ingredients`: Boolean — any matched ingredient expires within 7 days
   - `expiring_ingredient_list`: Optional JSON field — which ingredients are expiring
   - `created_at`: DateTime

   Educational docstrings explaining:
   - Why two tables: detail (per-ingredient) and summary (per-recipe) — different queries need different granularity
   - What denormalization means and why `recipe_name` is duplicated (convenience vs normalization tradeoff)
   - The role of NULL values in the join: NULL `inventory_item_id` means "missing ingredient"

4. **Create the recipe matching builder** at `src/normalization/build_recipe_matching.py`:
   - A function `build_recipe_matching()` that:
     - **Drops and rebuilds** both `RecipeIngredientMatch` and `RecipeMatchSummary` tables (same rebuild pattern as ActiveInventory)
     - Loads all recipes and all active (non-expired) inventory items
     - For each recipe:
       - Extracts and normalizes all ingredients using `extract_recipe_ingredients()`
       - For each ingredient, attempts to find a match in inventory:
         1. **Exact join key match**: ingredient join key == inventory join key (this is the RIGHT JOIN concept — we start from the recipe ingredient and look left into inventory)
         2. **Category match** (if no exact match): consult the `category_substitution_rules` in `config/normalization_mappings.json`. If the missing ingredient's category has `substitutable_within_subcategory: true`, look for inventory items in the same **sub-category** (e.g., "cheddar" and "mozzarella" are both in the "cheese_hard"/"cheese_soft" sub-categories under dairy). This is the fuzzy/substitute match. Categories marked as NOT substitutable (like vegetables and spices) should be flagged as unreliable suggestions.
       - Records each ingredient match as a `RecipeIngredientMatch` row
       - Checks if matched inventory items expire within 7 days
     - After processing all ingredients for a recipe, creates a `RecipeMatchSummary`:
       - Counts available vs missing
       - Builds the missing ingredient list
       - Determines if fully makeable
       - Records substitution opportunities
       - Flags expiring ingredients
     - Prints a **comprehensive report**:
       - Total recipes evaluated
       - Fully makeable recipes (with names)
       - Recipes needing just 1-2 more ingredients (with what's missing)
       - Most common missing ingredients across all recipes (this is your shopping list!)
       - Substitution opportunities found (e.g., "Recipe X needs cheddar, you have mozzarella (both dairy)")
       - Recipes that use expiring ingredients (make these first!)
     - Educational comments explaining:
       - How the RIGHT JOIN concept works even though we're implementing it in Python (iterating recipe ingredients and looking for inventory matches)
       - Why we rebuild this table rather than maintaining it as a live database view (educational value of understanding rebuild patterns, plus SQLite views can't easily do this JSON-to-join logic)
       - How this pattern of "match, score, rank" applies to recommendation systems generally
   - Make runnable directly

5. **Create query helper functions** at `src/analytics/recipe_queries.py`:
   - `get_makeable_recipes() -> pd.DataFrame` — recipes where `is_fully_makeable = True`
   - `get_recipes_missing_n(n: int) -> pd.DataFrame` — recipes missing N or fewer ingredients, sorted by fewest missing first
   - `get_recipes_with_substitutes() -> pd.DataFrame` — recipes where category substitutes exist for missing ingredients
   - `get_expiring_recipes() -> pd.DataFrame` — recipes using ingredients that expire within 7 days, sorted by soonest expiration
   - `get_shopping_list(recipe_ids: list[int]) -> pd.DataFrame` — consolidated, deduplicated list of missing ingredients for the specified recipes
   - `get_ingredient_detail(recipe_id: int) -> pd.DataFrame` — full ingredient match detail for one recipe
   - Each function:
     - Queries the database and returns a pandas DataFrame
     - Includes an educational docstring explaining the query logic
     - Can be called from scripts, notebooks, or the API layer
   - Include a main section that demos all functions with formatted output
   - Make runnable directly

6. **Create an expiration priority script** at `src/analytics/expiration_priority.py`:
   - Identify inventory items expiring in the next 7 days
   - Cross-reference with makeable recipes to find "use it up" recipes
   - Rank recipes by how many expiring ingredients they use
   - Print a prioritized recommendation:
     ```
     ⚠️  EXPIRING SOON:
       - spinach (expires in 2 days)
       - chicken breast (expires in 5 days)

     🍳 MAKE THESE FIRST (uses expiring ingredients):
       1. Chicken Stir Fry (uses: chicken breast, spinach)
       2. Spinach Salad (uses: spinach)
     ```
   - Include a simple matplotlib chart of the expiration timeline
   - Educational comments about how businesses use similar prioritization
   - Make runnable directly

7. **Run the recipe matching builder**:
   ```
   uv run python -m src.normalization.build_recipe_matching
   ```

8. **Run the query helpers and expiration script**:
   ```
   uv run python -m src.analytics.recipe_queries
   uv run python -m src.analytics.expiration_priority
   ```

9. **Create documentation** at `docs/data_models/recipe_matching.md`:
   - Both table structures with field descriptions
   - The matching algorithm explained step by step
   - The RIGHT JOIN concept with a diagram (ASCII art is fine)
   - Exact match vs category/fuzzy match explained
   - The rebuild pattern and when to trigger it
   - Example: trace one recipe through the matching process

## Things to Try After This Step

- Ask Claude Code: "What recipes can I make right now?"
- Ask Claude Code: "What recipes am I just one ingredient away from making?"
- Ask Claude Code: "Generate a shopping list for the top 3 almost-makeable recipes"
- Look at category substitutions — do they make sense? Is "cheddar" really interchangeable with "mozzarella" just because both are "dairy"? How would you make the matching smarter?
- Add a new recipe and re-run matching to see it get evaluated against your inventory
- Modify a recipe to use an ingredient you have and re-run — watch it become makeable
- Ask Claude Code: "What are my most commonly missing ingredients across all recipes?"
- Think about quantity matching — right now we only check if an ingredient EXISTS, not if you have ENOUGH. How would you add quantity comparison?
- Ask Claude Code: "Create a Jupyter notebook that visualizes the recipe matching results as a heatmap"
