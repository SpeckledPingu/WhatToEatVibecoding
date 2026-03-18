# Workstream 04: Data Cleaning, Normalization & Unified Inventory

Clean and normalize the receipt and pantry data so they can be combined into a unified inventory view. This is one of the most important workstreams — it demonstrates the real-world challenge of making different data sources work together.

## Context

Receipt data and pantry data describe similar things (food items) but use different:
- **Names**: "Organic Whole Milk 1gal" vs "milk"
- **Categories**: Receipts use store categories; pantry scans might not have categories at all
- **Units**: Different measurement systems and granularity
- **Structure**: Entirely different columns

To combine them, we need **normalization** — transforming data into a standard form. The key output is a **join key**: a standardized identifier that lets us link records across tables even though the original data looks completely different.

## Instructions

1. **Analyze the actual data** currently in the receipt and pantry database tables:
   - Query both tables and pull all unique item names
   - Also query recipe ingredients (from WS02) — ultimately, inventory needs to match recipe ingredients
   - Print a detailed analysis:
     - All unique receipt item names (sorted)
     - All unique pantry item names (sorted)
     - All unique recipe ingredient names (sorted)
     - Obvious pairs that represent the same food (e.g., "Chicken Breast 2lb" / "chicken breast" / "chicken breast" in a recipe)
     - Patterns that need cleaning: brand names, size/weight suffixes, abbreviations, qualifiers (organic, fresh, frozen)
     - Items that appear in one source but not others
   - This analysis directly informs the cleaning functions below

2. **Create a normalization module** at `src/normalization/food_names.py`:

   **CRITICAL: All normalization rules must be loaded from `config/normalization_mappings.json`, NOT hardcoded in Python.** The Python code should be generic logic that reads the config; the config file contains the specific data. This means students can add new aliases, abbreviations, or qualifiers by editing a JSON file — no Python changes needed.

   - A function `load_normalization_config() -> dict` that reads and caches `config/normalization_mappings.json`. Include comments explaining why configuration lives outside the code.
   - A function `normalize_food_name(raw_name: str) -> str` that:
     - Loads the config (via `load_normalization_config()`)
     - Converts to lowercase, strips whitespace
     - Applies `abbreviations` from config to expand receipt shorthand (e.g., "chkn" → "chicken")
     - Removes words listed in `qualifiers_to_strip` from config (organic, natural, fresh, etc.)
     - Removes words listed in `packaging_terms_to_strip` from config (block, bag, bunch, etc.)
     - Applies regex patterns from `size_patterns_to_strip` in config to remove embedded sizes (e.g., "16oz", "2lb")
     - Checks `name_aliases` in config — if the cleaned name matches any alias, maps to the canonical name (e.g., "whole milk" → "milk")
     - Returns the final clean, standardized name
     - **If a `normalized_name` column was provided in the source data (from the AI extraction prompts), prefer that over running the full normalization pipeline** — add a parameter `pre_normalized: str | None = None` and use it when available
   - A function `extract_food_category(name: str, existing_category: str | None) -> str` that:
     - If `existing_category` is provided and is a valid category from the config, normalize and return it
     - Otherwise, look up the food name in `food_categories` from config to infer the category
     - Falls back to "other" if no match found
   - **Also** add any rules specifically needed for patterns observed in the actual data from step 1, by updating the config file (not by hardcoding)
   - Include detailed comments explaining:
     - How each step uses the config file (not hardcoded lists)
     - WHY each type of cleaning exists (e.g., "receipts include package sizes because that's how stores track SKUs")
     - How students can customize by editing `config/normalization_mappings.json`
   - Include a test/demo section at the bottom that runs through examples from the actual data and prints the transformations:
     ```
     "Organic Whole Milk 1gal" → "milk"
     "Baby Spinach 5oz" → "spinach"
     "BNLS SKNLS CHKN BRST" → "chicken breast"
     ```

   **Also load the normalization config into a SQL table** for demonstrating data-driven joins:
   - Create a model `NormalizationMapping` in `src/models/normalization.py` with fields: `id`, `canonical_name`, `alias`, `category`
   - Create a function `load_config_to_sql()` that reads `config/normalization_mappings.json` and populates the `NormalizationMapping` table from the `name_aliases` and `food_categories` sections
   - This demonstrates how configuration data can live in BOTH a file (for human editing) and a database table (for SQL joins and lookups)
   - Include educational comments about the "config file as source of truth, SQL table as queryable cache" pattern

3. **Create a join key module** at `src/normalization/join_keys.py`:
   - A function `create_join_key(normalized_name: str, category: str) -> str` that:
     - Takes the already-normalized name and category
     - Creates a standardized key for matching across data sources
     - Strategy: combine the normalized name with category as `{category}:{normalized_name}` (e.g., "dairy:milk", "protein:chicken breast")
     - This key is what allows a receipt item, a pantry item, and a recipe ingredient to be recognized as the same food
   - Educational documentation explaining:
     - What a join key is (a shared identifier that lets you connect records across tables)
     - Why we need to create one (the raw data has no shared ID)
     - Why including category in the key helps (prevents "turkey" the meat from matching "turkey" the country in a recipe name)
     - How join keys relate to database foreign keys
   - Include examples using actual data from step 1 showing items from different sources that produce the same join key

4. **Create the unified inventory model** in `src/models/inventory.py`:
   - `ActiveInventory` SQLModel with:
     - `id`: Integer primary key
     - `item_name`: String — the normalized food name
     - `original_name`: String — the name as it appeared in the source data (for debugging and display)
     - `category`: String — standardized food category
     - `join_key`: String — the standardized matching key
     - `quantity`: Float — amount available
     - `unit`: String — standardized unit of measurement
     - `source`: String — "receipt" or "pantry"
     - `source_id`: Integer — the ID from the original receipt or pantry record (foreign key concept)
     - `source_table`: String — "receipt" or "pantry" (to know which table `source_id` refers to)
     - `date_acquired`: Date — purchase date (receipt) or inventory date (pantry)
     - `expiration_date`: Optional Date — calculated: date_acquired + shelf_life_weeks
     - `is_expired`: Boolean — whether expiration_date < today
     - `created_at`: DateTime — when this unified record was built
   - Educational docstrings explaining:
     - This is a **derived table** — it's rebuilt from source data, not edited directly
     - Why we keep `original_name` alongside `item_name` (data lineage, debugging)
     - The concept of a unified/consolidated view across multiple data sources
     - How `expiration_date` is calculated and why it's an approximation

5. **Create the inventory builder** at `src/normalization/build_inventory.py`:
   - This is the main normalization pipeline. Create a function `build_active_inventory()` that:
     - **Drops and recreates the ActiveInventory table** (demonstrate the rebuild pattern — this is NOT an incremental update, it's a full rebuild from source data every time)
     - Reads ALL records from the Receipt table
     - Reads ALL records from the Pantry table
     - For each record from either source:
       - Applies `normalize_food_name()` to the item name
       - Applies `extract_food_category()` to determine/validate category
       - Creates a `join_key` using `create_join_key()`
       - Looks up shelf life from the FoodShelfLife reference table by normalized name
       - Calculates `expiration_date` as `date_acquired + timedelta(weeks=shelf_life_weeks)`
       - Determines `is_expired` based on today's date
       - Creates an ActiveInventory record
     - Inserts all records into the ActiveInventory table
     - Prints a **detailed normalization report**:
       - Total records processed from each source
       - A table showing: original name → normalized name → join key (for each unique item)
       - Items that couldn't be matched to a shelf life entry (with suggestions to add them)
       - Items marked as expired
       - Final active inventory count (non-expired items)
       - Count of unique join keys (how many distinct food items you have)
     - Handle edge cases: items with no shelf life match get a default (4 weeks), items with missing dates use today
   - Include extensive educational comments explaining:
     - WHY we rebuild rather than incrementally update (simplicity, correctness, avoiding stale data)
     - The transformation pipeline concept: raw → cleaned → normalized → enriched
     - How this pattern applies beyond food data (any ETL/data pipeline)
   - Make runnable directly

6. **Create a normalization quality report** at `src/analytics/normalization_report.py`:
   - This script validates and visualizes the normalization results:
     - **Before/After table**: Show original names vs normalized names for every item
     - **Join key analysis**: List all unique join keys, how many source records map to each
     - **Duplicate detection**: Items that might be duplicates despite different names (same join key from different sources)
     - **Gap analysis**: Items in inventory that don't appear in any recipe, and vice versa
     - **Category distribution**: Bar chart showing items per category
     - **Expiration timeline**: Chart showing when inventory items expire over the next 4 weeks
     - **Data quality score**: Simple percentage of items that: (a) matched a shelf life, (b) have a category, (c) have a valid expiration date
   - Include educational comments about:
     - Why data quality monitoring matters
     - How to interpret the normalization results
     - What to do when items don't normalize well (add rules to the normalization module)
   - Make runnable directly

7. **Run the inventory builder**:
   ```
   uv run python -m src.normalization.build_inventory
   ```

8. **Run the normalization report**:
   ```
   uv run python -m src.analytics.normalization_report
   ```

9. **Update documentation** at `docs/data_models/inventory.md`:
   - The ActiveInventory table structure
   - The normalization pipeline: how raw data becomes unified inventory
   - Join key design and examples
   - Expiration calculation logic
   - The rebuild pattern and when it runs

## Things to Try After This Step

- Look at the normalization report — are there items that normalized incorrectly? Open `src/normalization/food_names.py` and add rules to fix them, then re-run
- Add a new receipt or pantry CSV with items that have unusual names, re-run the builder, and check the report
- Ask Claude Code: "What items in my inventory are expiring this week?"
- Ask Claude Code: "Show me items that are in my pantry but don't match any receipt — these were not recently purchased"
- Try modifying `normalize_food_name()` to handle a specific pattern in your data
- Look at items that didn't match a shelf life — add them to the seed script and re-run
- Ask Claude Code: "Create a Jupyter notebook that shows the normalization transformations as a visual pipeline"
- Think about edge cases: what happens if the same item appears in both a receipt and pantry scan from the same day?
