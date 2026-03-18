"""
schemas.py — Pydantic models for API request validation and response formatting.

WHY SEPARATE SCHEMAS FROM DATABASE MODELS?
The database models (in src/models/) define how data is STORED. These API schemas
define how data is SENT and RECEIVED over HTTP. They serve different purposes:

  - Security: A client creating a recipe shouldn't set the internal `id` or
    `created_at` — the server controls those. Separate schemas let you hide
    fields that clients shouldn't touch.
  - Validation: Pydantic schemas automatically check types, required fields,
    and constraints. If a client sends {"name": 123}, Pydantic will reject it
    with a clear error message before your code even runs.
  - Documentation: Every field description here appears in the auto-generated
    Swagger docs at /docs. Good descriptions = good documentation = happy users.

HOW PYDANTIC VALIDATION WORKS
When FastAPI receives a request, Pydantic:
  1. Parses the JSON body into Python objects
  2. Checks every field against its declared type (str, int, list, etc.)
  3. Validates constraints (min_length, ge=0, etc.)
  4. If anything fails, returns a 422 "Unprocessable Entity" response with a
     detailed error message explaining exactly what was wrong

This means you get automatic input validation for free — no manual
if-statements needed.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==========================================================================
# REQUEST MODELS — what the client sends TO the API
# ==========================================================================
# These define the shape of data in POST and PUT request bodies.
# Notice they do NOT include fields like `id` or `created_at` — those are
# controlled by the server, not the client.


class IngredientInput(BaseModel):
    """
    A single ingredient in a recipe creation/update request.

    This mirrors the ingredient objects stored in Recipe.ingredients JSON,
    but as a Pydantic model it gets validated automatically.
    """

    name: str = Field(
        ..., description="Ingredient name, e.g. 'flour' or 'chicken breast'"
    )
    quantity: float = Field(
        ..., ge=0, description="Amount needed, e.g. 2.5"
    )
    unit: str = Field(
        ..., description="Unit of measurement, e.g. 'cups', 'lbs', 'whole'"
    )
    category: str = Field(
        ...,
        description="Food category from config (protein, dairy, grain, spice, etc.)",
    )


class RecipeCreate(BaseModel):
    """
    Request body for creating a new recipe (POST /recipes).

    Includes all the fields needed to create a recipe. Fields like `id`,
    `created_at`, `source_format`, and `source_file` are set by the server.
    """

    name: str = Field(
        ..., min_length=1, description="Recipe name, e.g. 'Banana Bread'"
    )
    description: Optional[str] = Field(
        default=None, description="Brief description of the dish"
    )
    ingredients: list[IngredientInput] = Field(
        ..., min_length=1, description="List of ingredients (at least one required)"
    )
    instructions: list[str] = Field(
        ..., min_length=1, description="Step-by-step cooking instructions"
    )
    prep_time_minutes: Optional[int] = Field(
        default=None, ge=0, description="Minutes of active preparation"
    )
    cook_time_minutes: Optional[int] = Field(
        default=None, ge=0, description="Minutes of cooking time"
    )
    servings: Optional[int] = Field(
        default=None, ge=1, description="Number of portions"
    )
    weather_temp: Optional[str] = Field(
        default=None, description="Temperature tag: 'warm' or 'cold'"
    )
    weather_condition: Optional[str] = Field(
        default=None, description="Weather condition: 'rainy', 'sunny', or 'cloudy'"
    )
    tags: Optional[list[str]] = Field(
        default=None, description="Tags for filtering, e.g. ['breakfast', 'vegetarian']"
    )
    source: Optional[str] = Field(
        default=None, description="Where the recipe came from (URL or description)"
    )


class RecipeUpdate(BaseModel):
    """
    Request body for updating a recipe (PUT /recipes/{recipe_id}).

    ALL fields are optional — only the fields you include will be updated.
    This is called a "partial update" pattern: you send only what changed.
    """

    name: Optional[str] = Field(default=None, min_length=1, description="Recipe name")
    description: Optional[str] = Field(default=None, description="Brief description")
    ingredients: Optional[list[IngredientInput]] = Field(
        default=None, description="Updated ingredient list"
    )
    instructions: Optional[list[str]] = Field(
        default=None, description="Updated instructions"
    )
    prep_time_minutes: Optional[int] = Field(
        default=None, ge=0, description="Minutes of active preparation"
    )
    cook_time_minutes: Optional[int] = Field(
        default=None, ge=0, description="Minutes of cooking time"
    )
    servings: Optional[int] = Field(default=None, ge=1, description="Number of portions")
    weather_temp: Optional[str] = Field(
        default=None, description="Temperature tag: 'warm' or 'cold'"
    )
    weather_condition: Optional[str] = Field(
        default=None, description="Weather condition: 'rainy', 'sunny', or 'cloudy'"
    )
    tags: Optional[list[str]] = Field(default=None, description="Tags for filtering")
    source: Optional[str] = Field(default=None, description="Recipe source")


# ==========================================================================
# RESPONSE MODELS — what the API sends BACK to the client
# ==========================================================================
# These define the shape of JSON responses. They control what the client sees
# and ensure consistent response formatting across all endpoints.


class RecipeResponse(BaseModel):
    """Full recipe data returned by the API."""

    id: int = Field(description="Unique recipe identifier")
    name: str = Field(description="Recipe name")
    description: Optional[str] = Field(description="Brief description")
    ingredients: list = Field(description="List of ingredient objects")
    instructions: list = Field(description="Step-by-step instructions")
    prep_time_minutes: Optional[int] = Field(description="Prep time in minutes")
    cook_time_minutes: Optional[int] = Field(description="Cook time in minutes")
    servings: Optional[int] = Field(description="Number of portions")
    weather_temp: Optional[str] = Field(description="Temperature tag")
    weather_condition: Optional[str] = Field(description="Weather condition tag")
    tags: Optional[list] = Field(description="Recipe tags")
    source: Optional[str] = Field(description="Recipe source")
    source_file: str = Field(description="Original data file")
    created_at: datetime = Field(description="When the recipe was added")

    # model_config tells Pydantic to read attributes from ORM objects (SQLModel models)
    # instead of requiring a plain dictionary. This lets us pass a Recipe database
    # object directly and Pydantic will extract the fields automatically.
    model_config = {"from_attributes": True}


class RecipeListResponse(BaseModel):
    """A list of recipes with a count — used for GET /recipes."""

    count: int = Field(description="Total number of recipes returned")
    recipes: list[RecipeResponse] = Field(description="The recipe data")


class InventoryItemResponse(BaseModel):
    """A single item from the active inventory."""

    id: int = Field(description="Inventory record ID")
    item_name: str = Field(description="Normalized food name")
    original_name: str = Field(description="Name as it appeared in source data")
    category: str = Field(description="Food category (protein, dairy, etc.)")
    join_key: str = Field(description="Matching key (category:name)")
    quantity: float = Field(description="Amount available")
    unit: str = Field(description="Unit of measurement")
    source: str = Field(description="Data source: 'receipt' or 'pantry'")
    date_acquired: date = Field(description="When the item was purchased/inventoried")
    expiration_date: Optional[date] = Field(description="Estimated expiration date")
    is_expired: bool = Field(description="Whether the item has expired")

    model_config = {"from_attributes": True}


class InventoryListResponse(BaseModel):
    """List of inventory items with summary statistics."""

    count: int = Field(description="Number of items returned")
    total_items: int = Field(description="Total items in active inventory")
    expired_count: int = Field(description="Number of expired items")
    items: list[InventoryItemResponse] = Field(description="The inventory items")


class RecipeMatchResponse(BaseModel):
    """Recipe matching summary — how well a recipe matches current inventory."""

    recipe_id: int = Field(description="Recipe ID")
    recipe_name: str = Field(description="Recipe name")
    total_ingredients: int = Field(description="Total ingredients needed")
    available_ingredients: int = Field(description="Ingredients you have in stock")
    missing_ingredients: int = Field(description="Ingredients you're missing")
    missing_ingredient_list: list = Field(description="Names of missing ingredients")
    is_fully_makeable: bool = Field(description="True if all ingredients are available")
    has_category_substitutes: bool = Field(
        description="True if substitutes exist for missing ingredients"
    )
    substitute_details: list = Field(description="Details about possible substitutions")
    weather_temp: Optional[str] = Field(description="Temperature tag")
    weather_condition: Optional[str] = Field(description="Weather condition tag")
    uses_expiring_ingredients: bool = Field(
        description="True if recipe uses ingredients expiring soon"
    )
    expiring_ingredient_list: Optional[list] = Field(
        description="Details of expiring ingredients"
    )

    model_config = {"from_attributes": True}


class ShoppingListItem(BaseModel):
    """A single item on the shopping list."""

    ingredient_name: str = Field(description="What to buy")
    category: str = Field(description="Food category")
    needed_by_recipes: str = Field(description="Which recipes need this ingredient")
    recipe_count: int = Field(description="How many recipes need this")


class ShoppingListResponse(BaseModel):
    """Consolidated shopping list for selected recipes."""

    recipe_ids: list[int] = Field(description="Recipes this list was generated for")
    total_items: int = Field(description="Number of unique items to buy")
    items: list[ShoppingListItem] = Field(description="The shopping list items")


class IngestionStatusResponse(BaseModel):
    """Status report from running an ingestion or rebuild operation."""

    operation: str = Field(description="What operation was performed")
    status: str = Field(description="'success' or 'error'")
    message: str = Field(description="Human-readable status message")
    details: Optional[dict] = Field(
        default=None, description="Additional details (counts, errors, etc.)"
    )


class MessageResponse(BaseModel):
    """Simple message response for confirmations and errors."""

    message: str = Field(description="The response message")


class IngredientMatchResponse(BaseModel):
    """Ingredient-level match detail for a single recipe ingredient."""

    ingredient_name: str = Field(description="Normalized ingredient name")
    ingredient_category: str = Field(description="Food category")
    required_quantity: Optional[float] = Field(description="Amount the recipe needs")
    required_unit: Optional[str] = Field(description="Unit of measurement")
    is_available: bool = Field(description="Whether it's in stock")
    inventory_item_name: Optional[str] = Field(description="Matched inventory item")
    available_quantity: Optional[float] = Field(description="Amount in stock")
    category_substitute_available: bool = Field(
        description="Whether a same-category substitute exists"
    )
    substitute_item_name: Optional[str] = Field(description="Name of substitute item")

    model_config = {"from_attributes": True}
