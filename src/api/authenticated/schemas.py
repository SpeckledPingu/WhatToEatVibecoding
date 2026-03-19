"""
schemas.py — Pydantic models for the authenticated API.

This file REUSES all schemas from the simple API (they handle the same data)
and adds a few new schemas specific to authentication:
  - UserCreate — registration request
  - UserLogin — login request
  - UserResponse — user info in responses (deliberately EXCLUDES the password hash)
  - TokenResponse — the JWT token returned after successful login

WHY UserResponse EXCLUDES THE PASSWORD HASH
Even though the hash can't be reversed into a password, exposing it:
  1. Gives attackers a target to brute-force offline (without hitting your server)
  2. Reveals which hashing algorithm you use
  3. Is simply unnecessary — the client never needs it
Never expose more data than the client actually needs.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Re-export ALL schemas from the simple API — they're identical for both APIs
# ---------------------------------------------------------------------------
# The data schemas (RecipeCreate, RecipeResponse, InventoryItemResponse, etc.)
# are the same whether or not authentication is involved. Authentication only
# controls WHO can call the endpoint, not WHAT data the endpoint handles.

from src.api.simple.schemas import (  # noqa: F401
    IngredientInput,
    IngredientMatchResponse,
    IngestionStatusResponse,
    InventoryItemResponse,
    InventoryListResponse,
    MessageResponse,
    RecipeCreate,
    RecipeListResponse,
    RecipeMatchResponse,
    RecipeResponse,
    RecipeUpdate,
    ShoppingListItem,
    ShoppingListResponse,
)


# ==========================================================================
# AUTHENTICATION SCHEMAS — new models for user registration and login
# ==========================================================================


class UserCreate(BaseModel):
    """
    Request body for user registration (POST /auth/register).

    Only requires a username and password. The server handles everything
    else: assigning an ID, hashing the password, setting created_at, etc.
    """

    username: str = Field(
        ..., min_length=3, max_length=50,
        description="Unique username (3-50 characters)"
    )
    password: str = Field(
        ..., min_length=6,
        description="Password (minimum 6 characters). Will be hashed before storage — never stored in plain text"
    )


class UserLogin(BaseModel):
    """
    Request body for login (POST /auth/login).

    Identical fields to UserCreate, but semantically different:
    UserCreate means "I'm new, create my account."
    UserLogin means "I already have an account, verify my identity."
    """

    username: str = Field(..., description="Your registered username")
    password: str = Field(..., description="Your password")


class UserResponse(BaseModel):
    """
    User information returned in API responses.

    IMPORTANT: This model deliberately EXCLUDES hashed_password.
    We never send password data (even hashed) back to the client.
    Compare this to the User database model which HAS hashed_password —
    the database stores it, but the API never exposes it.
    """

    id: int = Field(description="Unique user ID")
    username: str = Field(description="Username")
    is_active: bool = Field(description="Whether the account is active")
    created_at: Optional[datetime] = Field(description="Registration timestamp")

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    Response from the login endpoint.

    Contains the JWT access token and its type. The client should store
    this token and include it in the Authorization header of subsequent
    requests to protected endpoints:

        Authorization: Bearer <access_token>
    """

    access_token: str = Field(description="JWT access token — include this in the Authorization header")
    token_type: str = Field(default="bearer", description="Token type — always 'bearer' for this API")
