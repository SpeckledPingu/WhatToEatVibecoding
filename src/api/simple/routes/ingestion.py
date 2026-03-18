"""
ingestion.py — Data ingestion endpoints for the WhatToEat API.

WHAT IS INGESTION?
Ingestion is the process of reading external data files (JSON, CSV) and loading
them into the database. It's the first step in our data pipeline:

  data files → INGESTION → database tables → normalization → matching

WHY ALL POST?
Every endpoint here uses HTTP POST because they all MODIFY the database.
Even though the client doesn't send a request body, POST is the correct method
because:
  - GET must be "safe" (no side effects) — these endpoints change data
  - POST means "process this request and create/modify resources"
  - The request body being empty is fine — the data comes from files on the server

PIPELINE ORDER
The ingestion pipeline has a specific order:
  1. Recipes → loads recipe JSON/Markdown into the Recipe table
  2. Receipts → loads receipt CSVs into the Receipt table
  3. Pantry → loads pantry CSVs into the PantryItem table
  4. Inventory refresh → normalizes and unifies into ActiveInventory
  5. Matching refresh → matches recipes against inventory

POST /ingest/all runs all five steps in the correct order.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from src.database import get_session
from src.models.recipe import Recipe
from src.models.receipt import Receipt
from src.models.pantry import PantryItem
from src.models.inventory import ActiveInventory
from src.models.recipe_matching import RecipeMatchSummary
from src.api.simple.schemas import IngestionStatusResponse

router = APIRouter()


# ==========================================================================
# POST /ingest/recipes — Ingest recipe files
# ==========================================================================

@router.post("/recipes", response_model=IngestionStatusResponse)
def ingest_recipes(session: Session = Depends(get_session)):
    """
    Trigger recipe ingestion from JSON files in data/recipes/json/.

    Scans for recipe JSON files, validates them, and loads them into the
    Recipe table. Existing recipes with the same name are updated (upsert).
    Companion Markdown files from data/recipes/markdown/ are attached
    automatically when filenames match.
    """
    try:
        # Count before
        before = session.exec(select(func.count()).select_from(Recipe)).one()

        from src.ingestion.recipes import ingest_recipes as run_recipe_ingestion

        run_recipe_ingestion()

        # Count after (need a fresh session since ingestion uses its own)
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
# POST /ingest/receipts — Ingest receipt files
# ==========================================================================

@router.post("/receipts", response_model=IngestionStatusResponse)
def ingest_receipts(session: Session = Depends(get_session)):
    """
    Trigger receipt ingestion from CSV files in data/receipts/.

    Reads receipt CSVs, normalizes column names, parses dates and prices,
    checks for duplicates, and inserts new rows into the Receipt table.
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
# POST /ingest/pantry — Ingest pantry files
# ==========================================================================

@router.post("/pantry", response_model=IngestionStatusResponse)
def ingest_pantry(session: Session = Depends(get_session)):
    """
    Trigger pantry ingestion from CSV files in data/pantry/.

    Reads pantry CSVs, normalizes column names, parses dates, checks for
    duplicates, and inserts new rows into the PantryItem table.
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
# POST /ingest/all — Run the full pipeline
# ==========================================================================

@router.post("/all", response_model=IngestionStatusResponse)
def ingest_all():
    """
    Run the complete data pipeline in the correct order:

    1. **Ingest recipes** — load recipe JSON/Markdown files
    2. **Ingest receipts** — load receipt CSV files
    3. **Ingest pantry** — load pantry CSV files
    4. **Rebuild active inventory** — normalize and unify all inventory
    5. **Rebuild recipe matching** — match recipes against inventory

    This is the "do everything" button. Run it after adding new data files
    or updating the normalization config.

    Returns a combined status report showing results from each step.
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

    # Step 4: Rebuild active inventory (normalization)
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
