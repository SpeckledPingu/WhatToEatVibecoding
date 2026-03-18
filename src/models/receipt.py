"""
receipt.py — SQLModel definition for the Receipt table.

WHAT IS A RECEIPT RECORD?
A receipt record represents a single line item from a store receipt — one row per
item purchased. This is TRANSACTION data: it records an event that happened at a
specific time ("I bought 2 avocados at Publix on March 17th for $6.00").

Compare this to the Pantry model (pantry.py), which represents STATE data: "what
do I currently have on hand?" These are fundamentally different data types, which
is why they live in separate tables with different schemas.

WHY SEPARATE TABLES?
In real-world data work, you almost never get two data sources that line up
perfectly. Receipt data has prices and store names. Pantry data has locations and
conditions. Forcing them into one table would mean lots of empty columns and
confusion about what each row means. Better to keep them separate and build
a unified view later (WS04) through normalization and joins.

DATA PROVENANCE
Every row tracks its `source_file` — the CSV filename it was loaded from. This
is a data engineering best practice called "data lineage" or "data provenance."
When something looks wrong in the database, you can trace it back to the exact
file (and row) it came from. This is invaluable for debugging and auditing.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Receipt(SQLModel, table=True):
    """
    A single line item from a store receipt.

    Each row corresponds to one product purchased during a shopping trip.
    The raw receipt text is preserved in `item_name`, while a pre-cleaned
    version may exist in `normalized_name` (produced by the AI extraction
    prompt in prompts/receipt_extraction.md).

    HOW THIS TABLE GETS POPULATED
    The ingestion script (src/ingestion/receipts.py) reads CSV files from
    data/receipts/, converts each row into a Receipt object, and inserts it
    into this table. The script can be re-run safely — it skips duplicates.
    """

    # -----------------------------------------------------------------------
    # Primary key
    # -----------------------------------------------------------------------
    id: Optional[int] = Field(default=None, primary_key=True)
    """Auto-incrementing unique identifier for each receipt line item."""

    # -----------------------------------------------------------------------
    # Item identification
    # -----------------------------------------------------------------------
    item_name: str = Field(index=True)
    """
    The item description exactly as printed on the receipt, e.g.
    'Greenwise Hmstyle Meatbal Ft'. This is the RAW data — often abbreviated,
    includes brand names, and hard to match against other data sources.
    We keep it for reference even though we'll primarily use normalized_name.
    """

    normalized_name: Optional[str] = Field(default=None, index=True)
    """
    A pre-cleaned version of the item name, e.g. 'meatball'.

    WHY TWO NAME FIELDS?
    Receipt item names are messy abbreviations from the store's POS system.
    The AI extraction prompt (prompts/receipt_extraction.md) asks the LLM to
    also produce a simple, normalized name at extraction time. If this column
    exists in the CSV, the normalization step in WS04 can use it as a head
    start instead of trying to decode 'Greenwise Hmstyle Meatbal Ft' from
    scratch. This is an example of "cleaning data at the source" — the closer
    to collection you clean, the better your downstream data quality.
    """

    # -----------------------------------------------------------------------
    # Purchase details
    # -----------------------------------------------------------------------
    quantity: int = Field(default=1)
    """How many units were purchased. Defaults to 1 for single items."""

    unit_price: Optional[float] = Field(default=None)
    """
    Price per individual unit, if available. Many receipts only show the
    total price for the line, so this is often null.
    """

    total_price: Optional[float] = Field(default=None)
    """
    Total price for this line item (quantity * unit_price, or the receipt total).
    This is the most reliably populated price field on receipts.
    """

    category: Optional[str] = Field(default=None)
    """
    Food category assigned during extraction (e.g., 'protein', 'dairy',
    'vegetable'). These categories align with the standard categories defined
    in config/normalization_mappings.json.
    """

    # -----------------------------------------------------------------------
    # Store and date
    # -----------------------------------------------------------------------
    store_name: str = Field(default="")
    """Which store this was purchased from, e.g. 'Publix', 'Kroger'."""

    purchase_date: date
    """
    The date the purchase was made (from the receipt header).

    WHY date INSTEAD OF datetime?
    Receipts record the day of purchase but rarely the exact time. Using
    Python's `date` type instead of `datetime` signals this clearly — the
    column holds a calendar date, not a timestamp.
    """

    # -----------------------------------------------------------------------
    # Data provenance
    # -----------------------------------------------------------------------
    source_file: str = Field(default="")
    """
    The CSV filename this row was loaded from, e.g. 'publix_2026_03_17.csv'.

    WHY TRACK SOURCE FILE?
    Data provenance — knowing where each record came from — is essential for
    debugging. If you find a suspicious price in the database, source_file
    lets you go back to the original CSV and check whether the issue was in
    the raw data or introduced during ingestion.
    """

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    """
    Timestamp of when this record was ingested into the database.
    Uses UTC to avoid timezone ambiguity.
    """
