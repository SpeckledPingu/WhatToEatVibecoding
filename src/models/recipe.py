"""
recipe.py — SQLModel definition for the Recipe table.

HOW SQLMODEL WORKS
SQLModel combines two powerful libraries:
  - SQLAlchemy (the most popular Python library for talking to databases)
  - Pydantic (a library for validating data and defining data shapes)

When you create a class that inherits from SQLModel with `table=True`, SQLModel
does two things at once:
  1. Creates a database table whose columns match the class's fields
  2. Creates a Python data validator that checks field types when you create objects

This means you get a single class that defines BOTH the database schema AND the
Python data structure — no need to keep two definitions in sync.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Column, Field, SQLModel, JSON


class Recipe(SQLModel, table=True):
    """
    A single recipe stored in the database.

    Each row represents one recipe that was ingested from a JSON file in
    `data/recipes/json/`. The structured data (ingredients, instructions) lives
    in JSON columns, while the optional full-text Markdown companion from
    `data/recipes/markdown/` is stored verbatim in `full_text_markdown`.

    WHY JSON FIELDS INSTEAD OF SEPARATE TABLES?
    Ingredients and instructions are tightly coupled to their recipe — you'd
    never look up an instruction without its recipe context. Storing them as
    JSON inside the recipe row keeps related data together, simplifies queries,
    and avoids the complexity of extra tables and foreign keys. The trade-off is
    that you can't easily query *across* ingredients with SQL alone (e.g., "find
    all recipes that use garlic"). For that, we'll build a separate matching
    table in a later workstream (WS05) that flattens ingredients out.
    """

    # -----------------------------------------------------------------------
    # Primary key
    # -----------------------------------------------------------------------
    id: Optional[int] = Field(default=None, primary_key=True)
    """
    WHAT IS A PRIMARY KEY?
    A primary key is a unique identifier for each row in a table — like a
    Social Security Number for data. No two rows can share the same primary key.

    WHY auto-increment?
    Setting `default=None` tells SQLite to automatically assign the next
    available integer (1, 2, 3, …) when a new row is inserted. This means you
    never have to worry about picking a unique ID yourself — the database
    handles it.
    """

    # -----------------------------------------------------------------------
    # Core recipe fields
    # -----------------------------------------------------------------------
    name: str = Field(index=True)
    """The recipe's display name, e.g. 'Apple Cake'. Indexed for fast lookups."""

    description: Optional[str] = Field(default=None)
    """A brief summary of the dish. Optional because some data files may omit it."""

    ingredients: list = Field(default=[], sa_column=Column(JSON))
    """
    A JSON list of ingredient objects. Each object has at minimum:
      - name (str): the ingredient name, e.g. "flour"
      - quantity (number): how much, e.g. 2.5
      - unit (str): measurement unit, e.g. "cups"
      - category (str): a standard food category from config/normalization_mappings.json
                         (protein, vegetable, fruit, dairy, grain, spice, condiment, etc.)

    Example:
        [
            {"name": "flour", "quantity": 2.5, "unit": "cups", "category": "grain"},
            {"name": "eggs", "quantity": 3, "unit": "whole", "category": "protein"}
        ]
    """

    instructions: list = Field(default=[], sa_column=Column(JSON))
    """
    A JSON list of preparation step strings, in order.

    Example:
        ["Preheat oven to 350°F.", "Mix dry ingredients.", "Add wet ingredients."]
    """

    # -----------------------------------------------------------------------
    # Timing and serving info
    # -----------------------------------------------------------------------
    prep_time_minutes: Optional[int] = Field(default=None)
    """How many minutes of active preparation (chopping, mixing, etc.)."""

    cook_time_minutes: Optional[int] = Field(default=None)
    """How many minutes the recipe spends cooking (in the oven, on the stove, etc.)."""

    servings: Optional[int] = Field(default=None)
    """How many portions this recipe makes."""

    # -----------------------------------------------------------------------
    # Weather-based recommendation tags
    # -----------------------------------------------------------------------
    weather_temp: Optional[str] = Field(default=None)
    """'warm' or 'cold' — used by WS11 to recommend recipes based on temperature."""

    weather_condition: Optional[str] = Field(default=None)
    """'rainy', 'sunny', or 'cloudy' — used by WS11 for weather-condition matching."""

    # -----------------------------------------------------------------------
    # Tags and metadata
    # -----------------------------------------------------------------------
    tags: Optional[list] = Field(default=None, sa_column=Column(JSON))
    """
    A JSON list of tag strings for filtering and search, e.g.
    ["breakfast", "vegetarian", "comfort food"].
    """

    source: Optional[str] = Field(default=None)
    """URL or description of where the recipe came from (e.g. a website URL)."""

    source_format: str = Field(default="json")
    """
    WHY TRACK SOURCE FORMAT?
    Data lineage (also called 'data provenance') means knowing where your data
    came from and how it was processed. If you ever find a bug in a recipe
    record, source_format tells you whether the structured data was parsed from
    a JSON file so you can trace back to the original file.
    Always 'json' since JSON files are the primary structured source.
    """

    source_file: str = Field(default="")
    """
    The original filename (e.g. 'apple_cake.json') so you can trace any
    database record back to the exact file it was ingested from.
    """

    full_text_markdown: Optional[str] = Field(default=None)
    """
    The full human-readable recipe text loaded from a companion .md file in
    `data/recipes/markdown/`. Stored as-is — not parsed for structure.

    WHY STORE FULL TEXT SEPARATELY?
    The JSON file gives us clean, structured data (ingredients list, step-by-step
    instructions) that's easy to query and compare. But the original recipe page
    often has useful context: tips, variations, stories, photos. Storing the full
    Markdown preserves all of that without polluting the structured fields.
    """

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """Timestamp of when this record was first ingested into the database."""
