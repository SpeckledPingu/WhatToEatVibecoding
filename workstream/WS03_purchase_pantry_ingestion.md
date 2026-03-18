# Workstream 03: Purchase & Pantry Data Ingestion

Ingest store receipt data and pantry inventory data from CSV files into the database. These two data sources have **different schemas** and go into **separate tables**, demonstrating how real-world data sources rarely align perfectly.

## Context

- **Receipt data** (`data/receipts/`): CSV files from photographing store receipts. Records what was bought, when, where, and for how much — a **transaction** record.
- **Pantry data** (`data/pantry/`): CSV files from photographing your pantry where an LLM extracted food items. Records what's currently on hand — a **state snapshot**.

These have fundamentally different structures because they capture different things. A receipt records a purchase event; a pantry scan records current inventory state. They will be normalized and combined into a unified inventory in WS04.

## Instructions

1. **Read and analyze all CSV files** in `data/receipts/` and `data/pantry/`:
   - For each CSV file, read it with pandas and examine:
     - Column names (exact spelling and casing)
     - Data types pandas inferred for each column
     - Number of rows
     - Sample of first 3-5 rows
     - Null/missing value counts per column
     - Unique values for categorical columns (like category, store_name)
   - Print a detailed comparison between receipt columns and pantry columns:
     - Which columns are shared vs unique to each source
     - How item names differ between sources (receipts often have brand/size info, pantry is informal)
     - Date format differences
   - **If no CSV files exist**: stop and inform me that data is needed. Show the extraction prompts from `prompts/receipt_extraction.md` and `prompts/pantry_extraction.md` so I know how to create data with AI assistance. Also create example CSVs in `data/receipts/` and `data/pantry/` matching the formats in `docs/guides/data_formats.md` with 10-15 realistic rows each so I can see the expected format. Then proceed with those example files.

2. **Design the Receipt SQLModel** in `src/models/receipt.py` based on the actual receipt CSV columns:
   - Examine the actual columns in the CSV files and include ALL of them in the model
   - The model **MUST** include these fields (add them if not in the CSV, using sensible defaults):
     - `id`: Integer primary key, auto-incrementing
     - `item_name`: String, required — the item as printed on the receipt
     - `normalized_name`: Optional string — a pre-cleaned version of the item name (may be provided by the AI extraction prompt in `prompts/receipt_extraction.md`; if this column exists in the CSV, use it during normalization in WS04 instead of cleaning `item_name` from scratch)
     - `quantity`: Integer or float — how many were purchased
     - `unit_price`: Optional float — price per unit
     - `total_price`: Optional float — total price for this line
     - `category`: Optional string — the store's category for the item
     - `store_name`: String — which store this was purchased from
     - `purchase_date`: Date — when the purchase was made
     - `source_file`: String — which CSV file this row came from
     - `created_at`: DateTime — when this record was ingested
   - Include any additional columns found in the actual CSV data
   - Add educational docstrings explaining:
     - Why we track `source_file` (data provenance — knowing where each record came from)
     - The difference between the receipt table (raw transaction data) and later normalized tables

3. **Design the Pantry SQLModel** in `src/models/pantry.py` based on the actual pantry CSV columns:
   - Examine the actual columns and include ALL of them
   - The model **MUST** include:
     - `id`: Integer primary key, auto-incrementing
     - `item_name`: String, required — the food item name
     - `quantity`: Float — how much is on hand
     - `unit`: String — unit of measurement (pounds, whole, bag, bottle, etc.)
     - `location`: Optional string — where stored (fridge, freezer, pantry, counter)
     - `condition`: Optional string — current state (good, wilting, frozen, opened)
     - `category`: Optional string — food category
     - `date_inventoried`: Date — when this inventory snapshot was taken
     - `notes`: Optional string — any additional notes
     - `source_file`: String — which CSV this came from
     - `created_at`: DateTime — ingestion timestamp
   - Include any additional columns found in the actual CSV data
   - Educational docstrings explaining how this differs from the receipt model

4. **Create a food shelf life reference table** in `src/models/shelf_life.py`:
   - Model `FoodShelfLife`:
     - `id`: Integer primary key
     - `food_name`: String — canonical food name (lowercase, simple)
     - `category`: String — food category matching our standard categories
     - `shelf_life_weeks`: Integer — how many weeks this food typically stays good
     - `storage_type`: String — "pantry", "fridge", or "freezer"
     - `notes`: Optional string — storage tips
   - Educational docstrings explaining:
     - What a reference/lookup table is and why it's useful
     - How this will be used to calculate expiration dates
   - Create a seed script at `scripts/seed_shelf_life.py` that:
     - **Reads shelf life data from `config/normalization_mappings.json`** — both the `shelf_life_defaults` (by category) and `shelf_life_overrides` (by specific food item) sections
     - Also examines the actual food items found in receipt and pantry data files to add any items not yet in the config
     - Populates the FoodShelfLife table from the config data
     - Prints what was seeded and which items from the data files had no config entry (suggesting the student add them to the config file)
     - Can be re-run safely (upserts or skips existing entries)
     - Includes comments explaining: why shelf life data lives in a config file (easy to edit without code changes), how the config file is also a SQL table (demonstrating data-driven lookups), and the seed data pattern

5. **Create ingestion scripts**:
   - `src/ingestion/receipts.py`:
     - A function `ingest_receipts()` that scans `data/receipts/` for CSV files
     - Read each CSV with pandas, handling potential issues:
       - Column name normalization (strip whitespace, lowercase)
       - Date parsing (try multiple formats)
       - Numeric type conversion for prices and quantities
       - Missing value handling
     - Check for duplicates (same item, store, date, price) and skip them
     - Insert rows into the database
     - Print a report: files processed, rows per file, total rows added, any data quality issues found
     - Educational comments explaining each pandas operation and data cleaning step
     - Runnable directly: `if __name__ == "__main__": ingest_receipts()`

   - `src/ingestion/pantry.py`:
     - Same pattern as receipts but for pantry CSV files
     - A function `ingest_pantry()` that scans `data/pantry/` for CSV files
     - Same data quality handling: column normalization, date parsing, type conversion
     - Duplicate handling based on item name + date inventoried
     - Print a similar report
     - Educational comments
     - Runnable directly

6. **Create a data comparison analysis** at `src/analytics/data_comparison.py`:
   - Load both receipt and pantry data from the database into pandas DataFrames
   - Print a side-by-side comparison report:
     - Column names in each table
     - Number of records in each
     - Unique item names from each source (first 20)
     - Examples of the same food described differently between sources (e.g., "Organic Whole Milk 1gal" in receipts vs "milk" in pantry)
     - Data type comparison for similar fields
     - Category overlap: what categories exist in each source
   - Include educational commentary:
     - WHY these datasets look different (different collection methods, different levels of detail)
     - What problems this creates for combining them (the normalization challenge)
     - Preview of what WS04 will do to solve it
   - Make runnable directly

7. **Run the ingestion scripts** in order:
   ```
   uv run python scripts/seed_shelf_life.py
   uv run python -m src.ingestion.receipts
   uv run python -m src.ingestion.pantry
   ```

8. **Run the comparison analysis** to show the differences:
   ```
   uv run python -m src.analytics.data_comparison
   ```

9. **Create data model documentation**:
   - `docs/data_models/receipts.md` — Receipt table structure, fields, and example records
   - `docs/data_models/pantry.md` — Pantry table structure, fields, and example records
   - `docs/data_models/shelf_life.md` — Shelf life reference table and how it's used

## Things to Try After This Step

- Compare item names between receipts and pantry — notice how "2% Milk" on a receipt might be "milk" in the pantry scan. This is the real-world data alignment challenge!
- Check your shelf life table: `uv run python -c "from sqlmodel import Session, select; from src.models.shelf_life import FoodShelfLife; from src.database import get_engine; s = Session(get_engine()); [print(f'{f.food_name}: {f.shelf_life_weeks} weeks ({f.storage_type})') for f in s.exec(select(FoodShelfLife)).all()]"`
- Add a new receipt CSV from a different store and re-run ingestion — observe how it handles new data
- Try `uv run python -c "import pandas as pd; df = pd.read_csv('data/receipts/YOUR_FILE.csv'); print(df.dtypes)"` to see how pandas interprets your CSV data types
- Think about what "join key" you would use to connect receipt items to pantry items — they don't share an ID!
- Ask Claude Code: "What are my most frequently purchased items from receipts?"
- Look at items in the shelf life table — adjust the weeks for items you know better (e.g., your bread might last longer if you freeze it)
