"""
matching.py — Recipe matching endpoints for the WhatToEat API.

HOW RECIPE MATCHING WORKS
Recipe matching connects your recipes to your inventory to answer the question:
"What can I cook with what I have?" The matching pipeline (built in WS05):

  1. Takes each recipe's ingredient list
  2. Normalizes ingredient names using the same pipeline as inventory items
  3. Creates join keys (e.g., "dairy:butter") and looks them up in ActiveInventory
  4. Records matches and misses in RecipeIngredientMatch (detail table)
  5. Aggregates into RecipeMatchSummary (summary table)

These endpoints expose that pre-computed matching data through the API.
The matching data is rebuilt when you call POST /matching/refresh.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from src.database import get_session
from src.models.recipe_matching import RecipeIngredientMatch, RecipeMatchSummary
from src.api.simple.schemas import (
    IngestionStatusResponse,
    IngredientMatchResponse,
    RecipeMatchResponse,
    ShoppingListItem,
    ShoppingListResponse,
)

router = APIRouter()


# ==========================================================================
# GET /matching/summary — Full match summary for all recipes
# ==========================================================================

@router.get("/summary", response_model=list[RecipeMatchResponse])
def get_match_summary(session: Session = Depends(get_session)):
    """
    Get the recipe match summary for every recipe in the database.

    Each entry shows how many ingredients are available vs. missing,
    whether the recipe is fully makeable, and if substitutes exist.

    **Tip:** Run POST /matching/refresh first if this returns empty.
    """
    results = session.exec(select(RecipeMatchSummary)).all()
    return [RecipeMatchResponse.model_validate(r) for r in results]


# ==========================================================================
# GET /matching/recipe/{recipe_id} — Ingredient-level detail
# ==========================================================================

@router.get("/recipe/{recipe_id}", response_model=list[IngredientMatchResponse])
def get_recipe_match_detail(
    recipe_id: int, session: Session = Depends(get_session)
):
    """
    Get the ingredient-level match detail for a specific recipe.

    Shows every ingredient with its availability status, matched inventory
    item, quantities, and potential substitutes. This is the most detailed
    view of a recipe's match against your inventory.

    - **recipe_id**: The ID of the recipe to examine

    **HTTP 404** if no match data exists for this recipe.
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

@router.get("/shopping-list", response_model=ShoppingListResponse)
def get_shopping_list(
    recipe_ids: str = Query(
        ..., description="Comma-separated list of recipe IDs, e.g. '1,3,5'"
    ),
    session: Session = Depends(get_session),
):
    """
    Generate a consolidated, deduplicated shopping list for selected recipes.

    Given a list of recipe IDs, finds all MISSING ingredients across those
    recipes and deduplicates them. If 3 recipes all need garlic, garlic
    appears once on the list.

    - **recipe_ids**: Comma-separated recipe IDs (e.g., "1,3,5")

    Returns the shopping list sorted by how many recipes need each item.
    """
    # Parse the comma-separated IDs into a list of integers
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

    # Find all missing ingredients for these recipes
    results = session.exec(
        select(RecipeIngredientMatch).where(
            RecipeIngredientMatch.recipe_id.in_(id_list),  # type: ignore[union-attr]
            RecipeIngredientMatch.is_available == False,  # noqa: E712
        )
    ).all()

    # Deduplicate by ingredient, tracking which recipes need it
    ingredient_map: dict[str, dict] = {}
    for r in results:
        if r.ingredient_name not in ingredient_map:
            ingredient_map[r.ingredient_name] = {
                "ingredient_name": r.ingredient_name,
                "category": r.ingredient_category,
                "recipes": set(),
            }
        ingredient_map[r.ingredient_name]["recipes"].add(r.recipe_name)

    # Build the response items, sorted by most-needed first
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
# POST /matching/refresh — Rebuild recipe matching tables
# ==========================================================================
# POST because it modifies the database (drops and recreates matching tables).

@router.post("/refresh", response_model=IngestionStatusResponse)
def refresh_matching(session: Session = Depends(get_session)):
    """
    Rebuild the recipe matching tables from current recipes and inventory.

    This runs the full matching pipeline:
    1. Drops existing RecipeIngredientMatch and RecipeMatchSummary tables
    2. Loads all recipes and active (non-expired) inventory
    3. Matches each recipe's ingredients against inventory using join keys
    4. Checks for category-level substitutes for missing ingredients
    5. Builds summary records with makeability and expiration info

    **Important:** Run POST /inventory/refresh first to ensure inventory is current.
    """
    try:
        from src.normalization.build_recipe_matching import build_recipe_matching

        build_recipe_matching()

        # Count the results
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
