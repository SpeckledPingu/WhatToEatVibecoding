"""
ingestion.py — Data ingestion endpoints for the AUTHENTICATED WhatToEat API.

COMPARING THIS TO THE SIMPLE API (src/api/simple/routes/ingestion.py):
The only difference: ALL ingestion endpoints are PROTECTED.

WHY ARE ALL INGESTION ENDPOINTS PROTECTED?
Ingestion modifies the database — it reads files from disk and inserts/updates
rows in bulk. This is a powerful operation that could:
  - Overwrite existing data
  - Load corrupted or malicious files
  - Trigger expensive rebuilds
Only authenticated users should be able to trigger data ingestion.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from src.database import get_session
from src.models.recipe import Recipe
from src.models.receipt import Receipt
from src.models.pantry import PantryItem
from src.models.inventory import ActiveInventory
from src.models.recipe_matching import RecipeMatchSummary
from src.api.authenticated.schemas import IngestionStatusResponse

# THIS IS NEW — import the auth dependency and User model
from src.api.authenticated.auth import User, get_current_user

router = APIRouter()


# ==========================================================================
# POST /ingest/recipes — Ingest recipe files (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: Ingestion modifies the database in bulk — loading, parsing,
# and inserting data from files. Only authenticated users should trigger this.

@router.post("/recipes", response_model=IngestionStatusResponse)
def ingest_recipes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← PROTECTED
):
    """
    Trigger recipe ingestion from JSON files in data/recipes/json/.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
    """
    try:
        before = session.exec(select(func.count()).select_from(Recipe)).one()

        from src.ingestion.recipes import ingest_recipes as run_recipe_ingestion

        run_recipe_ingestion()

        from src.database import get_engine
        from sqlmodel import Session as Sess

        engine = get_engine()
        with Sess(engine) as fresh:
            after = fresh.exec(select(func.count()).select_from(Recipe)).one()

        return IngestionStatusResponse(
            operation="recipe_ingestion",
            status="success",
            message=f"Recipe ingestion complete. {after} total recipes ({after - before} new)",
            details={"before": before, "after": after, "new": after - before},
        )
    except Exception as e:
        return IngestionStatusResponse(
            operation="recipe_ingestion",
            status="error",
            message=f"Recipe ingestion failed: {str(e)}",
        )


# ==========================================================================
# POST /ingest/receipts — Ingest receipt files (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: Bulk data loading should only be triggered by authenticated users.

@router.post("/receipts", response_model=IngestionStatusResponse)
def ingest_receipts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← PROTECTED
):
    """
    Trigger receipt ingestion from CSV files in data/receipts/.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
    """
    try:
        before = session.exec(select(func.count()).select_from(Receipt)).one()

        from src.ingestion.receipts import ingest_receipts as run_receipt_ingestion

        run_receipt_ingestion()

        from src.database import get_engine
        from sqlmodel import Session as Sess

        engine = get_engine()
        with Sess(engine) as fresh:
            after = fresh.exec(select(func.count()).select_from(Receipt)).one()

        return IngestionStatusResponse(
            operation="receipt_ingestion",
            status="success",
            message=f"Receipt ingestion complete. {after} total receipts ({after - before} new)",
            details={"before": before, "after": after, "new": after - before},
        )
    except Exception as e:
        return IngestionStatusResponse(
            operation="receipt_ingestion",
            status="error",
            message=f"Receipt ingestion failed: {str(e)}",
        )


# ==========================================================================
# POST /ingest/pantry — Ingest pantry files (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: Bulk data loading should only be triggered by authenticated users.

@router.post("/pantry", response_model=IngestionStatusResponse)
def ingest_pantry(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← PROTECTED
):
    """
    Trigger pantry ingestion from CSV files in data/pantry/.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
    """
    try:
        before = session.exec(select(func.count()).select_from(PantryItem)).one()

        from src.ingestion.pantry import ingest_pantry as run_pantry_ingestion

        run_pantry_ingestion()

        from src.database import get_engine
        from sqlmodel import Session as Sess

        engine = get_engine()
        with Sess(engine) as fresh:
            after = fresh.exec(select(func.count()).select_from(PantryItem)).one()

        return IngestionStatusResponse(
            operation="pantry_ingestion",
            status="success",
            message=f"Pantry ingestion complete. {after} total items ({after - before} new)",
            details={"before": before, "after": after, "new": after - before},
        )
    except Exception as e:
        return IngestionStatusResponse(
            operation="pantry_ingestion",
            status="error",
            message=f"Pantry ingestion failed: {str(e)}",
        )


# ==========================================================================
# POST /ingest/all — Run the full pipeline (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: The full pipeline modifies every table in the database.
# This is the most powerful single operation — definitely requires authentication.

@router.post("/all", response_model=IngestionStatusResponse)
def ingest_all(
    current_user: User = Depends(get_current_user),  # ← PROTECTED
):
    """
    Run the complete data pipeline in order:
    recipes → receipts → pantry → inventory rebuild → matching rebuild.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
    """
    results = {}
    errors = []

    # Step 1: Ingest recipes
    try:
        from src.ingestion.recipes import ingest_recipes as run_recipes

        run_recipes()
        results["recipes"] = "success"
    except Exception as e:
        results["recipes"] = f"error: {str(e)}"
        errors.append(f"recipes: {str(e)}")

    # Step 2: Ingest receipts
    try:
        from src.ingestion.receipts import ingest_receipts as run_receipts

        run_receipts()
        results["receipts"] = "success"
    except Exception as e:
        results["receipts"] = f"error: {str(e)}"
        errors.append(f"receipts: {str(e)}")

    # Step 3: Ingest pantry
    try:
        from src.ingestion.pantry import ingest_pantry as run_pantry

        run_pantry()
        results["pantry"] = "success"
    except Exception as e:
        results["pantry"] = f"error: {str(e)}"
        errors.append(f"pantry: {str(e)}")

    # Step 4: Rebuild active inventory
    try:
        from src.normalization.build_inventory import build_active_inventory

        build_active_inventory()
        results["inventory_refresh"] = "success"
    except Exception as e:
        results["inventory_refresh"] = f"error: {str(e)}"
        errors.append(f"inventory: {str(e)}")

    # Step 5: Rebuild recipe matching
    try:
        from src.normalization.build_recipe_matching import build_recipe_matching

        build_recipe_matching()
        results["matching_refresh"] = "success"
    except Exception as e:
        results["matching_refresh"] = f"error: {str(e)}"
        errors.append(f"matching: {str(e)}")

    # Get final counts
    from src.database import get_engine
    from sqlmodel import Session

    engine = get_engine()
    with Session(engine) as session:
        recipe_count = session.exec(select(func.count()).select_from(Recipe)).one()
        inventory_count = session.exec(
            select(func.count()).select_from(ActiveInventory)
        ).one()
        match_count = session.exec(
            select(func.count()).select_from(RecipeMatchSummary)
        ).one()

    overall_status = "success" if not errors else "partial_success"
    if len(errors) == 5:
        overall_status = "error"

    return IngestionStatusResponse(
        operation="full_pipeline",
        status=overall_status,
        message=(
            f"Pipeline complete: {recipe_count} recipes, "
            f"{inventory_count} inventory items, "
            f"{match_count} recipe matches"
        ),
        details={
            "step_results": results,
            "final_counts": {
                "recipes": recipe_count,
                "inventory_items": inventory_count,
                "recipe_matches": match_count,
            },
            "errors": errors if errors else None,
        },
    )
