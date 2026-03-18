"""
recipes.py — Ingest recipe data from JSON and Markdown files into the database.

HOW THIS SCRIPT WORKS
1. Scans `data/recipes/json/` for .json files (the primary structured data source)
2. For each JSON file, checks if a matching .md file exists in `data/recipes/markdown/`
3. Parses, validates, and loads each recipe into the SQLite database
4. If a recipe with the same name already exists, updates it instead of creating a duplicate
5. Prints a summary of what happened

RUN IT:
    uv run python -m src.ingestion.recipes
"""

import json
from pathlib import Path

from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.recipe import Recipe

# ---------------------------------------------------------------------------
# File paths — relative to the project root
# ---------------------------------------------------------------------------
# Path(__file__) is *this* file: src/ingestion/recipes.py
# .parent.parent.parent goes up to the project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
JSON_DIR = PROJECT_ROOT / "data" / "recipes" / "json"
MARKDOWN_DIR = PROJECT_ROOT / "data" / "recipes" / "markdown"
CONFIG_PATH = PROJECT_ROOT / "config" / "normalization_mappings.json"


def load_config() -> dict:
    """
    Load the normalization configuration file.

    This gives us the list of valid food categories so we can warn when a
    recipe's ingredient uses a category we don't recognize.
    """
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def get_valid_categories(config: dict) -> set[str]:
    """
    Extract the set of valid food category names from the config.

    HOW THIS WORKS
    The config's 'food_categories' key maps category names (like "protein",
    "vegetable") to lists of example foods. We just need the keys — those
    are the valid category names that ingredients should use.
    """
    categories = config.get("food_categories", {})
    # Filter out the _description key that's used for documentation
    return {key for key in categories if not key.startswith("_")}


def parse_json_recipe(file_path: Path) -> dict:
    """
    Read a single JSON recipe file and return its contents as a Python dictionary.

    HOW JSON PARSING WORKS
    JSON (JavaScript Object Notation) is a text format for structured data.
    Python's built-in `json` module converts JSON into native Python types:
      - JSON objects { } become Python dicts
      - JSON arrays [ ] become Python lists
      - JSON strings become Python strings
      - JSON numbers become Python ints or floats

    Parameters:
        file_path: Path to the .json file to read

    Returns:
        A dictionary with the recipe data, plus a 'source_file' key
        tracking which file this came from.

    Raises:
        json.JSONDecodeError: If the file contains invalid JSON
        FileNotFoundError: If the file doesn't exist
    """
    with open(file_path, "r") as f:
        data = json.load(f)

    # Add provenance tracking — which file did this data come from?
    data["source_file"] = file_path.name
    data["source_format"] = "json"

    return data


def load_full_text_markdown(json_file_path: Path) -> str | None:
    """
    Check for a companion Markdown file and return its contents if found.

    FILE-PAIRING STRATEGY
    JSON and Markdown files are linked by filename:
      - data/recipes/json/chicken_soup.json
      - data/recipes/markdown/chicken_soup.md

    The JSON file provides clean, structured data for the database. The
    Markdown file preserves the full human-readable recipe text (descriptions,
    tips, photos, stories) that doesn't fit neatly into structured fields.

    WHY STORE FULL TEXT SEPARATELY?
    Structured data is great for searching and comparing. But recipes often have
    rich narrative context that would be lost if we only kept the parsed fields.
    Storing the Markdown as-is gives us the best of both worlds.

    Parameters:
        json_file_path: Path to the JSON file (we derive the .md path from it)

    Returns:
        The full Markdown text as a string, or None if no companion file exists.
    """
    # Replace the .json extension with .md and look in the markdown directory
    md_filename = json_file_path.stem + ".md"
    md_path = MARKDOWN_DIR / md_filename

    if md_path.exists():
        with open(md_path, "r") as f:
            return f.read()

    return None


def validate_recipe(data: dict, valid_categories: set[str]) -> tuple[bool, list[str]]:
    """
    Check a parsed recipe dictionary for required fields and data quality.

    WHY VALIDATE DATA?
    "Garbage in, garbage out" — if we load bad data into the database, every
    query and analysis built on that data will be wrong. Validation catches
    problems early, when they're cheap to fix. It's much easier to fix a
    missing field in a JSON file than to debug why a recommendation algorithm
    is giving weird results three workstreams later.

    Parameters:
        data: The parsed recipe dictionary
        valid_categories: Set of allowed ingredient category names from config

    Returns:
        A tuple of (is_valid, issues):
          - is_valid: True if the recipe has all required fields
          - issues: A list of warning/error strings describing any problems found
    """
    issues = []

    # --- Required field checks ---
    # A recipe must have a name — everything else is optional but nice to have
    if not data.get("name"):
        issues.append("ERROR: Missing required field 'name'")

    # --- Recommended field checks (warnings, not errors) ---
    if not data.get("ingredients"):
        issues.append("WARNING: No ingredients listed")
    if not data.get("instructions"):
        issues.append("WARNING: No instructions listed")
    if not data.get("description"):
        issues.append("WARNING: No description provided")

    # --- Weather tag checks ---
    weather_temp = data.get("weather_temp")
    if weather_temp and weather_temp not in ("warm", "cold"):
        issues.append(f"WARNING: weather_temp '{weather_temp}' not in (warm, cold)")

    weather_condition = data.get("weather_condition")
    if weather_condition and weather_condition not in ("rainy", "sunny", "cloudy"):
        issues.append(
            f"WARNING: weather_condition '{weather_condition}' not in (rainy, sunny, cloudy)"
        )

    # --- Ingredient validation ---
    ingredients = data.get("ingredients", [])
    for i, ing in enumerate(ingredients):
        # Each ingredient should be a dict with name, quantity, unit, category
        if not isinstance(ing, dict):
            issues.append(f"WARNING: Ingredient #{i+1} is not an object: {ing}")
            continue

        if not ing.get("name"):
            issues.append(f"WARNING: Ingredient #{i+1} missing 'name'")

        category = ing.get("category", "")
        if category and category not in valid_categories:
            issues.append(
                f"WARNING: Ingredient '{ing.get('name', '?')}' has unknown "
                f"category '{category}' (valid: {sorted(valid_categories)})"
            )

    # The recipe is valid if there are no ERROR-level issues
    is_valid = not any(issue.startswith("ERROR") for issue in issues)
    return is_valid, issues


def ingest_recipes():
    """
    Main ingestion function — scan, parse, validate, and load all recipe files.

    This function is designed to be re-run safely whenever new recipe files are
    added. It uses an "upsert" strategy: if a recipe with the same name already
    exists, it updates that record. Otherwise, it creates a new one.
    """
    print("=" * 70)
    print("RECIPE INGESTION")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Load configuration for validation
    # ------------------------------------------------------------------
    config = load_config()
    valid_categories = get_valid_categories(config)
    print(f"\nLoaded {len(valid_categories)} valid ingredient categories from config:")
    print(f"  {sorted(valid_categories)}")

    # ------------------------------------------------------------------
    # Step 2: Discover files
    # ------------------------------------------------------------------
    if not JSON_DIR.exists():
        print(f"\nERROR: JSON directory not found: {JSON_DIR}")
        print("Please add recipe JSON files to data/recipes/json/ before running.")
        return

    json_files = sorted(JSON_DIR.glob("*.json"))
    md_files = sorted(MARKDOWN_DIR.glob("*.md")) if MARKDOWN_DIR.exists() else []

    # Build a set of markdown base names for quick lookup
    md_basenames = {f.stem for f in md_files}

    print(f"\nFiles discovered:")
    print(f"  JSON files:     {len(json_files)} in {JSON_DIR}")
    print(f"  Markdown files: {len(md_files)} in {MARKDOWN_DIR}")

    # Report which JSON files have/lack a Markdown companion
    matched = [f for f in json_files if f.stem in md_basenames]
    unmatched = [f for f in json_files if f.stem not in md_basenames]
    print(f"  JSON with Markdown companion: {len(matched)}")
    if unmatched:
        print(f"  JSON without Markdown companion: {len(unmatched)}")
        for f in unmatched:
            print(f"    - {f.name}")

    if not json_files:
        print("\nNo JSON recipe files found. Nothing to ingest.")
        return

    # ------------------------------------------------------------------
    # Step 3: Set up the database
    # ------------------------------------------------------------------
    engine = get_engine()
    create_db_and_tables(engine)

    # ------------------------------------------------------------------
    # Step 4: Parse, validate, and load each recipe
    # ------------------------------------------------------------------
    stats = {"new": 0, "updated": 0, "failed": 0, "warnings": 0}
    all_issues: list[tuple[str, list[str]]] = []

    with Session(engine) as session:
        for json_file in json_files:
            print(f"\n--- Processing: {json_file.name} ---")

            # Parse the JSON file
            try:
                data = parse_json_recipe(json_file)
            except json.JSONDecodeError as e:
                print(f"  FAILED: Invalid JSON — {e}")
                stats["failed"] += 1
                continue
            except Exception as e:
                print(f"  FAILED: {type(e).__name__} — {e}")
                stats["failed"] += 1
                continue

            # Load companion Markdown if it exists
            markdown_text = load_full_text_markdown(json_file)
            if markdown_text:
                print(f"  Found Markdown companion: {json_file.stem}.md")
                data["full_text_markdown"] = markdown_text
            else:
                print(f"  No Markdown companion found for {json_file.stem}")
                data["full_text_markdown"] = None

            # Validate
            is_valid, issues = validate_recipe(data, valid_categories)
            if issues:
                stats["warnings"] += len(issues)
                all_issues.append((json_file.name, issues))
                for issue in issues:
                    print(f"  {issue}")

            if not is_valid:
                print(f"  SKIPPED: Recipe failed validation (has ERROR-level issues)")
                stats["failed"] += 1
                continue

            # Check for existing recipe with the same name (upsert logic)
            existing = session.exec(
                select(Recipe).where(Recipe.name == data.get("name"))
            ).first()

            if existing:
                # Update the existing record with new data
                existing.description = data.get("description")
                existing.ingredients = data.get("ingredients", [])
                existing.instructions = data.get("instructions", [])
                existing.prep_time_minutes = data.get("prep_time_minutes")
                existing.cook_time_minutes = data.get("cook_time_minutes")
                existing.servings = data.get("servings")
                existing.weather_temp = data.get("weather_temp")
                existing.weather_condition = data.get("weather_condition")
                existing.tags = data.get("tags")
                existing.source = data.get("source")
                existing.source_format = data.get("source_format", "json")
                existing.source_file = data.get("source_file", "")
                existing.full_text_markdown = data.get("full_text_markdown")
                session.add(existing)
                print(f"  UPDATED: '{existing.name}' (id={existing.id})")
                stats["updated"] += 1
            else:
                # Create a new recipe record
                recipe = Recipe(
                    name=data.get("name", ""),
                    description=data.get("description"),
                    ingredients=data.get("ingredients", []),
                    instructions=data.get("instructions", []),
                    prep_time_minutes=data.get("prep_time_minutes"),
                    cook_time_minutes=data.get("cook_time_minutes"),
                    servings=data.get("servings"),
                    weather_temp=data.get("weather_temp"),
                    weather_condition=data.get("weather_condition"),
                    tags=data.get("tags"),
                    source=data.get("source"),
                    source_format=data.get("source_format", "json"),
                    source_file=data.get("source_file", ""),
                    full_text_markdown=data.get("full_text_markdown"),
                )
                session.add(recipe)
                print(f"  NEW: '{recipe.name}'")
                stats["new"] += 1

        # Commit all changes in a single transaction
        session.commit()

    # ------------------------------------------------------------------
    # Step 5: Print summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"  JSON files scanned:  {len(json_files)}")
    print(f"  New recipes added:   {stats['new']}")
    print(f"  Existing updated:    {stats['updated']}")
    print(f"  Failed to ingest:    {stats['failed']}")
    print(f"  Validation warnings: {stats['warnings']}")

    if all_issues:
        print(f"\nValidation details:")
        for filename, issues in all_issues:
            print(f"  {filename}:")
            for issue in issues:
                print(f"    {issue}")

    print(f"\nDatabase: {engine.url}")
    print("Done!")


if __name__ == "__main__":
    ingest_recipes()
