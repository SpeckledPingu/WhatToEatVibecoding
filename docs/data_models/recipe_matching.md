# Recipe Matching Data Models

## Overview

The recipe matching system determines which recipes can be made with current inventory, which are close to makeable, and which have viable ingredient substitutions. It produces two derived tables that are rebuilt from scratch each time the matching pipeline runs.

## Table Structures

### RecipeIngredientMatch (Detail Table)

One row per ingredient per recipe — the ingredient-level view.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer (PK) | Auto-incrementing unique identifier |
| `recipe_id` | Integer (FK) | References Recipe table |
| `recipe_name` | String | Denormalized recipe name for display convenience |
| `ingredient_name` | String | Normalized ingredient name |
| `ingredient_join_key` | String (indexed) | Join key (e.g., "protein:chicken breast") |
| `ingredient_category` | String | Food category (protein, dairy, etc.) |
| `required_quantity` | Float (optional) | Amount the recipe needs |
| `required_unit` | String (optional) | Unit of measurement |
| `inventory_item_id` | Integer (optional) | FK to ActiveInventory — **NULL if missing** |
| `inventory_item_name` | String (optional) | Matched inventory item name — **NULL if missing** |
| `available_quantity` | Float (optional) | Amount in stock |
| `is_available` | Boolean | True if ingredient found in active inventory |
| `category_substitute_available` | Boolean | True if a same-category substitute exists |
| `substitute_item_name` | String (optional) | Name of potential substitute |
| `created_at` | DateTime | When this record was built |

### RecipeMatchSummary (Summary Table)

One row per recipe — the recipe-level view.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer (PK) | Auto-incrementing unique identifier |
| `recipe_id` | Integer (FK) | References Recipe table |
| `recipe_name` | String | Denormalized recipe name |
| `total_ingredients` | Integer | Total ingredients in recipe |
| `available_ingredients` | Integer | How many are in stock |
| `missing_ingredients` | Integer | How many are NOT in stock |
| `missing_ingredient_list` | JSON | List of missing ingredient names |
| `has_category_substitutes` | Boolean | Any missing ingredient has a substitute |
| `substitute_details` | JSON | Details about available substitutions |
| `is_fully_makeable` | Boolean | True if all ingredients are available |
| `weather_temp` | String (optional) | "warm" or "cold" from recipe |
| `weather_condition` | String (optional) | "rainy", "sunny", "cloudy" from recipe |
| `uses_expiring_ingredients` | Boolean | Any matched ingredient expires within 7 days |
| `expiring_ingredient_list` | JSON (optional) | Expiring ingredient details |
| `created_at` | DateTime | When this summary was built |

## The Matching Algorithm

### Step-by-Step Process

1. **Drop and rebuild** both matching tables (clean slate)
2. **Load** all recipes and all active (non-expired) inventory items
3. **Build lookup structures** — index inventory by join key and category for fast matching
4. **For each recipe:**
   a. Extract and normalize all ingredients using the same pipeline as inventory
   b. For each ingredient, attempt matching:
      - **Exact match**: ingredient join key == inventory join key
      - **Category substitute** (if no exact match): check if a same-sub-category item exists
   c. Check if matched inventory items expire within 7 days
   d. Create a RecipeIngredientMatch row for each ingredient
   e. Create a RecipeMatchSummary row aggregating all ingredients
5. **Insert** all records and print a comprehensive report

### The RIGHT JOIN Concept

```
    INVENTORY (left)              RECIPE INGREDIENTS (right)
    ┌──────────────────┐          ┌──────────────────┐
    │ dairy:butter     │──────────│ dairy:butter     │  ← MATCH
    │ protein:chicken  │──────────│ protein:chicken  │  ← MATCH
    │ grain:rice       │          │ spice:saffron    │  ← NO MATCH (NULL)
    │ vegetable:onion  │──────────│ vegetable:onion  │  ← MATCH
    │ dairy:milk       │          │ dairy:cream      │  ← NO MATCH (NULL)
    └──────────────────┘          └──────────────────┘

    RIGHT JOIN keeps ALL recipe ingredients (right side).
    Where inventory has no match (left side), we get NULL.
    NULL = missing ingredient = something you need to buy.
```

In SQL terms:
```sql
SELECT
    inv.item_name AS inventory_item,
    ri.name AS recipe_ingredient
FROM active_inventory inv
RIGHT JOIN recipe_ingredients ri
    ON inv.join_key = ri.join_key
```

We implement this in Python because:
- SQLite doesn't support RIGHT JOIN directly
- Recipe ingredients are stored in JSON (not their own table)
- Python lets us apply complex normalization and substitution logic

### Exact Match vs. Category/Fuzzy Match

**Exact match**: The ingredient's join key matches an inventory item's join key.
- Recipe needs "protein:chicken breast" → inventory has "protein:chicken breast" → MATCH
- This is the reliable, high-confidence match.

**Category substitute match**: No exact match, but a same-sub-category item exists.
- Recipe needs "dairy:cheddar" → inventory has "dairy:mozzarella" → SUBSTITUTE
- Reliability depends on the category:
  - **Reliable**: pasta shapes (spaghetti ↔ penne), hard cheeses (cheddar ↔ swiss)
  - **Unreliable**: vegetables (carrots ≠ spinach), spices (cumin ≠ cinnamon)
- The `category_substitution_rules` in config define which categories support substitution

## The Rebuild Pattern

Both tables are **derived tables** — they are computed from Recipe and ActiveInventory data and rebuilt from scratch every time the pipeline runs. This means:

- **Never edit these tables directly** — changes would be lost on next rebuild
- **Trigger a rebuild** when: recipes change, inventory changes, or substitution rules change
- **Command**: `uv run python -m src.normalization.build_recipe_matching`

## Example: Tracing a Recipe Through Matching

Recipe: "Chicken Stir Fry" with ingredients:
```json
[
  {"name": "chicken breast", "quantity": 1, "unit": "lb", "category": "protein"},
  {"name": "soy sauce", "quantity": 2, "unit": "tbsp", "category": "condiment"},
  {"name": "broccoli", "quantity": 1, "unit": "head", "category": "vegetable"},
  {"name": "jasmine rice", "quantity": 1, "unit": "cup", "category": "grain"}
]
```

**Step 1: Extract and normalize each ingredient**

| Raw Name | Normalized | Category | Join Key |
|----------|-----------|----------|----------|
| chicken breast | chicken breast | protein | protein:chicken breast |
| soy sauce | soy sauce | condiment | condiment:soy sauce |
| broccoli | broccoli | vegetable | vegetable:broccoli |
| jasmine rice | jasmine rice | grain | grain:jasmine rice |

**Step 2: Match against inventory**

| Ingredient | Join Key | Inventory Match | Status |
|-----------|----------|----------------|--------|
| chicken breast | protein:chicken breast | chicken breast (id=5) | AVAILABLE |
| soy sauce | condiment:soy sauce | soy sauce (id=12) | AVAILABLE |
| broccoli | vegetable:broccoli | NULL | MISSING |
| jasmine rice | grain:jasmine rice | NULL | MISSING (but rice available → sub) |

**Step 3: Check substitutions for missing items**

- broccoli: vegetable category is NOT substitutable → no substitute
- jasmine rice: grain/rice sub-category → rice in inventory → SUBSTITUTE AVAILABLE

**Step 4: Build summary**

| Field | Value |
|-------|-------|
| total_ingredients | 4 |
| available_ingredients | 2 |
| missing_ingredients | 2 |
| missing_ingredient_list | ["broccoli", "jasmine rice"] |
| has_category_substitutes | True |
| substitute_details | [{"missing": "jasmine rice", "substitute": "rice", "category": "grain"}] |
| is_fully_makeable | False |

Result: This recipe is 2 ingredients away from makeable, and one of those has a substitute. If you swap jasmine rice for regular rice, you only need to buy broccoli.
