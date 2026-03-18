# Workstream 02: Recipe Data Ingestion

Ingest recipe data from JSON and Markdown files into the SQLite database. This workstream reads the actual data files provided to determine the schema, creates the database models, and builds ingestion scripts.

## Context

Recipes have two components:
- **JSON files** in `data/recipes/json/` — structured data, typically extracted using the prompt in `prompts/recipe_extraction.md` or typed by hand. This is the **primary data source** that gets parsed into database fields.
- **Markdown files** in `data/recipes/markdown/` — the full human-readable text of the recipe (narrative descriptions, tips, detailed instructions). This is an **optional companion** that gets stored as-is in a `full_text_markdown` field on the recipe record.

JSON and Markdown files are **linked by filename**: `chicken_soup.json` pairs with `chicken_soup.md`. If the AI extraction doesn't capture the full recipe text, students can use a browser markdown extension (like MarkDownload) to save the recipe page as markdown, or paste it manually into the Streamlit app.

## Instructions

1. **Read and analyze all recipe files** in `data/recipes/json/` and check for companions in `data/recipes/markdown/`:
   - For each JSON file: read the contents, examine field names, data types, nesting structure (especially the ingredients array), and note any inconsistencies between files
   - Check which JSON files have a matching `.md` file in `data/recipes/markdown/` (same base name)
   - Also read `config/normalization_mappings.json` to understand the standard food categories that ingredients should use
   - Print a detailed analysis: how many JSON files found, how many have matching Markdown companions, what fields exist, what fields vary between files, any unexpected structures
   - **If no recipe JSON files exist**: stop and inform me that recipe data files are needed before this workstream can proceed. Show the expected formats from `docs/guides/data_formats.md` and the extraction prompt from `prompts/recipe_extraction.md`. Create 2-3 example recipe files (both JSON and matching Markdown) in the respective data directories so I can see the format and modify them with real recipes.

2. **Design the Recipe SQLModel** in `src/models/recipe.py` based on the actual data found:
   - Examine the fields present in the data files and include all of them
   - The table **MUST** include these fields (create them even if not present in the source data, using sensible defaults or None):
     - `id`: Integer primary key, auto-incrementing
     - `name`: String, required — the recipe name
     - `description`: Optional string — brief description of the dish
     - `ingredients`: **JSON field** — a list of ingredient objects. Each ingredient object should have at minimum: `name` (str), `quantity` (number), `unit` (str), and `category` (str — use the standard categories defined in `config/normalization_mappings.json` under `food_categories`)
     - `instructions`: **JSON field** — an ordered list of preparation step strings
     - `prep_time_minutes`: Optional integer
     - `cook_time_minutes`: Optional integer
     - `servings`: Optional integer
     - `weather_temp`: Optional string — "warm" or "cold", for weather-based recommendations
     - `weather_condition`: Optional string — "rainy", "sunny", or "cloudy"
     - `tags`: Optional JSON field — list of tag strings
     - `source`: Optional string — where the recipe came from
     - `source_format`: String — "json" (always "json" since JSON is the primary structured source)
     - `source_file`: String — the original filename for traceability
     - `full_text_markdown`: Optional text — the full human-readable recipe text from a matching `.md` file or pasted by the user. Stored as-is, not parsed for structure.
     - `created_at`: DateTime, defaults to now — when the record was ingested
   - Add educational docstrings to the class and each field explaining:
     - Why JSON fields are used for nested data (ingredients, instructions) instead of separate tables
     - What a primary key is and why auto-increment is convenient
     - Why we track `source_format` and `source_file` (data lineage/provenance)
   - Include any additional fields discovered in the actual data files

3. **Create the ingestion script** at `src/ingestion/recipes.py`:
   - A function `parse_json_recipe(file_path: Path) -> dict` that reads a JSON recipe file and returns a normalized dictionary. Include comments explaining JSON parsing.
   - A function `load_full_text_markdown(json_file_path: Path) -> str | None` that checks if a matching `.md` file exists in `data/recipes/markdown/` (same base name as the JSON file, e.g., `chicken_soup.json` → `chicken_soup.md`). If found, reads and returns the full markdown content as a string. If not found, returns None. Include comments explaining the file-pairing strategy and why full text is stored separately from structured data.
   - A function `validate_recipe(data: dict) -> tuple[bool, list[str]]` that checks for required fields and returns (is_valid, list_of_issues). Validate ingredient categories against the standard categories in `config/normalization_mappings.json`. Include comments about why data validation matters.
   - A main function `ingest_recipes()` that:
     - Scans `data/recipes/json/` for JSON files (these are the primary data source)
     - Parses each JSON file for structured recipe data
     - For each recipe, checks for a matching `.md` file in `data/recipes/markdown/` and loads it as the `full_text_markdown` field
     - Validates each parsed recipe
     - Checks for duplicate recipes by name — if a duplicate is found, update the existing record
     - Inserts new records or updates existing ones in the database
     - Prints a comprehensive summary:
       - Files found per directory
       - Successfully ingested (new vs updated)
       - Validation warnings
       - Any files that failed to parse (with the error)
     - Creates the database tables if they don't exist yet
   - Handle edge cases gracefully: missing fields get None, unexpected formats produce informative error messages rather than crashes
   - Make this script runnable directly: `if __name__ == "__main__": ingest_recipes()`

4. **Create a recipe analysis script** at `src/analytics/recipe_analysis.py`:
   - Load all recipes from the database into a pandas DataFrame
   - Print a formatted report with:
     - Total number of recipes ingested
     - Count by source format (JSON vs Markdown)
     - Count by weather_temp and weather_condition categories
     - Average number of ingredients per recipe
     - Top 10 most common ingredients across all recipes (extracted from the JSON field)
     - Recipes missing weather categorization (candidates for you to fill in)
     - List of all unique ingredient categories found
   - Include educational comments explaining each pandas operation used:
     - How to load SQL data into a DataFrame
     - How to work with JSON fields in pandas
     - How `value_counts()`, `groupby()`, and `explode()` work
   - Make this script runnable directly

5. **Run the ingestion** to load all current recipe files into the database:
   ```
   uv run python -m src.ingestion.recipes
   ```

6. **Run the analysis script** to verify the data and show what's in the database:
   ```
   uv run python -m src.analytics.recipe_analysis
   ```

7. **Create data model documentation** at `docs/data_models/recipes.md`:
   - Table name and purpose
   - All fields with their types, constraints, and descriptions
   - The JSON structure for the `ingredients` field with an example
   - The JSON structure for the `instructions` field with an example
   - 1-2 example records
   - Design decision explanations: why JSON fields vs separate tables, why track source info, etc.

## Things to Try After This Step

- Query your recipes directly: `uv run python -c "from sqlmodel import Session, select; from src.models.recipe import Recipe; from src.database import get_engine; session = Session(get_engine()); recipes = session.exec(select(Recipe)).all(); [print(f'{r.name} ({r.source_format})') for r in recipes]"`
- Add a new recipe JSON file to `data/recipes/json/` and re-run this workstream — watch it get ingested while skipping/updating existing ones
- Try writing the same recipe in both JSON and Markdown format to see how both parsers produce the same database record
- Look at the `ingredients` JSON field in the database — this is how nested data coexists with relational structure
- Modify the analysis script to find which recipes share the most ingredients
- Ask Claude Code: "Create a Jupyter notebook that visualizes ingredient frequency as a bar chart"
- Try intentionally breaking a JSON file (remove a comma) and re-run ingestion — observe the error handling
