"""
inventory.py — SQLModel definition for the ActiveInventory (unified view) table.

WHAT IS A UNIFIED INVENTORY?
Receipt data and pantry data describe the same thing — food you have — but they
come from different sources with different formats:
  - Receipts: "Greenwise Hmstyle Meatbal Ft" (messy, has prices, purchase dates)
  - Pantry:   "all purpose flour" (clean, has locations, conditions)

The ActiveInventory table COMBINES both into a single, standardized view. After
normalization, a receipt "Publix Unsltd Btr" and a pantry "butter" both become
rows in this table with item_name="butter" and join_key="dairy:butter".

THIS IS A DERIVED TABLE
Unlike receipts and pantry tables (which hold raw ingested data), ActiveInventory
is REBUILT from scratch every time the normalization pipeline runs. Think of it
like a spreadsheet formula — it always reflects the latest source data. You never
edit this table directly; you edit the source data or normalization rules, then
rebuild.

WHY REBUILD INSTEAD OF UPDATE?
  - Simplicity: no complex logic to detect what changed
  - Correctness: impossible for stale data to linger
  - Reproducibility: given the same inputs, you always get the same output
  - Debugging: if something looks wrong, re-run and check the normalization report
  The trade-off is speed — a full rebuild is slower than incremental updates. For
  a personal food inventory (hundreds of items), this is negligible.

DATA LINEAGE
Every row tracks where it came from (source, source_id, source_table, original_name).
This is essential for debugging: "This join key looks wrong → check original_name →
find the source record → update the normalization config."
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class ActiveInventory(SQLModel, table=True):
    """
    A unified inventory item combining receipt and pantry data.

    Each row represents one food item from either source, normalized and enriched
    with category, join key, and expiration information. Multiple source records
    can map to the same join key (e.g., receipt "butter" and pantry "butter"),
    which is how we detect overlapping inventory.
    """

    # -----------------------------------------------------------------------
    # Primary key
    # -----------------------------------------------------------------------
    id: Optional[int] = Field(default=None, primary_key=True)
    """Auto-incrementing unique identifier for each unified inventory record."""

    # -----------------------------------------------------------------------
    # Normalized item identification
    # -----------------------------------------------------------------------
    item_name: str = Field(index=True)
    """
    The NORMALIZED food name after cleaning. This is what the normalization
    pipeline produced — lowercase, no brand names, no sizes, aliases resolved.
    Example: "butter" (from receipt "Publix Unsltd Btr Ft").
    """

    original_name: str
    """
    The item name as it appeared in the SOURCE data, before any normalization.
    We keep this for:
      - Debugging: if normalization looks wrong, compare original to normalized
      - Display: users might want to see "Publix Unsltd Btr" not just "butter"
      - Data lineage: tracing the full transformation chain
    """

    category: str = Field(default="other")
    """Standardized food category (protein, dairy, grain, spice, etc.)."""

    join_key: str = Field(index=True)
    """
    The standardized matching key: "{category}:{item_name}".
    Example: "dairy:butter"

    WHAT IS A JOIN KEY?
    A join key is a shared identifier that lets you connect records across tables.
    A receipt "butter", a pantry "butter", and a recipe ingredient "butter" all
    produce the join key "dairy:butter" — which is how the system knows they're
    the same food even though they came from completely different data sources.
    """

    # -----------------------------------------------------------------------
    # Quantity and measurement
    # -----------------------------------------------------------------------
    quantity: float = Field(default=1.0)
    """How much of this item is available (from receipt quantity or pantry quantity)."""

    unit: str = Field(default="whole")
    """Unit of measurement (standardized where possible)."""

    # -----------------------------------------------------------------------
    # Source tracking (data lineage)
    # -----------------------------------------------------------------------
    source: str
    """Which data source this came from: 'receipt' or 'pantry'."""

    source_id: Optional[int] = Field(default=None)
    """
    The primary key ID from the original source table. Combined with source_table,
    this lets you trace back to the exact row in receipts or pantry that produced
    this unified record.

    WHY TRACK THIS?
    This is a simplified version of a FOREIGN KEY. In a more complex system, you'd
    have actual foreign key constraints. Here we store the ID and table name
    separately because the ID could refer to either the Receipt or PantryItem table.
    """

    source_table: str = Field(default="")
    """Which table source_id refers to: 'receipt' or 'pantryitem'."""

    # -----------------------------------------------------------------------
    # Dates and expiration
    # -----------------------------------------------------------------------
    date_acquired: date
    """
    When this food item entered the household:
      - For receipts: the purchase_date
      - For pantry: the date_inventoried (an approximation — the item may have
        been purchased earlier, but this is the best date we have)
    """

    expiration_date: Optional[date] = Field(default=None)
    """
    CALCULATED field: date_acquired + shelf_life_weeks.

    HOW EXPIRATION IS CALCULATED
    We look up the item's shelf life from the FoodShelfLife reference table
    (or use a category default if no specific entry exists). Then:
      expiration_date = date_acquired + timedelta(weeks=shelf_life_weeks)

    This is an APPROXIMATION — actual shelf life depends on storage conditions,
    packaging, handling, and many other factors. It's a useful guide, not a
    guarantee. When in doubt, trust your nose over this date.
    """

    is_expired: bool = Field(default=False)
    """
    Whether expiration_date has passed (expiration_date < today).
    Recalculated on every rebuild, so it's always current.
    """

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    """When this unified record was built (UTC). Changes on every rebuild."""
