# ActiveInventory — Unified Inventory View

## Overview

The `ActiveInventory` table is a **derived table** that combines receipt and pantry data into a single, normalized view. Unlike the source tables (`Receipt`, `PantryItem`), this table is **rebuilt from scratch** every time the normalization pipeline runs — it's never edited directly.

## Table Structure

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-incrementing unique identifier |
| `item_name` | String (indexed) | Normalized food name (e.g., "butter") |
| `original_name` | String | Name as it appeared in source data (for debugging) |
| `category` | String | Standardized food category (protein, dairy, grain, etc.) |
| `join_key` | String (indexed) | Matching key: `{category}:{item_name}` |
| `quantity` | Float | Amount available |
| `unit` | String | Unit of measurement |
| `source` | String | Data source: "receipt" or "pantry" |
| `source_id` | Integer | ID from the original source table |
| `source_table` | String | Which table source_id refers to |
| `date_acquired` | Date | Purchase date (receipt) or inventory date (pantry) |
| `expiration_date` | Date (nullable) | Calculated: date_acquired + shelf_life_weeks |
| `is_expired` | Boolean | Whether expiration_date < today |
| `created_at` | DateTime | When this record was built (UTC) |

## The Normalization Pipeline

Raw data goes through a multi-step transformation to become unified inventory:

```
Receipt "Greenwise Hmstyle Meatbal Ft"
  → pre-normalized: "meatball"           (from AI extraction)
  → normalized: "meatball"               (alias check — already canonical)
  → category: "protein"                  (from config lookup)
  → join_key: "protein:meatball"         (category:name)
  → shelf_life: 4 weeks (default)        (no specific override)
  → expiration: 2026-04-14               (purchase_date + 4 weeks)
```

### Pipeline Steps

1. **Normalize name**: lowercase, expand abbreviations, strip qualifiers/sizes, resolve aliases
2. **Assign category**: use source category if valid, otherwise look up in config
3. **Create join key**: combine `{category}:{normalized_name}`
4. **Look up shelf life**: check FoodShelfLife table (specific → category default → 4 weeks)
5. **Calculate expiration**: `date_acquired + timedelta(weeks=shelf_life_weeks)`

## Join Key Design

The join key format `{category}:{name}` serves as a shared identifier across all data sources:

| Source | Original Name | Join Key |
|--------|---------------|----------|
| Receipt | "Publix Unsltd Btr Ft" | `dairy:butter` |
| Pantry | "butter" | `dairy:butter` |
| Recipe | "butter" | `dairy:butter` |

Including the category prevents false matches (e.g., "turkey" the protein vs. any other use of the word).

## Expiration Calculation

```
expiration_date = date_acquired + timedelta(weeks=shelf_life_weeks)
is_expired = expiration_date < today
```

**Shelf life lookup order:**
1. Exact match in `FoodShelfLife` table (e.g., "chicken breast" → 1 week)
2. Category default (e.g., "protein (default)" → 1 week for fridge)
3. Ultimate fallback: 4 weeks

These are **approximations** — actual shelf life depends on storage conditions, packaging, and handling.

## The Rebuild Pattern

Every pipeline run **drops and recreates** the ActiveInventory table:
- Ensures no stale or orphaned records
- Handles schema changes automatically
- Guarantees reproducibility (same inputs → same output)
- Simple: no complex change-detection logic needed

**When to rebuild:**
- After adding new receipt or pantry data
- After modifying normalization rules in config
- After updating shelf life data
- Anytime you want a fresh view of your inventory

**How to rebuild:**
```bash
uv run python -m src.normalization.build_inventory
```

## Related Tables

- **Receipt**: Source transaction data (purchases)
- **PantryItem**: Source state data (current inventory)
- **FoodShelfLife**: Reference table for expiration calculation
- **NormalizationMapping**: Config rules loaded into SQL for joins
- **Recipe**: Used for gap analysis (what can you cook with current inventory?)

## Supporting Modules

| Module | Purpose |
|--------|---------|
| `src/normalization/food_names.py` | Name normalization and category extraction |
| `src/normalization/join_keys.py` | Join key creation |
| `src/normalization/build_inventory.py` | Main pipeline orchestrator |
| `src/analytics/normalization_report.py` | Quality validation and reporting |
| `config/normalization_mappings.json` | All normalization rules (source of truth) |
