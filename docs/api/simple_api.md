# WhatToEat Simple API — Documentation

## Overview

The WhatToEat API is a REST API built with FastAPI that provides access to your food inventory and recipe data. It lets you:

- Browse, create, update, and delete recipes
- View your current food inventory and expiration dates
- Find recipes you can make with ingredients you already have
- Trigger data ingestion from your receipt and pantry files

**No authentication is required** — this is a local development API designed for learning.

## Running the API

```bash
uv run uvicorn src.api.simple.main:app --reload --port 8000
```

Then open **http://localhost:8000/docs** for interactive Swagger documentation.

## Interactive Documentation

FastAPI automatically generates two documentation UIs:

- **Swagger UI** at `/docs` — Interactive explorer where you can try every endpoint
- **ReDoc** at `/redoc` — Alternative read-only documentation format

Both are generated from the endpoint definitions, schemas, and docstrings in the code.

## Endpoint Reference

### Root

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | Welcome message with links to docs |

### Recipes

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/recipes` | List all recipes (with optional filters) |
| GET | `/recipes/makeable` | Recipes you can make right now |
| GET | `/recipes/almost-makeable` | Recipes missing only a few ingredients |
| GET | `/recipes/with-substitutions` | Recipes with ingredient swap options |
| GET | `/recipes/{recipe_id}` | Get a single recipe by ID |
| POST | `/recipes` | Create a new recipe |
| PUT | `/recipes/{recipe_id}` | Update an existing recipe |
| DELETE | `/recipes/{recipe_id}` | Delete a recipe |

### Inventory

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/inventory` | List active inventory (with filters) |
| GET | `/inventory/expiring` | Items expiring soon |
| GET | `/inventory/summary` | Inventory statistics |
| GET | `/inventory/{item_id}` | Get a single inventory item |
| POST | `/inventory/refresh` | Rebuild active inventory from source data |
| DELETE | `/inventory/{item_id}` | Remove an inventory item |

### Matching

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/matching/summary` | Match summary for all recipes |
| GET | `/matching/recipe/{recipe_id}` | Ingredient-level match detail |
| GET | `/matching/shopping-list?recipe_ids=1,2,3` | Shopping list for selected recipes |
| POST | `/matching/refresh` | Rebuild recipe matching tables |

### Ingestion

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/ingest/recipes` | Ingest recipe files from data/recipes/ |
| POST | `/ingest/receipts` | Ingest receipt CSVs from data/receipts/ |
| POST | `/ingest/pantry` | Ingest pantry CSVs from data/pantry/ |
| POST | `/ingest/all` | Run the full pipeline (ingest → normalize → match) |

## HTTP Status Codes

| Code | Meaning | When You'll See It |
|------|---------|--------------------|
| **200 OK** | Success | Most GET/PUT/DELETE responses |
| **201 Created** | Resource created | POST /recipes (new recipe) |
| **404 Not Found** | Resource doesn't exist | GET /recipes/99999 |
| **422 Unprocessable Entity** | Invalid request data | Malformed JSON, wrong types |

## Example Requests

### List all recipes

```bash
curl http://localhost:8000/recipes
```

### Search recipes by name

```bash
curl "http://localhost:8000/recipes?search=cake"
```

### Get a single recipe

```bash
curl http://localhost:8000/recipes/1
```

### Create a new recipe

```bash
curl -X POST http://localhost:8000/recipes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Simple Pasta",
    "description": "Quick weeknight dinner",
    "ingredients": [
      {"name": "pasta", "quantity": 8, "unit": "oz", "category": "grain"},
      {"name": "olive oil", "quantity": 2, "unit": "tbsp", "category": "condiment"},
      {"name": "garlic", "quantity": 3, "unit": "cloves", "category": "vegetable"}
    ],
    "instructions": [
      "Boil pasta according to package directions",
      "Sauté garlic in olive oil",
      "Toss pasta with garlic oil"
    ],
    "servings": 2,
    "weather_temp": "warm"
  }'
```

### Update a recipe

```bash
curl -X PUT http://localhost:8000/recipes/1 \
  -H "Content-Type: application/json" \
  -d '{"servings": 4, "description": "Updated description"}'
```

### Delete a recipe

```bash
curl -X DELETE http://localhost:8000/recipes/1
```

### Get inventory (filtered by category)

```bash
curl "http://localhost:8000/inventory?category=dairy"
```

### Get items expiring within 3 days

```bash
curl "http://localhost:8000/inventory/expiring?days=3"
```

### Get a shopping list

```bash
curl "http://localhost:8000/matching/shopping-list?recipe_ids=1,2,3"
```

### Run the full ingestion pipeline

```bash
curl -X POST http://localhost:8000/ingest/all
```

## Testing with the Swagger UI

1. Open http://localhost:8000/docs in your browser
2. Click on any endpoint to expand it
3. Click **"Try it out"**
4. Fill in any parameters
5. Click **"Execute"**
6. See the response below, including status code, headers, and body

This is the easiest way to explore the API — no curl or code needed!
