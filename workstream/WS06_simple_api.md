# Workstream 06: Simple REST API (No Authentication)

Build a minimal FastAPI application that exposes the database through REST endpoints. This is the simplest possible API — no authentication, no complex middleware — to clearly teach the fundamentals of how web APIs work.

## Context

A REST API lets other programs (like our Streamlit frontend) interact with the database through HTTP requests. Instead of the frontend writing SQL queries directly, it sends HTTP requests to specific URLs (called **endpoints**), and the API handles the database operations.

**Why does this matter?** This is how every website and mobile app works. When you open Instagram, the app sends API requests to Instagram's servers. When you search on Google, your browser sends API requests. Learning to build and consume APIs is one of the most transferable skills in programming.

**HTTP Methods** (the verbs of the web):
- **GET** — Read/retrieve data (like browsing a menu)
- **POST** — Create new data (like placing an order)
- **PUT** — Update existing data (like modifying an order)
- **DELETE** — Remove data (like canceling an order)

## Instructions

1. **Create the simple API application** at `src/api/simple/main.py`:
   - Create a FastAPI application with:
     - Title: `"WhatToEat API"`
     - Description: A paragraph explaining what this API does, written for someone seeing an API for the first time
     - Version: `"1.0.0"`
   - Add CORS middleware configured for local development:
     - Allow all origins (`["*"]`) — add a comment explaining that this is fine for local development but would be restricted in production (and briefly explain what CORS is and why it exists)
   - Add a root endpoint `GET /` that returns a welcome message with links to the API docs (`/docs`) and a brief description of available endpoint groups
   - Include the routers from the route files (created below) using `app.include_router()`
   - Add educational comments explaining:
     - What FastAPI is and how it auto-generates documentation
     - What CORS is (Cross-Origin Resource Sharing — browser security)
     - How `include_router` organizes endpoints into groups
     - What "reload" mode means when running with uvicorn

2. **Create Pydantic schemas** at `src/api/simple/schemas.py`:
   - **Request models** (what the client sends):
     - `RecipeCreate` — fields needed to create a new recipe (name, ingredients, instructions, weather fields, etc.)
     - `RecipeUpdate` — fields that can be updated (all optional)
     - `IngredientInput` — structure for a single ingredient in recipe creation
   - **Response models** (what the API sends back):
     - `RecipeResponse` — full recipe data for API responses
     - `RecipeListResponse` — list of recipes with count
     - `InventoryItemResponse` — single inventory item
     - `InventoryListResponse` — list of inventory items with summary stats
     - `RecipeMatchResponse` — recipe matching summary for one recipe
     - `ShoppingListResponse` — consolidated shopping list
     - `IngestionStatusResponse` — result of running an ingestion operation
     - `MessageResponse` — simple message responses
   - Include `Field()` descriptions on every field — these appear in the auto-generated API docs
   - Educational comments explaining:
     - Why we use separate schemas for API input/output vs database models (separation of concerns, security — don't expose internal IDs in create requests)
     - What Pydantic validation does (automatic type checking and error messages)
     - How these schemas become the API documentation

3. **Create recipe endpoints** at `src/api/simple/routes/recipes.py`:
   - `GET /recipes` — List all recipes
     - Optional query parameters: `weather_temp`, `weather_condition`, `search` (name search)
     - Returns list of recipes matching filters
     - Comment: GET is for reading data, query params filter the results
   - `GET /recipes/{recipe_id}` — Get one recipe by ID
     - Returns 404 if not found
     - Comment: Path parameters identify a specific resource
   - `POST /recipes` — Create a new recipe
     - Accepts a RecipeCreate body
     - Returns 201 Created with the new recipe
     - Comment: POST creates new resources, 201 means "created successfully"
   - `PUT /recipes/{recipe_id}` — Update an existing recipe
     - Accepts a RecipeUpdate body (partial updates allowed)
     - Returns 404 if not found
     - Comment: PUT updates existing resources, only provided fields change
   - `DELETE /recipes/{recipe_id}` — Delete a recipe
     - Returns 404 if not found, 200 with confirmation if deleted
     - Comment: DELETE removes resources, this is destructive and cannot be undone
   - `GET /recipes/makeable` — Get recipes that can be made with current inventory
     - Returns recipes where `is_fully_makeable = True` from RecipeMatchSummary
   - `GET /recipes/almost-makeable` — Get recipes missing few ingredients
     - Query parameter: `max_missing` (default 2)
     - Returns recipes sorted by fewest missing ingredients
   - `GET /recipes/with-substitutions` — Get recipes where category substitutes exist
   - Each endpoint should have:
     - A detailed docstring (appears in Swagger docs)
     - Proper HTTP status codes with comments explaining each (200, 201, 404, 422)
     - Educational inline comments about REST conventions

4. **Create inventory endpoints** at `src/api/simple/routes/inventory.py`:
   - `GET /inventory` — List active inventory
     - Query params: `category`, `expiring_within_days` (filter to items expiring soon), `source`
   - `GET /inventory/{item_id}` — Get one inventory item
   - `GET /inventory/expiring` — Items expiring within 7 days (or configurable with query param)
   - `GET /inventory/summary` — Summary statistics: total items, by category, expired count
   - `POST /inventory/refresh` — Trigger a rebuild of the ActiveInventory table
     - Runs the `build_active_inventory()` function from WS04
     - Returns a status report
     - Comment: This is a POST because it CHANGES data (rebuilds the table), even though it doesn't take a body
   - `DELETE /inventory/{item_id}` — Remove an item from active inventory
   - Educational comments on each endpoint

5. **Create recipe matching endpoints** at `src/api/simple/routes/matching.py`:
   - `GET /matching/summary` — Full recipe match summary for all recipes
     - Returns all RecipeMatchSummary records
   - `GET /matching/recipe/{recipe_id}` — Ingredient-level match detail for one recipe
     - Returns all RecipeIngredientMatch records for that recipe
   - `GET /matching/shopping-list` — Generate a consolidated shopping list
     - Query param: `recipe_ids` (comma-separated list of recipe IDs)
     - Returns deduplicated list of missing ingredients for those recipes
   - `POST /matching/refresh` — Trigger a rebuild of recipe matching tables
     - Runs `build_recipe_matching()` from WS05
     - Returns a status report
   - Educational comments explaining how these endpoints expose the logic built in WS05

6. **Create ingestion endpoints** at `src/api/simple/routes/ingestion.py`:
   - `POST /ingest/recipes` — Trigger recipe ingestion from data files
     - Runs `ingest_recipes()` from WS02
     - Returns count of new/updated recipes
   - `POST /ingest/receipts` — Trigger receipt ingestion
     - Runs `ingest_receipts()` from WS03
   - `POST /ingest/pantry` — Trigger pantry ingestion
     - Runs `ingest_pantry()` from WS03
   - `POST /ingest/all` — Run the full pipeline in order:
     1. Ingest recipes
     2. Ingest receipts
     3. Ingest pantry
     4. Rebuild active inventory (normalize)
     5. Rebuild recipe matching
     - Returns a combined status report
   - Comment: All ingestion endpoints are POST because they modify the database

7. **Create `__init__.py` files** for the routes package and **wire up all routes** in `main.py`:
   - Use `app.include_router(router, prefix="/recipes", tags=["Recipes"])` pattern
   - Add educational comments explaining:
     - What a router is (a way to organize endpoints into groups)
     - What the `prefix` does (adds a URL prefix to all endpoints in the group)
     - What `tags` do (groups endpoints in the auto-generated docs)

8. **Test the API** by starting it and verifying key endpoints:
   ```bash
   uv run uvicorn src.api.simple.main:app --reload --port 8000
   ```
   - Test the root endpoint: `curl http://localhost:8000/`
   - Test listing recipes: `curl http://localhost:8000/recipes`
   - Test the auto-generated docs: open http://localhost:8000/docs in a browser
   - Print example curl commands for each endpoint type (GET, POST, PUT, DELETE)

9. **Create API documentation** at `docs/api/simple_api.md`:
   - Overview of the API and its purpose
   - Full endpoint reference table: Method, URL, Description, Auth Required
   - Example requests and responses for each endpoint group
   - How to use the auto-generated Swagger docs at `/docs`
   - Common HTTP status codes and what they mean in this API
   - How to test with curl, httpx, or the Swagger UI

## Things to Try After This Step

- Open http://localhost:8000/docs in your browser — this is auto-generated interactive API documentation. Click "Try it out" on any endpoint to test it live!
- Use curl to add a recipe: `curl -X POST http://localhost:8000/recipes -H "Content-Type: application/json" -d '{"name": "Test Recipe", "ingredients": [{"name": "test", "quantity": 1, "unit": "cup", "category": "other"}], "instructions": ["Step 1"]}'`
- Try requesting a recipe that doesn't exist (`/recipes/99999`) — observe the 404 response
- Run the full ingestion pipeline through the API: `curl -X POST http://localhost:8000/ingest/all`
- Notice there's NO authentication — anyone who can reach this API can delete all your recipes! We'll add auth in WS07
- Look at the response headers in curl (`curl -v ...`) — what HTTP headers does FastAPI send?
- Ask Claude Code: "Add an endpoint that returns the top 10 most common ingredients across all recipes"
- Try sending malformed JSON to a POST endpoint — observe how Pydantic validation catches it
