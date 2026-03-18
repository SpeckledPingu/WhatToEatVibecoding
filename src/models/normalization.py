"""
normalization.py — SQLModel definition for the NormalizationMapping table.

WHY STORE CONFIG IN A DATABASE TABLE?
The normalization rules live in config/normalization_mappings.json as their
"source of truth" — students edit that file to add new food aliases, categories,
and cleaning rules. But we ALSO load those rules into this database table because:

  1. **SQL joins**: With the rules in a table, we can JOIN inventory items against
     aliases using SQL instead of Python loops. SQL engines are optimized for this.
  2. **Queryability**: We can easily ask questions like "how many aliases does each
     food have?" or "which canonical names have no aliases?" using simple SQL.
  3. **Data-driven pattern**: This demonstrates the common pattern of storing
     configuration in a database for runtime use while keeping a human-editable
     file as the source of truth.

THE "CONFIG FILE → SQL TABLE" PATTERN
  - config/normalization_mappings.json = source of truth (human-editable)
  - NormalizationMapping table = queryable cache (machine-optimized)
  - The load_config_to_sql() function syncs from file to table
  - When you add a new alias in the JSON file, re-run the loader to update the table
"""

from typing import Optional

from sqlmodel import Field, SQLModel


class NormalizationMapping(SQLModel, table=True):
    """
    A single normalization rule: maps an alias to its canonical food name.

    For example, if config says:
        "chicken breast": ["boneless chicken", "chkn breast", "bnls chkn"]

    This creates 3 rows:
        (canonical_name="chicken breast", alias="boneless chicken", category="protein")
        (canonical_name="chicken breast", alias="chkn breast",      category="protein")
        (canonical_name="chicken breast", alias="bnls chkn",        category="protein")

    Plus one "self-referencing" row for the canonical name itself:
        (canonical_name="chicken breast", alias="chicken breast",   category="protein")

    WHY A SELF-REFERENCING ROW?
    If someone searches for "chicken breast" (already canonical), we still want a
    match in the table. Including the canonical name as its own alias means every
    valid food name appears in the alias column — canonical or not.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    """Auto-incrementing unique identifier."""

    canonical_name: str = Field(index=True)
    """
    The standardized food name that all aliases map TO. This is the name used
    in join keys, shelf life lookups, and recipe matching. Example: "chicken breast".
    """

    alias: str = Field(index=True)
    """
    One known variation of the canonical name. This could be the canonical name
    itself, a spelling variation, an abbreviation, or a brand-style name.
    Example: "bnls sknls chkn" → canonical "chicken breast".
    """

    category: str = Field(default="other")
    """
    The food category for this canonical name (protein, dairy, grain, etc.).
    Pulled from the food_categories section of the config file.
    """
