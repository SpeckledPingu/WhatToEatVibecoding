"""
recipe_analysis.py — Analyze ingested recipe data using pandas.

HOW THIS SCRIPT WORKS
This script loads all recipes from the SQLite database into a pandas DataFrame
and produces a formatted report covering recipe counts, ingredient frequencies,
weather categories, and more.

WHAT IS PANDAS?
Pandas is Python's most popular library for tabular data. Think of a DataFrame
as a spreadsheet in code — rows and columns that you can filter, group, and
summarize with simple method calls.

RUN IT:
    uv run python -m src.analytics.recipe_analysis
"""

import json

import pandas as pd
from sqlmodel import Session, select

from src.database import get_engine
from src.models.recipe import Recipe


def load_recipes_to_dataframe() -> pd.DataFrame:
    """
    Load all recipes from the database into a pandas DataFrame.

    HOW SQL-TO-DATAFRAME WORKS
    1. We open a database session and run a SELECT query for all Recipe rows.
    2. SQLModel returns Python objects (one Recipe per row).
    3. We convert each object to a dictionary with model_dump().
    4. pd.DataFrame() turns a list of dictionaries into a table where:
       - Each dictionary becomes one row
       - Each key becomes a column
    """
    engine = get_engine()
    with Session(engine) as session:
        recipes = session.exec(select(Recipe)).all()

        if not recipes:
            print("No recipes found in the database. Run ingestion first:")
            print("  uv run python -m src.ingestion.recipes")
            return pd.DataFrame()

        # Convert SQLModel objects to dictionaries, then to a DataFrame
        # model_dump() is a Pydantic/SQLModel method that turns an object
        # into a plain dict of {field_name: value}
        data = [recipe.model_dump() for recipe in recipes]
        return pd.DataFrame(data)


def analyze_recipes():
    """
    Produce a formatted analysis report of all recipes in the database.
    """
    df = load_recipes_to_dataframe()

    if df.empty:
        return

    print("=" * 70)
    print("RECIPE ANALYSIS REPORT")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Total recipe count
    # ------------------------------------------------------------------
    # len(df) gives the number of rows — one row per recipe
    print(f"\nTotal recipes in database: {len(df)}")

    # ------------------------------------------------------------------
    # Count by source format
    # ------------------------------------------------------------------
    # value_counts() counts how many times each unique value appears in a column.
    # It returns a Series sorted by frequency (most common first).
    print(f"\nRecipes by source format:")
    format_counts = df["source_format"].value_counts()
    for fmt, count in format_counts.items():
        print(f"  {fmt}: {count}")

    # ------------------------------------------------------------------
    # Count by weather categories
    # ------------------------------------------------------------------
    # fillna() replaces NaN (missing values) with a placeholder string so
    # they show up in the counts instead of being silently dropped.
    print(f"\nRecipes by weather_temp:")
    temp_counts = df["weather_temp"].fillna("(not set)").value_counts()
    for temp, count in temp_counts.items():
        print(f"  {temp}: {count}")

    print(f"\nRecipes by weather_condition:")
    cond_counts = df["weather_condition"].fillna("(not set)").value_counts()
    for cond, count in cond_counts.items():
        print(f"  {cond}: {count}")

    # ------------------------------------------------------------------
    # Average number of ingredients per recipe
    # ------------------------------------------------------------------
    # We apply len() to each ingredients list to count how many ingredients
    # each recipe has, then take the mean across all recipes.
    df["ingredient_count"] = df["ingredients"].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )
    avg_ingredients = df["ingredient_count"].mean()
    print(f"\nAverage ingredients per recipe: {avg_ingredients:.1f}")
    print(f"  Min: {df['ingredient_count'].min()}")
    print(f"  Max: {df['ingredient_count'].max()}")

    # ------------------------------------------------------------------
    # Top 10 most common ingredients
    # ------------------------------------------------------------------
    # HOW explode() WORKS
    # Each recipe has a list of ingredient objects. explode() "un-nests" these
    # lists: if a recipe has 8 ingredients, explode creates 8 rows (one per
    # ingredient), each still linked to the same recipe data. This lets us
    # count individual ingredients across ALL recipes.
    #
    # Step by step:
    #   1. Extract the 'name' from each ingredient dict
    #   2. Explode the lists into individual rows
    #   3. Count occurrences with value_counts()
    all_ingredient_names = df["ingredients"].apply(
        lambda ings: [ing["name"] for ing in ings if isinstance(ing, dict)]
    )
    # explode() turns each list into separate rows
    exploded = all_ingredient_names.explode()
    # value_counts() counts how often each ingredient name appears
    top_ingredients = exploded.value_counts().head(10)

    print(f"\nTop 10 most common ingredients across all recipes:")
    for ingredient, count in top_ingredients.items():
        print(f"  {ingredient}: used in {count} recipe(s)")

    # ------------------------------------------------------------------
    # Recipes missing weather categorization
    # ------------------------------------------------------------------
    # isna() returns True for each row where the value is NaN/None.
    # The | operator combines two boolean conditions (logical OR).
    missing_weather = df[
        df["weather_temp"].isna() | df["weather_condition"].isna()
    ]
    print(f"\nRecipes missing weather categorization: {len(missing_weather)}")
    if not missing_weather.empty:
        for _, row in missing_weather.iterrows():
            temp = row["weather_temp"] or "(missing)"
            cond = row["weather_condition"] or "(missing)"
            print(f"  {row['name']} — temp: {temp}, condition: {cond}")

    # ------------------------------------------------------------------
    # All unique ingredient categories
    # ------------------------------------------------------------------
    # HOW groupby() COULD BE USED HERE
    # groupby() splits a DataFrame into groups based on a column's values,
    # then lets you apply an aggregation (count, sum, mean, etc.) to each group.
    # Here we just need unique categories, so we extract and flatten them.
    all_categories = df["ingredients"].apply(
        lambda ings: [
            ing.get("category", "unknown")
            for ing in ings
            if isinstance(ing, dict)
        ]
    )
    # Flatten all category lists into one Series, then get unique values
    unique_categories = sorted(all_categories.explode().dropna().unique())
    print(f"\nUnique ingredient categories found ({len(unique_categories)}):")
    for cat in unique_categories:
        print(f"  {cat}")

    # ------------------------------------------------------------------
    # Quick recipe listing
    # ------------------------------------------------------------------
    print(f"\nAll recipes:")
    for _, row in df.iterrows():
        tag_str = ", ".join(row["tags"]) if isinstance(row["tags"], list) else ""
        has_md = "with Markdown" if row.get("full_text_markdown") else "JSON only"
        print(f"  {row['name']} ({has_md}) [{tag_str}]")

    print(f"\n{'=' * 70}")
    print("Analysis complete.")


if __name__ == "__main__":
    analyze_recipes()
