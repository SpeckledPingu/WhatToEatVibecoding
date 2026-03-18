# Pantry Data Model

## Overview

The `pantryitem` table stores food items observed during kitchen inventory scans. Each row represents one food item found in the pantry, fridge, freezer, or on the counter. This is **state data** — it captures what you currently have on hand.

## Table: `pantryitem`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | Integer | Auto | Primary key, auto-incrementing |
| `item_name` | String | Yes | Food item name (pre-normalized, e.g., "all purpose flour") |
| `quantity` | Float | Yes | Amount on hand (defaults to 1.0, supports fractional amounts) |
| `unit` | String | Yes | Unit of measurement (pounds, container, bag, bottle, etc.) |
| `location` | String | No | Storage location: pantry, fridge, freezer, counter |
| `condition` | String | No | Current state: good, opened, frozen, wilting, expired |
| `category` | String | No | Food category (protein, dairy, vegetable, grain, etc.) |
| `date_inventoried` | Date | Yes | When this inventory snapshot was taken |
| `notes` | Optional | No | Additional context (e.g., "about 0.75 full") |
| `source_file` | String | Yes | CSV filename for data provenance |
| `created_at` | DateTime | Auto | When this record was ingested (UTC) |

## Key Design Decisions

### State vs. Transaction Data
Unlike receipts (which record purchase events), pantry data captures the *current state* of your inventory. A new pantry scan gives you an updated picture of what's on hand.

### Float Quantities
Pantry quantities use float (not integer) because real inventory is often partial: "about 0.75 of a bag" or "half a bottle remaining."

### Location and Condition
These fields are unique to pantry data (receipts don't have them). They're critical for:
- **Shelf life calculations**: the same food lasts different amounts of time in the fridge vs. pantry
- **Use priority**: items marked "wilting" or "opened" should be used first

### Pre-normalized Names
Pantry item names are typically already clean because the AI extraction prompt normalizes them during data collection. This means pantry names are closer to canonical food names than receipt names.

## Example Records

```
| item_name         | qty  | unit      | location | condition | category | date_inventoried |
|-------------------|------|-----------|----------|-----------|----------|------------------|
| all purpose flour | 5    | pounds    | pantry   | good      | grain    | 2026-03-18       |
| chocolate chips   | 1    | bag       | pantry   | opened    | snack    | 2026-03-18       |
| olive oil         | 1    | bottle    | pantry   | opened    | condiment| 2026-03-18       |
```

## Source Data

- **Location**: `data/pantry/` (CSV files)
- **Ingestion script**: `src/ingestion/pantry.py`
- **Model definition**: `src/models/pantry.py`

## Related Tables

- **Receipt**: Purchase transaction data (different schema, different purpose)
- **FoodShelfLife**: Shelf life reference — combined with `date_inventoried` to calculate expiration
- Both are unified through normalization in WS04
