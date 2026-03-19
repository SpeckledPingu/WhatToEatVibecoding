"""
recipes.py — Recipe endpoints for the AUTHENTICATED WhatToEat API.

COMPARING THIS TO THE SIMPLE API (src/api/simple/routes/recipes.py):
This file is NEARLY IDENTICAL to the simple version. The differences are
minimal and concentrated — which is the whole point! Adding authentication
to an API requires surprisingly little code change.

THE ONLY DIFFERENCES:
  1. Import: We import `get_current_user` and `User` from our auth module
  2. Import: Schemas come from authenticated.schemas (which re-exports simple's)
  3. Protected endpoints: Add `current_user: User = Depends(get_current_user)`
     as a parameter to POST, PUT, and DELETE endpoints

That's it. The endpoint logic is EXACTLY the same. The `current_user` parameter
acts as a gatekeeper — FastAPI calls `get_current_user` BEFORE your endpoint
runs. If the token is invalid, the endpoint never executes.

READ BOTH FILES SIDE BY SIDE to see how little changes!
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from src.database import get_engine, get_session, create_db_and_tables
from src.models.recipe import Recipe
from src.models.recipe_matching import RecipeMatchSummary

# Import schemas from the authenticated schemas module
# (which re-exports everything from the simple API's schemas)
from src.api.authenticated.schemas import (
    MessageResponse,
    RecipeCreate,
    RecipeListResponse,
    RecipeMatchResponse,
    RecipeResponse,
    RecipeUpdate,
)

# THIS IS NEW — import the auth dependency and User model
from src.api.authenticated.auth import User, get_current_user

router = APIRouter()


# ==========================================================================
# GET /recipes — List all recipes (with optional filters)
# ==========================================================================
# 🔓 PUBLIC: Reading recipes is safe and non-destructive — no auth needed.
# Anyone can browse recipes without logging in, just like browsing a cookbook
# in a bookstore. No data is modified, so there's no security risk.
#
# COMPARE TO SIMPLE API: This endpoint is IDENTICAL — no auth parameter added.

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

    🔓 **Public** — no authentication required.
    """
    query = select(Recipe)

    if weather_temp:
        query = query.where(Recipe.weather_temp == weather_temp)
    if weather_condition:
        query = query.where(Recipe.weather_condition == weather_condition)
    if search:
        query = query.where(Recipe.name.contains(search))  # type: ignore[union-attr]

    recipes = session.exec(query).all()

    return RecipeListResponse(
        count=len(recipes),
        recipes=[RecipeResponse.model_validate(r) for r in recipes],
    )


# ==========================================================================
# GET /recipes/makeable — Recipes you can make right now
# ==========================================================================
# 🔓 PUBLIC: Reading match data is safe — no data changes.

@router.get("/makeable", response_model=list[RecipeMatchResponse])
def get_makeable_recipes(session: Session = Depends(get_session)):
    """
    Get recipes where ALL ingredients are currently in your active inventory.

    🔓 **Public** — no authentication required.
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
# 🔓 PUBLIC: Reading data is always safe.

@router.get("/almost-makeable", response_model=list[RecipeMatchResponse])
def get_almost_makeable_recipes(
    max_missing: int = Query(
        default=2, ge=1, description="Maximum number of missing ingredients"
    ),
    session: Session = Depends(get_session),
):
    """
    Get recipes that are missing only a few ingredients.

    🔓 **Public** — no authentication required.
    """
    results = session.exec(
        select(RecipeMatchSummary).where(
            RecipeMatchSummary.missing_ingredients <= max_missing,
            RecipeMatchSummary.missing_ingredients > 0,
        )
    ).all()

    sorted_results = sorted(results, key=lambda r: r.missing_ingredients)
    return [RecipeMatchResponse.model_validate(r) for r in sorted_results]


# ==========================================================================
# GET /recipes/with-substitutions — Recipes with ingredient swaps
# ==========================================================================
# 🔓 PUBLIC: Viewing substitution suggestions is safe and non-destructive.

@router.get("/with-substitutions", response_model=list[RecipeMatchResponse])
def get_recipes_with_substitutions(session: Session = Depends(get_session)):
    """
    Get recipes where missing ingredients have same-category substitutes.

    🔓 **Public** — no authentication required.
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
# 🔓 PUBLIC: Viewing a single recipe is safe — like reading a page in a cookbook.

@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_recipe(recipe_id: int, session: Session = Depends(get_session)):
    """
    Get a single recipe by its unique ID.

    🔓 **Public** — no authentication required.
    """
    recipe = session.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id {recipe_id} not found",
        )

    return RecipeResponse.model_validate(recipe)


# ==========================================================================
# POST /recipes — Create a new recipe (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: Creating data changes the database — only authenticated users
# should be able to add new recipes. Without auth, anyone could flood the
# database with junk data.
#
# COMPARE TO SIMPLE API: The ONLY difference is the `current_user` parameter.
# That single parameter triggers the entire authentication chain:
#   1. FastAPI extracts the token from the Authorization header
#   2. get_current_user() validates the token and looks up the user
#   3. If valid, the User object is injected as `current_user`
#   4. If invalid, a 401 error is returned BEFORE this function runs

@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe_data: RecipeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← THIS IS THE ONLY DIFFERENCE!
):
    """
    Create a new recipe.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
    """
    recipe_dict = recipe_data.model_dump()
    recipe_dict["ingredients"] = [
        ing.model_dump() for ing in recipe_data.ingredients
    ]
    recipe_dict["source_format"] = "api"
    recipe_dict["source_file"] = "api_upload"

    recipe = Recipe(**recipe_dict)
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    return RecipeResponse.model_validate(recipe)


# ==========================================================================
# PUT /recipes/{recipe_id} — Update an existing recipe (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: Modifying existing data requires authentication — only verified
# users should be able to change recipe content.

@router.put("/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: int,
    recipe_data: RecipeUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← THIS IS THE ONLY DIFFERENCE!
):
    """
    Update an existing recipe. Only provided fields are changed.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
    """
    recipe = session.get(Recipe, recipe_id)

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id {recipe_id} not found",
        )

    update_data = recipe_data.model_dump(exclude_unset=True)
    if "ingredients" in update_data and update_data["ingredients"] is not None:
        update_data["ingredients"] = [
            ing.model_dump() for ing in recipe_data.ingredients
        ]

    for field, value in update_data.items():
        setattr(recipe, field, value)

    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    return RecipeResponse.model_validate(recipe)


# ==========================================================================
# DELETE /recipes/{recipe_id} — Delete a recipe (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: DELETE is destructive — once a recipe is gone, it's gone.
# Only authenticated users should be able to permanently remove data.

@router.delete("/{recipe_id}", response_model=MessageResponse)
def delete_recipe(
    recipe_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← THIS IS THE ONLY DIFFERENCE!
):
    """
    Permanently delete a recipe.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
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

    return MessageResponse(message=f"Recipe '{recipe_name}' (id={recipe_id}) deleted")
