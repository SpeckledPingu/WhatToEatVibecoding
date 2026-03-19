"""
matching.py — Recipe matching endpoints for the AUTHENTICATED WhatToEat API.

COMPARING THIS TO THE SIMPLE API (src/api/simple/routes/matching.py):
Nearly identical. The only difference:
  - POST /matching/refresh is PROTECTED (requires authentication)
  - All GET endpoints remain PUBLIC

WHY IS ONLY /refresh PROTECTED?
GET endpoints just read pre-computed matching data — safe for anyone.
POST /matching/refresh REBUILDS the matching tables, dropping and recreating
data. This is a significant operation that should require authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from src.database import get_session
from src.models.recipe_matching import RecipeIngredientMatch, RecipeMatchSummary
from src.api.authenticated.schemas import (
    IngestionStatusResponse,
    IngredientMatchResponse,
    RecipeMatchResponse,
    ShoppingListItem,
    ShoppingListResponse,
)

# THIS IS NEW — import the auth dependency and User model
from src.api.authenticated.auth import User, get_current_user

router = APIRouter()


# ==========================================================================
# GET /matching/summary — Full match summary for all recipes
# ==========================================================================
# 🔓 PUBLIC: Viewing match results is safe — just reading pre-computed data.

@router.get("/summary", response_model=list[RecipeMatchResponse])
def get_match_summary(session: Session = Depends(get_session)):
    """
    Get the recipe match summary for every recipe.

    🔓 **Public** — no authentication required.
    """
    results = session.exec(select(RecipeMatchSummary)).all()
    return [RecipeMatchResponse.model_validate(r) for r in results]


# ==========================================================================
# GET /matching/recipe/{recipe_id} — Ingredient-level detail
# ==========================================================================
# 🔓 PUBLIC: Viewing ingredient match details is safe, read-only data.

@router.get("/recipe/{recipe_id}", response_model=list[IngredientMatchResponse])
def get_recipe_match_detail(
    recipe_id: int, session: Session = Depends(get_session)
):
    """
    Get ingredient-level match detail for a specific recipe.

    🔓 **Public** — no authentication required.
    """
    results = session.exec(
        select(RecipeIngredientMatch).where(
            RecipeIngredientMatch.recipe_id == recipe_id
        )
    ).all()

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No match data found for recipe_id {recipe_id}. "
            "Try running POST /matching/refresh first.",
        )

    return [IngredientMatchResponse.model_validate(r) for r in results]


# ==========================================================================
# GET /matching/shopping-list — Consolidated shopping list
# ==========================================================================
# 🔓 PUBLIC: Generating a shopping list is a read-only aggregation.

@router.get("/shopping-list", response_model=ShoppingListResponse)
def get_shopping_list(
    recipe_ids: str = Query(
        ..., description="Comma-separated list of recipe IDs, e.g. '1,3,5'"
    ),
    session: Session = Depends(get_session),
):
    """
    Generate a consolidated shopping list for selected recipes.

    🔓 **Public** — no authentication required.
    """
    try:
        id_list = [int(x.strip()) for x in recipe_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="recipe_ids must be comma-separated integers, e.g. '1,3,5'",
        )

    if not id_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one recipe_id is required",
        )

    results = session.exec(
        select(RecipeIngredientMatch).where(
            RecipeIngredientMatch.recipe_id.in_(id_list),  # type: ignore[union-attr]
            RecipeIngredientMatch.is_available == False,  # noqa: E712
        )
    ).all()

    ingredient_map: dict[str, dict] = {}
    for r in results:
        if r.ingredient_name not in ingredient_map:
            ingredient_map[r.ingredient_name] = {
                "ingredient_name": r.ingredient_name,
                "category": r.ingredient_category,
                "recipes": set(),
            }
        ingredient_map[r.ingredient_name]["recipes"].add(r.recipe_name)

    items = []
    for entry in ingredient_map.values():
        items.append(
            ShoppingListItem(
                ingredient_name=entry["ingredient_name"],
                category=entry["category"],
                needed_by_recipes=", ".join(sorted(entry["recipes"])),
                recipe_count=len(entry["recipes"]),
            )
        )
    items.sort(key=lambda x: x.recipe_count, reverse=True)

    return ShoppingListResponse(
        recipe_ids=id_list,
        total_items=len(items),
        items=items,
    )


# ==========================================================================
# POST /matching/refresh — Rebuild recipe matching tables (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: Rebuilding matching tables is a heavy operation that drops
# and recreates data. Only authenticated users should trigger this rebuild.

@router.post("/refresh", response_model=IngestionStatusResponse)
def refresh_matching(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← THIS IS THE ONLY DIFFERENCE!
):
    """
    Rebuild the recipe matching tables from current recipes and inventory.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
    """
    try:
        from src.normalization.build_recipe_matching import build_recipe_matching

        build_recipe_matching()

        summary_count = session.exec(
            select(func.count()).select_from(RecipeMatchSummary)
        ).one()
        detail_count = session.exec(
            select(func.count()).select_from(RecipeIngredientMatch)
        ).one()

        return IngestionStatusResponse(
            operation="matching_refresh",
            status="success",
            message=f"Recipe matching rebuilt: {summary_count} recipes, {detail_count} ingredient matches",
            details={
                "recipe_count": summary_count,
                "ingredient_match_count": detail_count,
            },
        )
    except Exception as e:
        return IngestionStatusResponse(
            operation="matching_refresh",
            status="error",
            message=f"Matching refresh failed: {str(e)}",
        )
