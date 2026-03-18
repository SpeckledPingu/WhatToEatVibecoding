# Food Shelf Life Reference Table

## Overview

The `foodshelflife` table is a **reference table** (also called a lookup table) that stores how long different foods stay fresh under various storage conditions. Unlike receipt or pantry tables that grow with each data import, this table is relatively static — it holds "facts" about food that the rest of the system consults.

## Table: `foodshelflife`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | Integer | Auto | Primary key, auto-incrementing |
| `food_name` | String | Yes | Canonical food name (lowercase), e.g., "chicken breast" |
| `category` | String | Yes | Food category (protein, dairy, grain, etc.) |
| `shelf_life_weeks` | Integer | Yes | How many weeks the food stays good |
| `storage_type` | String | Yes | Storage method: pantry, fridge, freezer, counter |
| `notes` | String | No | Optional storage tips |

## Data Source

This table is seeded from `config/normalization_mappings.json`, which contains two sections:

### Category Defaults (`shelf_life_defaults`)
Broad defaults like "all protein in the fridge lasts 1 week." These serve as fallback values when a specific food item isn't listed.

### Per-Item Overrides (`shelf_life_overrides`)
Specific values like "chicken breast in the fridge lasts 1 week." These take precedence over category defaults for listed items.

## How Expiration Is Calculated

```
expiration_date = date_inventoried + (shelf_life_weeks * 7 days)
is_expired = expiration_date < today
is_active = expiration_date >= today
```

For example: if spinach was inventoried on March 18 and has a shelf life of 1 week, it expires around March 25.

## Example Records

```
| food_name          | category  | shelf_life_weeks | storage_type | notes                      |
|--------------------|-----------|------------------|--------------|-----------------------------|
| chicken breast     | protein   | 1                | fridge       | Specific override           |
| honey              | condiment | 520              | pantry       | ~10 years!                  |
| protein (default)  | protein   | 16               | freezer      | Default for frozen protein  |
```

## Seeding the Table

Run the seed script to populate this table from config:

```bash
uv run python scripts/seed_shelf_life.py
```

The script:
1. Reads both `shelf_life_defaults` and `shelf_life_overrides` from config
2. Creates database records for each entry
3. Scans receipt and pantry data files to identify foods without shelf life entries
4. Prints a report suggesting which items to add to the config

The script is safe to re-run — existing records are updated, not duplicated.

## Customization

To add or adjust shelf life values, edit `config/normalization_mappings.json`:

```json
"shelf_life_overrides": {
    "your_food_item": {"weeks": 2, "storage": "fridge"}
}
```

Then re-run the seed script to load the changes into the database.
