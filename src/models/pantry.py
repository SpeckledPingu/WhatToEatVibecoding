"""
pantry.py — SQLModel definition for the Pantry (inventory) table.

WHAT IS A PANTRY RECORD?
A pantry record represents a food item observed during an inventory scan — one
row per item found in your kitchen. This is STATE data: it captures what you have
on hand RIGHT NOW (or at least, at the time of the inventory).

Compare this to the Receipt model (receipt.py), which represents TRANSACTION data:
"what did I buy and when?" A receipt says "I bought milk on March 17th." A pantry
record says "I have milk in the fridge, and it's about half full."

WHY THE DIFFERENCE MATTERS
When you combine these two data sources (WS04), you get a richer picture:
  - Receipts tell you WHEN things arrived and HOW MUCH they cost
  - Pantry scans tell you WHAT'S LEFT and its CONDITION

Together, they enable questions like: "I bought spinach a week ago — is it still
good?" (Receipt purchase_date + shelf life data = estimated expiration).

HOW DATA IS COLLECTED
Users photograph their pantry/fridge/freezer and use an AI extraction prompt
(prompts/pantry_extraction.md) to produce a CSV. The AI normalizes item names
at extraction time, so pantry data is typically much cleaner than receipt data.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class PantryItem(SQLModel, table=True):
    """
    A single food item from a pantry inventory scan.

    Each row represents one food item observed in the kitchen, including its
    quantity, storage location, and current condition. Unlike receipt data
    (which tracks purchases), pantry data tracks current inventory state.

    TABLE NAME NOTE
    SQLModel automatically names the table 'pantryitem' (lowercase class name).
    This is fine — table names are internal identifiers. The class name
    PantryItem is more descriptive in Python code.
    """

    # -----------------------------------------------------------------------
    # Primary key
    # -----------------------------------------------------------------------
    id: Optional[int] = Field(default=None, primary_key=True)
    """Auto-incrementing unique identifier for each pantry item."""

    # -----------------------------------------------------------------------
    # Item identification
    # -----------------------------------------------------------------------
    item_name: str = Field(index=True)
    """
    The food item name, e.g. 'all purpose flour', 'chocolate chips'.

    Unlike receipt item_name (which is messy receipt abbreviations), pantry
    item names are typically already normalized by the AI extraction prompt.
    This means pantry names are closer to "canonical" food names and easier
    to match against recipes and shelf life data.
    """

    # -----------------------------------------------------------------------
    # Quantity and measurement
    # -----------------------------------------------------------------------
    quantity: float = Field(default=1.0)
    """
    How much of this item is on hand.

    WHY float INSTEAD OF int?
    Pantry quantities are often fractional: "about 0.75 of a bag" or "0.5
    bottle remaining." Using float accommodates these partial amounts that
    are common in real-world inventory.
    """

    unit: str = Field(default="whole")
    """
    Unit of measurement: 'pounds', 'container', 'bag', 'bottle', 'box',
    'jar', 'whole', 'bunch', 'can', etc.

    WHY TRACK UNITS?
    The same food can be measured in different ways. You might have "5 pounds"
    of flour but "1 bag" of chocolate chips. Units help you understand the
    actual quantity and will be important for recipe matching (WS05) — a
    recipe needs "2 cups of flour", not "2 bags of flour."
    """

    # -----------------------------------------------------------------------
    # Storage and condition
    # -----------------------------------------------------------------------
    location: Optional[str] = Field(default=None)
    """
    Where this item is stored: 'pantry', 'fridge', 'freezer', or 'counter'.

    Location affects shelf life — the same food lasts different amounts of
    time depending on storage. This connects to the FoodShelfLife reference
    table (shelf_life.py) for expiration calculations.
    """

    condition: Optional[str] = Field(default=None)
    """
    Current state of the food: 'good', 'opened', 'frozen', 'wilting', 'expired'.

    This is a human assessment from the inventory scan. An opened container
    of oats is different from a sealed one — knowing the condition helps
    prioritize what to use first.
    """

    category: Optional[str] = Field(default=None)
    """
    Food category (e.g., 'protein', 'dairy', 'grain', 'spice').
    Matches the standard categories in config/normalization_mappings.json.
    """

    # -----------------------------------------------------------------------
    # Inventory date
    # -----------------------------------------------------------------------
    date_inventoried: date
    """
    When this inventory snapshot was taken.

    IMPORTANT FOR EXPIRATION TRACKING
    This date serves as the "clock start" for shelf life calculations:
      expiration_date = date_inventoried + shelf_life_weeks
    If the pantry was scanned on March 18th and milk lasts 1 week, the milk
    expires around March 25th. This is an approximation — the milk was likely
    purchased before the scan — but it's a useful starting point.
    """

    # -----------------------------------------------------------------------
    # Additional info
    # -----------------------------------------------------------------------
    notes: Optional[str] = Field(default=None)
    """
    Free-text notes from the inventory scan, e.g. 'about 0.75 full',
    'higher protein for yeast breads'. These provide context that doesn't
    fit neatly into structured fields.
    """

    # -----------------------------------------------------------------------
    # Data provenance
    # -----------------------------------------------------------------------
    source_file: str = Field(default="")
    """
    The CSV filename this row was loaded from, e.g. 'shelves_2026_03_18.csv'.
    Tracks data lineage for debugging and auditing.
    """

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """Timestamp of when this record was ingested into the database (UTC)."""
