"""
recipes.py — Recipe endpoints for the WhatToEat API.

WHAT ARE ENDPOINTS?
An endpoint is a specific URL that the API responds to. Each endpoint handles
one type of request — listing recipes, getting a single recipe, creating one, etc.

REST CONVENTION: RESOURCE-BASED URLS
In REST APIs, URLs represent "resources" (things), and HTTP methods represent
"actions" (what to do with them):
  - GET /recipes        → Read ALL recipes (a collection)
  - GET /recipes/5      → Read ONE recipe (a specific item)
  - POST /recipes       → Create a NEW recipe
  - PUT /recipes/5      → Update an EXISTING recipe
  - DELETE /recipes/5   → Delete a recipe

The URL says WHAT, the HTTP method says HOW. This pattern is so common that
most developers can guess how an API works just from the URLs.

HOW FASTAPI ROUTERS WORK
A router is a group of related endpoints. Instead of putting every endpoint
in main.py, we organize them into files by topic (recipes, inventory, etc.).
The router collects endpoints defined here, and main.py includes the whole
group with a URL prefix like "/recipes".
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from src.database import get_engine, get_session, create_db_and_tables
from src.models.recipe import Recipe
from src.models.recipe_matching import RecipeMatchSummary
from src.api.simple.schemas import (
    MessageResponse,
    RecipeCreate,
    RecipeListResponse,
    RecipeMatchResponse,
    RecipeResponse,
    RecipeUpdate,
)

# Create a router — this collects all the endpoints defined in this file.
# The prefix and tags are set in main.py when this router is included.
router = APIRouter()


# ==========================================================================
# GET /recipes — List all recipes (with optional filters)
# ==========================================================================
# HTTP GET is for READING data. It should never modify anything in the database.
# Query parameters (the ?key=value part of a URL) are used to filter results.
# Example: GET /recipes?weather_temp=warm&search=cake

@router.get("", response_model=RecipeListResponse)
def list_recipes(
    weather_temp: Optional[str] = Query(
        default=None, description="Filter by temperature: 'warm' or 'cold'"
    ),
    weather_condition: Optional[str] = Query(
        default=None, description="Filter by weather: 'rainy', 'sunny', or 'cloudy'"
    ),
    search: Optional[str] = Query(
        default=None, description="Search recipes by name (case-insensitive)"
    ),
    session: Session = Depends(get_session),
):
    """
    List all recipes, optionally filtered by weather or name search.

    - **weather_temp**: Filter recipes tagged for warm or cold weather
    - **weather_condition**: Filter by rainy, sunny, or cloudy conditions
    - **search**: Find recipes whose name contains this text (case-insensitive)

    Returns all matching recipes with a count. If no filters are provided,
    returns every recipe in the database.
    """
    # Start building a query — select() creates a SQL SELECT statement
    query = select(Recipe)

    # Apply filters only if the client provided them
    if weather_temp:
        query = query.where(Recipe.weather_temp == weather_temp)
    if weather_condition:
        query = query.where(Recipe.weather_condition == weather_condition)
    if search:
        # .contains() generates SQL LIKE '%search%' for substring matching
        query = query.where(Recipe.name.contains(search))  # type: ignore[union-attr]

    recipes = session.exec(query).all()

    # Return a structured response with count + list
    return RecipeListResponse(
        count=len(recipes),
        recipes=[RecipeResponse.model_validate(r) for r in recipes],
    )


# ==========================================================================
# GET /recipes/makeable — Recipes you can make right now
# ==========================================================================
# This endpoint MUST be defined BEFORE /recipes/{recipe_id} because FastAPI
# matches routes in order. If {recipe_id} came first, "makeable" would be
# interpreted as a recipe_id and cause an error.

@router.get("/makeable", response_model=list[RecipeMatchResponse])
def get_makeable_recipes(session: Session = Depends(get_session)):
    """
    Get recipes where ALL ingredients are currently in your active inventory.

    These are the recipes you can make right now without buying anything.
    Data comes from the RecipeMatchSummary table built by the matching pipeline.

    **Tip:** If this returns empty, try running POST /matching/refresh first
    to rebuild the matching data.
    """
    results = session.exec(
        select(RecipeMatchSummary).where(
            RecipeMatchSummary.is_fully_makeable == True  # noqa: E712
        )
    ).all()

    return [RecipeMatchResponse.model_validate(r) for r in results]


# ==========================================================================
# GET /recipes/almost-makeable — Recipes you're close to making
# ==========================================================================

@router.get("/almost-makeable", response_model=list[RecipeMatchResponse])
def get_almost_makeable_recipes(
    max_missing: int = Query(
        default=2, ge=1, description="Maximum number of missing ingredients"
    ),
    session: Session = Depends(get_session),
):
    """
    Get recipes that are missing only a few ingredients, sorted by fewest missing.

    Perfect for deciding what to cook if you're willing to buy 1-2 items.

    - **max_missing**: Include recipes missing up to this many ingredients (default: 2)
    """
    results = session.exec(
        select(RecipeMatchSummary).where(
            RecipeMatchSummary.missing_ingredients <= max_missing,
            RecipeMatchSummary.missing_ingredients > 0,
        )
    ).all()

    # Sort by fewest missing ingredients first — the closest to makeable
    sorted_results = sorted(results, key=lambda r: r.missing_ingredients)

    return [RecipeMatchResponse.model_validate(r) for r in sorted_results]


# ==========================================================================
# GET /recipes/with-substitutions — Recipes with ingredient swaps
# ==========================================================================

@router.get("/with-substitutions", response_model=list[RecipeMatchResponse])
def get_recipes_with_substitutions(session: Session = Depends(get_session)):
    """
    Get recipes where missing ingredients have same-category substitutes in stock.

    For example, if a recipe needs cheddar but you have mozzarella, the recipe
    appears here with substitution details. Whether the swap actually works
    depends on the recipe — the API just identifies the possibility.
    """
    results = session.exec(
        select(RecipeMatchSummary).where(
            RecipeMatchSummary.has_category_substitutes == True  # noqa: E712
        )
    ).all()

    return [RecipeMatchResponse.model_validate(r) for r in results]


# ==========================================================================
# GET /recipes/{recipe_id} — Get a single recipe by ID
# ==========================================================================
# Path parameters (the {recipe_id} part) identify a SPECIFIC resource.
# Unlike query params (?key=value), path params are required — the URL
# itself is different for each recipe: /recipes/1, /recipes/2, etc.

@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_recipe(recipe_id: int, session: Session = Depends(get_session)):
    """
    Get a single recipe by its unique ID.

    Returns the full recipe data including ingredients, instructions, and metadata.

    - **recipe_id**: The unique numeric identifier for the recipe

    **HTTP 404** is returned if no recipe exists with that ID.
    """
    recipe = session.get(Recipe, recipe_id)

    if not recipe:
        # 404 Not Found — the standard HTTP status code for "this resource doesn't exist"
        # This is not an error in your code — it's a normal response meaning "I looked,
        # but there's nothing here with that ID."
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id {recipe_id} not found",
        )

    return RecipeResponse.model_validate(recipe)


# ==========================================================================
# POST /recipes — Create a new recipe
# ==========================================================================
# HTTP POST is for CREATING new resources. The client sends the recipe data
# in the request body (as JSON), and the server assigns an ID and saves it.
# Convention: return 201 Created (not 200 OK) to signal that something new was made.

@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_recipe(recipe_data: RecipeCreate, session: Session = Depends(get_session)):
    """
    Create a new recipe.

    Send a JSON body with the recipe details. The server assigns an ID and
    records the creation timestamp automatically.

    **HTTP 201 Created** means the recipe was saved successfully.
    **HTTP 422 Unprocessable Entity** means the request body was malformed
    (e.g., missing required fields, wrong types).
    """
    # Convert the Pydantic input model to a database model
    # .model_dump() turns the Pydantic object into a plain dictionary
    recipe_dict = recipe_data.model_dump()

    # Convert IngredientInput objects to plain dicts for JSON storage
    recipe_dict["ingredients"] = [
        ing.model_dump() for ing in recipe_data.ingredients
    ]

    # Set server-controlled fields
    recipe_dict["source_format"] = "api"
    recipe_dict["source_file"] = "api_upload"

    recipe = Recipe(**recipe_dict)
    session.add(recipe)
    session.commit()
    # refresh() reloads the object from the database to get the auto-generated
    # id and any default values the database applied
    session.refresh(recipe)

    return RecipeResponse.model_validate(recipe)


# ==========================================================================
# PUT /recipes/{recipe_id} — Update an existing recipe
# ==========================================================================
# HTTP PUT is for UPDATING existing resources. Only the fields included in
# the request body are changed — all other fields stay the same.

@router.put("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: int,
    recipe_data: RecipeUpdate,
    session: Session = Depends(get_session),
):
    """
    Update an existing recipe. Only provided fields are changed.

    Send a JSON body with the fields you want to update — any fields you omit
    will keep their current values.

    - **recipe_id**: The ID of the recipe to update

    **HTTP 404** if the recipe doesn't exist.
    """
    recipe = session.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id {recipe_id} not found",
        )

    # model_dump(exclude_unset=True) only returns fields the client actually sent,
    # ignoring fields left at their default (None). This is how partial updates work.
    update_data = recipe_data.model_dump(exclude_unset=True)

    # Convert IngredientInput objects to plain dicts if ingredients were updated
    if "ingredients" in update_data and update_data["ingredients"] is not None:
        update_data["ingredients"] = [
            ing.model_dump() for ing in recipe_data.ingredients
        ]

    # Apply each updated field to the database object
    for field, value in update_data.items():
        setattr(recipe, field, value)

    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    return RecipeResponse.model_validate(recipe)


# ==========================================================================
# DELETE /recipes/{recipe_id} — Delete a recipe
# ==========================================================================
# HTTP DELETE removes a resource. This is DESTRUCTIVE — once deleted, the
# recipe is gone from the database. In a production API, you might use
# "soft delete" (marking as inactive) instead, but for learning we use
# a real delete.

@router.delete("/{recipe_id}", response_model=MessageResponse)
def delete_recipe(recipe_id: int, session: Session = Depends(get_session)):
    """
    Permanently delete a recipe.

    **Warning:** This cannot be undone! The recipe and all its data will be
    removed from the database.

    - **recipe_id**: The ID of the recipe to delete

    **HTTP 404** if the recipe doesn't exist.
    """
    recipe = session.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id {recipe_id} not found",
        )

    recipe_name = recipe.name
    session.delete(recipe)
    session.commit()

    # 200 OK with a confirmation message
    return MessageResponse(message=f"Recipe '{recipe_name}' (id={recipe_id}) deleted")
