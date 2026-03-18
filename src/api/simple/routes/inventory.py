"""
inventory.py — Inventory endpoints for the WhatToEat API.

WHAT IS ACTIVE INVENTORY?
The ActiveInventory table is a UNIFIED view of all food you currently have,
built by combining receipt data (things you bought) and pantry data (things
you inventoried). Each item has been normalized (cleaned names, assigned
categories) and enriched with expiration dates.

This is a DERIVED table — it's rebuilt from scratch when you call
POST /inventory/refresh. You don't edit it directly; you update the source
data (receipts, pantry) and rebuild.

WHY THESE ENDPOINTS?
These endpoints let a frontend (like our Streamlit app) display your current
inventory, filter by category or expiration, and trigger rebuilds — all
without the frontend needing to know anything about SQL or the database.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from src.database import get_session
from src.models.inventory import ActiveInventory
from src.api.simple.schemas import (
    IngestionStatusResponse,
    InventoryItemResponse,
    InventoryListResponse,
    MessageResponse,
)

router = APIRouter()


# ==========================================================================
# GET /inventory — List active inventory items
# ==========================================================================

@router.get("", response_model=InventoryListResponse)
def list_inventory(
    category: Optional[str] = Query(
        default=None, description="Filter by food category (e.g., 'dairy', 'protein')"
    ),
    expiring_within_days: Optional[int] = Query(
        default=None,
        ge=1,
        description="Only show items expiring within this many days",
    ),
    source: Optional[str] = Query(
        default=None, description="Filter by source: 'receipt' or 'pantry'"
    ),
    session: Session = Depends(get_session),
):
    """
    List all active (non-expired) inventory items, with optional filters.

    - **category**: Show only items in this food category
    - **expiring_within_days**: Show only items expiring within N days
    - **source**: Show only items from receipts or pantry

    The response includes summary statistics: total items and expired count.
    """
    # Base query: all inventory items
    query = select(ActiveInventory)

    if category:
        query = query.where(ActiveInventory.category == category)
    if source:
        query = query.where(ActiveInventory.source == source)
    if expiring_within_days:
        cutoff = date.today() + timedelta(days=expiring_within_days)
        query = query.where(
            ActiveInventory.expiration_date <= cutoff,
            ActiveInventory.is_expired == False,  # noqa: E712
        )

    items = session.exec(query).all()

    # Get total counts for the summary stats
    total_items = session.exec(
        select(func.count()).select_from(ActiveInventory)
    ).one()
    expired_count = session.exec(
        select(func.count())
        .select_from(ActiveInventory)
        .where(ActiveInventory.is_expired == True)  # noqa: E712
    ).one()

    return InventoryListResponse(
        count=len(items),
        total_items=total_items,
        expired_count=expired_count,
        items=[InventoryItemResponse.model_validate(i) for i in items],
    )


# ==========================================================================
# GET /inventory/expiring — Items expiring soon
# ==========================================================================
# Defined BEFORE /{item_id} so FastAPI doesn't try to parse "expiring" as an ID.

@router.get("/expiring", response_model=list[InventoryItemResponse])
def get_expiring_items(
    days: int = Query(
        default=7, ge=1, description="Show items expiring within this many days"
    ),
    session: Session = Depends(get_session),
):
    """
    Get inventory items expiring within the specified number of days.

    Defaults to 7 days. These are the "use it or lose it" items — cook with
    them soon to reduce food waste!
    """
    cutoff = date.today() + timedelta(days=days)

    items = session.exec(
        select(ActiveInventory).where(
            ActiveInventory.expiration_date <= cutoff,
            ActiveInventory.is_expired == False,  # noqa: E712
        )
    ).all()

    return [InventoryItemResponse.model_validate(i) for i in items]


# ==========================================================================
# GET /inventory/summary — Inventory statistics
# ==========================================================================

@router.get("/summary")
def get_inventory_summary(session: Session = Depends(get_session)):
    """
    Get summary statistics about the current inventory.

    Returns total item count, breakdown by category, expired count,
    and items expiring within 7 days.
    """
    all_items = session.exec(select(ActiveInventory)).all()

    total = len(all_items)
    expired = sum(1 for i in all_items if i.is_expired)
    cutoff = date.today() + timedelta(days=7)
    expiring_soon = sum(
        1
        for i in all_items
        if not i.is_expired and i.expiration_date and i.expiration_date <= cutoff
    )

    # Count items by category
    by_category: dict[str, int] = {}
    for item in all_items:
        by_category[item.category] = by_category.get(item.category, 0) + 1

    return {
        "total_items": total,
        "expired_count": expired,
        "expiring_within_7_days": expiring_soon,
        "active_items": total - expired,
        "by_category": by_category,
    }


# ==========================================================================
# POST /inventory/refresh — Rebuild the active inventory
# ==========================================================================
# This is a POST (not GET) because it MODIFIES the database — it drops and
# recreates the ActiveInventory table. Even though the client doesn't send
# a request body, POST is correct because the operation changes server state.

@router.post("/refresh", response_model=IngestionStatusResponse)
def refresh_inventory(session: Session = Depends(get_session)):
    """
    Rebuild the ActiveInventory table from receipt and pantry data.

    This runs the full normalization pipeline:
    1. Syncs normalization config to the database
    2. Reads all Receipt and PantryItem records
    3. Normalizes names, assigns categories, creates join keys
    4. Calculates expiration dates from shelf life data
    5. Writes everything to the ActiveInventory table

    The old ActiveInventory data is completely replaced.
    """
    try:
        from src.normalization.build_inventory import build_active_inventory

        build_active_inventory()

        # Count the results
        count = session.exec(
            select(func.count()).select_from(ActiveInventory)
        ).one()

        return IngestionStatusResponse(
            operation="inventory_refresh",
            status="success",
            message=f"Active inventory rebuilt with {count} items",
            details={"item_count": count},
        )
    except Exception as e:
        return IngestionStatusResponse(
            operation="inventory_refresh",
            status="error",
            message=f"Inventory refresh failed: {str(e)}",
        )


# ==========================================================================
# GET /inventory/{item_id} — Get a single inventory item
# ==========================================================================

@router.get("/{item_id}", response_model=InventoryItemResponse)
def get_inventory_item(item_id: int, session: Session = Depends(get_session)):
    """
    Get a single inventory item by its ID.

    - **item_id**: The unique identifier for the inventory item

    **HTTP 404** if the item doesn't exist.
    """
    item = session.get(ActiveInventory, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item with id {item_id} not found",
        )

    return InventoryItemResponse.model_validate(item)


# ==========================================================================
# DELETE /inventory/{item_id} — Remove an inventory item
# ==========================================================================

@router.delete("/{item_id}", response_model=MessageResponse)
def delete_inventory_item(item_id: int, session: Session = Depends(get_session)):
    """
    Remove an item from active inventory.

    Note: This only removes it from the unified ActiveInventory table. The
    original receipt or pantry record is preserved. The item will reappear
    if you run POST /inventory/refresh.

    - **item_id**: The ID of the item to remove

    **HTTP 404** if the item doesn't exist.
    """
    item = session.get(ActiveInventory, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item with id {item_id} not found",
        )

    item_name = item.item_name
    session.delete(item)
    session.commit()

    return MessageResponse(
        message=f"Inventory item '{item_name}' (id={item_id}) removed"
    )
