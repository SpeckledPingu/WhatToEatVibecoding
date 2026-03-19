"""
main.py — The FastAPI application entry point for the WhatToEat API.

WHAT IS FASTAPI?
FastAPI is a modern Python web framework for building APIs. It's called "Fast"
for two reasons:
  1. Performance: It's built on top of Starlette and Pydantic, which are very fast
  2. Development speed: It auto-generates interactive docs, validates inputs
     automatically, and requires minimal boilerplate code

When you run this application, FastAPI:
  - Starts an HTTP server that listens for requests
  - Routes each request to the right endpoint function based on the URL and method
  - Validates request data using the Pydantic schemas we defined
  - Returns JSON responses with proper HTTP status codes
  - Auto-generates interactive API documentation at /docs (Swagger UI)

HOW TO RUN THIS API:
    uv run uvicorn src.api.simple.main:app --reload --port 8000

  - `src.api.simple.main:app` tells uvicorn WHERE the FastAPI app object is
  - `--reload` means uvicorn watches for code changes and restarts automatically
    (great for development — you edit code and the API updates instantly)
  - `--port 8000` sets the port number (the API will be at http://localhost:8000)

Then open http://localhost:8000/docs in your browser to see the interactive docs!
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import create_db_and_tables, get_engine
from src.api.simple.routes import recipes, inventory, matching, ingestion, weather

# ==========================================================================
# Create the FastAPI application
# ==========================================================================
# This is the main application object. FastAPI uses the title, description,
# and version to generate the interactive documentation at /docs.

app = FastAPI(
    title="WhatToEat API",
    description=(
        "A REST API for managing your food inventory and finding recipes you can cook. "
        "This API lets you browse recipes, check what's in your kitchen, find out which "
        "recipes you can make with ingredients you already have, and trigger data ingestion "
        "from your receipt and pantry files. If you're new to APIs, visit /docs for an "
        "interactive explorer where you can try every endpoint directly in your browser."
    ),
    version="1.0.0",
)

# ==========================================================================
# CORS Middleware
# ==========================================================================
# WHAT IS CORS? (Cross-Origin Resource Sharing)
# When a web page at one address (e.g., http://localhost:8501 — our Streamlit app)
# tries to make a request to a DIFFERENT address (e.g., http://localhost:8000 — this API),
# the browser blocks it by default. This is a SECURITY feature called the
# "Same-Origin Policy" — it prevents malicious websites from secretly making
# requests to other sites using your logged-in session.
#
# CORS is the mechanism that lets a server say "it's OK, I trust requests from
# these specific origins." By adding CORS middleware, we tell browsers:
# "Allow requests from these origins to reach my API."
#
# allow_origins=["*"] means "allow requests from ANY origin." This is fine for
# LOCAL development, but in production you'd restrict this to your actual frontend
# domain (e.g., allow_origins=["https://myapp.com"]) so that random websites
# can't access your API through users' browsers.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins — OK for local dev, restrict in production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # Allow all headers
)

# ==========================================================================
# Include routers — organize endpoints into logical groups
# ==========================================================================
# WHAT IS A ROUTER?
# A router is like a chapter in a book — it groups related endpoints together.
# Instead of putting every endpoint in this one file, we split them into
# separate files by topic (recipes, inventory, etc.).
#
# WHAT DOES prefix DO?
# The prefix adds a URL path to every endpoint in that router. So if the
# recipes router has a GET "" endpoint, it becomes GET /recipes. If it has
# GET /{recipe_id}, it becomes GET /recipes/{recipe_id}.
#
# WHAT DO tags DO?
# Tags group endpoints together in the auto-generated documentation at /docs.
# All recipe endpoints appear under the "Recipes" section, inventory endpoints
# under "Inventory", etc. This makes the docs easier to browse.

app.include_router(recipes.router, prefix="/recipes", tags=["Recipes"])
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(matching.router, prefix="/matching", tags=["Matching"])
app.include_router(ingestion.router, prefix="/ingest", tags=["Ingestion"])
app.include_router(weather.router, prefix="/weather", tags=["Weather"])


# ==========================================================================
# Startup event — ensure database tables exist
# ==========================================================================
# This runs once when the server starts. It creates any missing database
# tables so the API is ready to handle requests immediately.

@app.on_event("startup")
def on_startup():
    """Create database tables on server startup if they don't exist."""
    engine = get_engine()
    create_db_and_tables(engine)


# ==========================================================================
# Root endpoint — welcome message
# ==========================================================================

@app.get("/", tags=["Root"])
def root():
    """
    Welcome to the WhatToEat API!

    This root endpoint provides links to the API documentation and a summary
    of available endpoint groups.
    """
    return {
        "message": "Welcome to the WhatToEat API!",
        "docs": "/docs — Interactive API documentation (Swagger UI)",
        "redoc": "/redoc — Alternative documentation (ReDoc)",
        "endpoints": {
            "/recipes": "Browse, create, update, and delete recipes",
            "/inventory": "View your food inventory and expiration status",
            "/matching": "See which recipes match your current inventory",
            "/ingest": "Trigger data ingestion from files",
            "/weather": "Current weather and weather-based recipe recommendations",
        },
    }
