"""
inventory.py — Inventory endpoints for the AUTHENTICATED WhatToEat API.

COMPARING THIS TO THE SIMPLE API (src/api/simple/routes/inventory.py):
Nearly identical. The only differences:
  1. Import get_current_user and User from the auth module
  2. Protected endpoints (POST /refresh, DELETE /{item_id}) add the
     `current_user: User = Depends(get_current_user)` parameter
  3. Public endpoints (all GETs) remain unchanged

WHICH ENDPOINTS ARE PROTECTED AND WHY:
  - POST /inventory/refresh — rebuilds the entire inventory table (destructive)
  - DELETE /inventory/{item_id} — removes items (destructive)
  - All GET endpoints remain public — reading inventory is safe
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from src.database import get_session
from src.models.inventory import ActiveInventory
from src.api.authenticated.schemas import (
    IngestionStatusResponse,
    InventoryItemResponse,
    InventoryListResponse,
    MessageResponse,
)

# THIS IS NEW — import the auth dependency and User model
from src.api.authenticated.auth import User, get_current_user

router = APIRouter()


# ==========================================================================
# GET /inventory — List active inventory items
# ==========================================================================
# 🔓 PUBLIC: Viewing your inventory is safe — it's just reading data.
# Like looking in your fridge, not taking anything out.

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
    List all active inventory items with optional filters.

    🔓 **Public** — no authentication required.
    """
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
# 🔓 PUBLIC: Checking expiration dates is safe — no data changes.

@router.get("/expiring", response_model=list[InventoryItemResponse])
def get_expiring_items(
    days: int = Query(
        default=7, ge=1, description="Show items expiring within this many days"
    ),
    session: Session = Depends(get_session),
):
    """
    Get inventory items expiring within the specified number of days.

    🔓 **Public** — no authentication required.
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
# 🔓 PUBLIC: Summary statistics are safe, read-only data.

@router.get("/summary")
def get_inventory_summary(session: Session = Depends(get_session)):
    """
    Get summary statistics about the current inventory.

    🔓 **Public** — no authentication required.
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
# POST /inventory/refresh — Rebuild the active inventory (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: This REPLACES the entire ActiveInventory table. It's a
# significant operation that drops and recreates data — only authenticated
# users should trigger it.

@router.post("/refresh", response_model=IngestionStatusResponse)
def refresh_inventory(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← THIS IS THE ONLY DIFFERENCE!
):
    """
    Rebuild the ActiveInventory table from receipt and pantry data.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
    """
    try:
        from src.normalization.build_inventory import build_active_inventory

        build_active_inventory()

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
# 🔓 PUBLIC: Viewing a single item is safe — just reading data.

@router.get("/{item_id}", response_model=InventoryItemResponse)
def get_inventory_item(item_id: int, session: Session = Depends(get_session)):
    """
    Get a single inventory item by its ID.

    🔓 **Public** — no authentication required.
    """
    item = session.get(ActiveInventory, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item with id {item_id} not found",
        )

    return InventoryItemResponse.model_validate(item)


# ==========================================================================
# DELETE /inventory/{item_id} — Remove an inventory item (PROTECTED)
# ==========================================================================
# 🔒 PROTECTED: DELETE is destructive — removing items from inventory changes
# what recipes you can make. Only authenticated users should do this.

@router.delete("/{item_id}", response_model=MessageResponse)
def delete_inventory_item(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← THIS IS THE ONLY DIFFERENCE!
):
    """
    Remove an item from active inventory.

    🔒 **Protected** — requires a valid JWT token in the Authorization header.
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
