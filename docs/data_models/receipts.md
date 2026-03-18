# Receipt Data Model

## Overview

The `receipt` table stores individual line items from store receipts. Each row represents one product purchased during a shopping trip. This is **transaction data** — it records purchase events, not current inventory state.

## Table: `receipt`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | Integer | Auto | Primary key, auto-incrementing |
| `item_name` | String | Yes | Item description as printed on receipt (e.g., "Greenwise Hmstyle Meatbal Ft") |
| `normalized_name` | String | No | Pre-cleaned item name from AI extraction (e.g., "meatball") |
| `quantity` | Integer | Yes | Number of units purchased (defaults to 1) |
| `unit_price` | Float | No | Price per unit (often empty on receipts) |
| `total_price` | Float | No | Total price for this line item |
| `category` | String | No | Food category (protein, dairy, vegetable, grain, etc.) |
| `store_name` | String | Yes | Store where purchased (e.g., "Publix") |
| `purchase_date` | Date | Yes | Date of purchase |
| `source_file` | String | Yes | CSV filename for data provenance |
| `created_at` | DateTime | Auto | When this record was ingested (UTC) |

## Key Design Decisions

### Two Name Fields
- `item_name` preserves the raw receipt text for reference
- `normalized_name` is a pre-cleaned version for matching against pantry and recipe data
- The AI extraction prompt produces both at data collection time

### Data Provenance
The `source_file` field tracks which CSV file each record came from. This is essential for debugging — when a record looks wrong, you can trace it back to the original file.

### Duplicate Detection
During ingestion, duplicates are detected by matching on `item_name + store_name + purchase_date + total_price`. This prevents double-counting when the ingestion script is re-run.

## Example Records

```
| item_name                    | normalized_name | qty | total_price | category  | store  | date       |
|------------------------------|-----------------|-----|-------------|-----------|--------|------------|
| Greenwise Hmstyle Meatbal Ft | meatball        | 1   | 9.59        | protein   | Publix | 2026-03-17 |
| Sar Slcd Provolone Ft        | cheese          | 1   | 4.05        | dairy     | Publix | 2026-03-17 |
| Hass Avocados Lrg Ft         | avocado         | 4   | 6.00        | fruit     | Publix | 2026-03-17 |
```

## Source Data

- **Location**: `data/receipts/` (CSV files)
- **Ingestion script**: `src/ingestion/receipts.py`
- **Model definition**: `src/models/receipt.py`

## Related Tables

- **PantryItem**: Current inventory state (different schema, different purpose)
- **FoodShelfLife**: Shelf life reference for expiration calculations
- Both are unified through normalization in WS04
