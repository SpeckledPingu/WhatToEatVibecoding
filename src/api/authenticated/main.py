"""
main.py — The FastAPI application entry point for the AUTHENTICATED WhatToEat API.

# ==========================================================================
# DIFFERENCES FROM THE SIMPLE API (src/api/simple/main.py):
# ==========================================================================
# 1. User registration and login endpoints (/auth/register, /auth/login, /auth/me)
# 2. JWT token-based authentication (tokens issued at login, validated on requests)
# 3. Some endpoints require a valid token (POST, PUT, DELETE operations)
# 4. Password hashing with bcrypt (never store plain text passwords)
# 5. OAuth2 Bearer token scheme (Authorization: Bearer <token>)
# 6. User model/table added to the database for storing registered accounts
# 7. Auth router included with /auth prefix
# 8. Description updated to explain authentication features
# 9. Runs on port 8001 (not 8000) so both APIs can run simultaneously
#
# WHAT STAYED THE SAME:
# - All the same recipe, inventory, matching, and ingestion endpoints
# - Same CORS configuration
# - Same database (shared with the simple API)
# - Same data models (Recipe, Receipt, PantryItem, etc.)
# - Same response formats and schemas
# - The LOGIC of every endpoint is identical — only the access control changed
# ==========================================================================

HOW TO RUN THIS API:
    uv run uvicorn src.api.authenticated.main:app --reload --port 8001

Then open http://localhost:8001/docs in your browser!

You can run BOTH APIs simultaneously:
    Terminal 1: uv run uvicorn src.api.simple.main:app --reload --port 8000
    Terminal 2: uv run uvicorn src.api.authenticated.main:app --reload --port 8001

Then compare them side by side at:
    - Simple: http://localhost:8000/docs
    - Authenticated: http://localhost:8001/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import create_db_and_tables, get_engine

# Import route modules — same as simple API PLUS auth routes
from src.api.authenticated.routes import auth, recipes, inventory, matching, ingestion

# Import the User model so SQLModel registers it for table creation
from src.api.authenticated.auth import User  # noqa: F401

# ==========================================================================
# Create the FastAPI application
# ==========================================================================

app = FastAPI(
    title="WhatToEat API (Authenticated)",
    description=(
        "A secured REST API for managing your food inventory and finding recipes. "
        "This is the AUTHENTICATED version — it adds user registration, login, and "
        "JWT token-based access control on top of the same endpoints as the simple API. "
        "\n\n"
        "**What's different from the simple API?**\n"
        "- You can register an account and log in to get a JWT token\n"
        "- Read-only endpoints (GET) are still public — anyone can browse\n"
        "- Write endpoints (POST, PUT, DELETE) require a valid token\n"
        "- Click the 'Authorize' button above to enter your token\n"
        "\n"
        "**Quick start:**\n"
        "1. Register: POST /auth/register with a username and password\n"
        "2. Login: POST /auth/login to get your JWT token\n"
        "3. Authorize: Click the lock icon and paste your token\n"
        "4. Use protected endpoints freely until the token expires (30 min)"
    ),
    version="1.0.0",
)

# ==========================================================================
# CORS Middleware — same configuration as the simple API
# ==========================================================================
# See src/api/simple/main.py for detailed comments about what CORS is.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================================
# Include routers — same as simple API PLUS the auth router
# ==========================================================================
# The auth router is the ONLY new addition compared to the simple API.

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(recipes.router, prefix="/recipes", tags=["Recipes"])
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(matching.router, prefix="/matching", tags=["Matching"])
app.include_router(ingestion.router, prefix="/ingest", tags=["Ingestion"])


# ==========================================================================
# Startup event — ensure all database tables exist (including User table)
# ==========================================================================

@app.on_event("startup")
def on_startup():
    """Create database tables on server startup, including the User table."""
    engine = get_engine()
    create_db_and_tables(engine)


# ==========================================================================
# Root endpoint — welcome message (updated for authenticated API)
# ==========================================================================

@app.get("/", tags=["Root"])
def root():
    """
    Welcome to the Authenticated WhatToEat API!

    This root endpoint explains how to get started with authentication.
    """
    return {
        "message": "Welcome to the WhatToEat API (Authenticated)!",
        "docs": "/docs — Interactive API documentation (Swagger UI)",
        "redoc": "/redoc — Alternative documentation (ReDoc)",
        "getting_started": {
            "step_1": "POST /auth/register — Create an account",
            "step_2": "POST /auth/login — Get your JWT token",
            "step_3": "Use the token in the Authorization header: Bearer <token>",
        },
        "endpoints": {
            "/auth": "Register, login, and manage your account",
            "/recipes": "Browse, create, update, and delete recipes",
            "/inventory": "View your food inventory and expiration status",
            "/matching": "See which recipes match your current inventory",
            "/ingest": "Trigger data ingestion from files",
        },
        "note": "GET endpoints are public. POST/PUT/DELETE require authentication.",
    }
