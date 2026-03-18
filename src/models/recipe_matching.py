"""
recipe_matching.py — SQLModel definitions for recipe-to-inventory matching tables.

WHY TWO TABLES?
Recipe matching produces data at two different levels of detail, and different
queries need different granularity:

  1. **RecipeIngredientMatch** (DETAIL level) — one row per ingredient per recipe.
     Use this when you want to see WHICH specific ingredients are available or
     missing for a recipe. Like an itemized receipt.

  2. **RecipeMatchSummary** (SUMMARY level) — one row per recipe, aggregating
     ingredient matches. Use this when you want to find "which recipes can I make?"
     without caring about individual ingredients. Like a receipt total.

This detail + summary pattern is common in databases:
  - E-commerce: OrderItems (detail) + Orders (summary)
  - Banking: Transactions (detail) + AccountBalance (summary)
  - Analytics: Events (detail) + DailyMetrics (summary)

WHAT IS DENORMALIZATION?
You'll notice `recipe_name` appears in BOTH tables, even though it could be
looked up from the Recipe table using `recipe_id`. This is intentional
**denormalization** — storing redundant data for convenience.

  - Normalized (no redundancy): JOIN Recipe ON recipe_id to get the name
  - Denormalized (duplicated): recipe_name is right here, no JOIN needed

Trade-off: denormalization wastes a tiny bit of storage but makes queries
simpler and faster. For display-oriented data like this, it's a good trade.

THE ROLE OF NULL
In the detail table, `inventory_item_id` and `inventory_item_name` are Optional
(can be NULL). A NULL here means "this ingredient was NOT found in inventory" —
it's the missing piece in our RIGHT JOIN concept. NULL isn't an error; it's
meaningful data telling us "you don't have this ingredient."

THESE ARE DERIVED TABLES
Like ActiveInventory, both tables are REBUILT from scratch whenever the matching
pipeline runs. They reflect the current state of recipes and inventory — never
edit them directly.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Column, Field, SQLModel, JSON


class RecipeIngredientMatch(SQLModel, table=True):
    """
    One row per ingredient per recipe, recording whether that ingredient
    was found in the active inventory.

    This is the DETAIL table — it shows the ingredient-level breakdown of
    each recipe's match against inventory. Think of it as answering:
    "For Recipe X, which ingredients do I have and which am I missing?"

    The matching logic works like a conceptual RIGHT JOIN:
      - RIGHT side: recipe ingredients (we start here — every ingredient gets a row)
      - LEFT side: inventory items (we look here for matches)
      - NULL on the left: ingredient is missing from inventory
    """

    # -----------------------------------------------------------------------
    # Primary key
    # -----------------------------------------------------------------------
    id: Optional[int] = Field(default=None, primary_key=True)
    """Auto-incrementing unique identifier."""

    # -----------------------------------------------------------------------
    # Recipe reference
    # -----------------------------------------------------------------------
    recipe_id: int = Field(index=True)
    """Foreign key to the Recipe table. Indexed for fast lookups by recipe."""

    recipe_name: str
    """
    Denormalized recipe name for convenient display. Saves a JOIN to the
    Recipe table in most queries. See module docstring for why this is OK.
    """

    # -----------------------------------------------------------------------
    # Ingredient identification (from recipe)
    # -----------------------------------------------------------------------
    ingredient_name: str
    """The normalized ingredient name (after running through normalize_food_name)."""

    ingredient_join_key: str = Field(index=True)
    """The join key for this ingredient (e.g., 'protein:chicken breast')."""

    ingredient_category: str
    """The food category of this ingredient (e.g., 'protein', 'dairy')."""

    required_quantity: Optional[float] = Field(default=None)
    """How much the recipe needs (e.g., 2.0). NULL if the recipe didn't specify."""

    required_unit: Optional[str] = Field(default=None)
    """Unit of measurement (e.g., 'cups', 'lbs'). NULL if not specified."""

    # -----------------------------------------------------------------------
    # Inventory match result (from active inventory)
    # -----------------------------------------------------------------------
    inventory_item_id: Optional[int] = Field(default=None)
    """
    Foreign key to ActiveInventory. NULL if this ingredient is NOT in stock.
    A NULL here is the "missing ingredient" signal — the empty left side of
    our conceptual RIGHT JOIN.
    """

    inventory_item_name: Optional[str] = Field(default=None)
    """
    The inventory item name that matched. NULL if not in stock.
    May differ from ingredient_name if the match was approximate.
    """

    available_quantity: Optional[float] = Field(default=None)
    """How much of this ingredient is in stock. NULL if not available."""

    is_available: bool = Field(default=False)
    """
    True if this ingredient was found in active (non-expired) inventory.
    This is the key flag for determining recipe makeability.
    """

    # -----------------------------------------------------------------------
    # Category substitute matching
    # -----------------------------------------------------------------------
    category_substitute_available: bool = Field(default=False)
    """
    True if a same-category item exists in inventory that could substitute.
    For example, if the recipe needs cheddar but you have mozzarella (both
    dairy/cheese), this would be True. Reliability depends on the category's
    substitution rules in config/normalization_mappings.json.
    """

    substitute_item_name: Optional[str] = Field(default=None)
    """Name of the potential substitute item, if one was found."""

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    """When this match record was created. Changes on every rebuild."""


class RecipeMatchSummary(SQLModel, table=True):
    """
    One row per recipe, summarizing how well it matches current inventory.

    This is the SUMMARY table — it answers high-level questions like:
      - "Which recipes can I make right now?" (is_fully_makeable = True)
      - "What am I one ingredient away from?" (missing_ingredients = 1)
      - "Which recipes have substitutes available?" (has_category_substitutes = True)
      - "What should I cook before ingredients expire?" (uses_expiring_ingredients = True)

    Each row aggregates all the ingredient-level detail from RecipeIngredientMatch
    into convenient summary fields.
    """

    # -----------------------------------------------------------------------
    # Primary key
    # -----------------------------------------------------------------------
    id: Optional[int] = Field(default=None, primary_key=True)
    """Auto-incrementing unique identifier."""

    # -----------------------------------------------------------------------
    # Recipe reference
    # -----------------------------------------------------------------------
    recipe_id: int = Field(index=True)
    """Foreign key to the Recipe table."""

    recipe_name: str
    """Denormalized recipe name for convenient display."""

    # -----------------------------------------------------------------------
    # Ingredient match counts
    # -----------------------------------------------------------------------
    total_ingredients: int
    """Total number of ingredients in this recipe."""

    available_ingredients: int
    """How many ingredients are currently in stock (exact match)."""

    missing_ingredients: int
    """How many ingredients are NOT in stock. missing = total - available."""

    missing_ingredient_list: list = Field(default=[], sa_column=Column(JSON))
    """
    JSON list of missing ingredient names, e.g., ["cheddar", "sour cream"].
    Stored as JSON for easy display — no extra table needed for a simple list.
    """

    # -----------------------------------------------------------------------
    # Substitution info
    # -----------------------------------------------------------------------
    has_category_substitutes: bool = Field(default=False)
    """True if ANY missing ingredient has a same-category substitute in inventory."""

    substitute_details: list = Field(default=[], sa_column=Column(JSON))
    """
    JSON list of substitution details, e.g.:
    [{"missing": "cheddar", "substitute": "mozzarella", "category": "dairy"}]
    """

    # -----------------------------------------------------------------------
    # Makeability
    # -----------------------------------------------------------------------
    is_fully_makeable: bool = Field(default=False)
    """True if ALL ingredients are in stock. The recipe can be made right now."""

    # -----------------------------------------------------------------------
    # Weather tags (from recipe, for filtering)
    # -----------------------------------------------------------------------
    weather_temp: Optional[str] = Field(default=None)
    """'warm' or 'cold' — from the Recipe table, for weather-based filtering."""

    weather_condition: Optional[str] = Field(default=None)
    """'rainy', 'sunny', 'cloudy' — from the Recipe table."""

    # -----------------------------------------------------------------------
    # Expiration urgency
    # -----------------------------------------------------------------------
    uses_expiring_ingredients: bool = Field(default=False)
    """True if any matched (available) ingredient expires within 7 days."""

    expiring_ingredient_list: Optional[list] = Field(
        default=None, sa_column=Column(JSON)
    )
    """
    JSON list of expiring ingredient details, e.g.:
    [{"name": "spinach", "expiration_date": "2024-01-15", "days_until_expiry": 2}]
    """

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    """When this summary was created. Changes on every rebuild."""
