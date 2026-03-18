"""
shelf_life.py — SQLModel definition for the FoodShelfLife reference table.

WHAT IS A REFERENCE TABLE?
A reference table (also called a "lookup table") stores stable, reusable data
that other tables reference. Unlike receipt or pantry tables — which grow with
each new data file — the shelf life table is relatively static. It holds
"facts" about food: how long does chicken last in the fridge? How long are
dried beans good in the pantry?

Think of it like a dictionary or encyclopedia that other parts of the system
consult. When the inventory system needs to calculate an expiration date, it
looks up the food item in this table to find its shelf life.

WHY A DATABASE TABLE INSTEAD OF JUST CONFIG?
The shelf life data originates in config/normalization_mappings.json (so students
can edit it without touching code), but we ALSO load it into a database table.
This demonstrates two important patterns:
  1. Configuration-as-data: the same data serves both config and database roles
  2. SQL joins: we can JOIN the shelf life table against pantry items using SQL,
     which is faster and more flexible than doing lookups in Python code

HOW EXPIRATION IS CALCULATED
  expiration_date = date_inventoried + (shelf_life_weeks * 7 days)
  is_expired = expiration_date < today

A food item is "active" (still good) when its expiration date is in the future.
"""

from typing import Optional

from sqlmodel import Field, SQLModel


class FoodShelfLife(SQLModel, table=True):
    """
    How long a specific food item stays fresh, by storage method.

    Each row maps a food name to its expected shelf life in weeks for a
    given storage type (fridge, freezer, or pantry). This table is seeded
    from config/normalization_mappings.json by scripts/seed_shelf_life.py
    and can be extended as students discover new foods in their data.

    USAGE IN EXPIRATION TRACKING
    To check if a pantry item is still good:
      1. Look up the item's food_name in this table
      2. Get shelf_life_weeks for the matching storage_type
      3. Calculate: expiration = date_inventoried + timedelta(weeks=shelf_life_weeks)
      4. Compare: if expiration > today, the item is still active
    """

    # -----------------------------------------------------------------------
    # Primary key
    # -----------------------------------------------------------------------
    id: Optional[int] = Field(default=None, primary_key=True)
    """Auto-incrementing unique identifier."""

    # -----------------------------------------------------------------------
    # Food identification
    # -----------------------------------------------------------------------
    food_name: str = Field(index=True)
    """
    The canonical (normalized, lowercase) food name, e.g. 'chicken breast',
    'olive oil', 'bread'. This should match the normalized names used in
    receipt and pantry tables so that joins work correctly.
    """

    category: str = Field(default="other")
    """
    Food category matching our standard categories from config:
    protein, vegetable, fruit, dairy, grain, spice, condiment, beverage,
    snack, other.
    """

    # -----------------------------------------------------------------------
    # Shelf life data
    # -----------------------------------------------------------------------
    shelf_life_weeks: int
    """
    How many weeks this food typically stays good under the specified
    storage conditions. For example:
      - Fresh chicken breast in the fridge: ~1 week
      - Dried pasta in the pantry: ~104 weeks (2 years)
      - Honey in the pantry: ~520 weeks (10 years!)

    These are conservative estimates. Actual shelf life depends on many
    factors (packaging, temperature, handling). Students are encouraged to
    adjust these values based on their own experience.
    """

    storage_type: str = Field(default="pantry")
    """
    Where this food should be stored: 'pantry', 'fridge', 'freezer', or 'counter'.

    The same food has very different shelf lives depending on storage:
      - Bread on the counter: ~1 week
      - Bread in the freezer: ~12 weeks
    """

    notes: Optional[str] = Field(default=None)
    """Optional storage tips or notes, e.g. 'keep sealed', 'store in cool dry place'."""
