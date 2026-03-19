# WhatToEat API (Authenticated) — Documentation

## Overview

The authenticated API is a secured version of the WhatToEat API that adds user registration, login, and JWT token-based access control. It runs on **port 8001** alongside the simple API on port 8000.

**Start the API:**
```bash
uv run uvicorn src.api.authenticated.main:app --reload --port 8001
```

**Interactive docs:** http://localhost:8001/docs

---

## Authentication Flow

```
                    ┌──────────────────────────────────────────────┐
                    │            AUTHENTICATION FLOW                │
                    └──────────────────────────────────────────────┘

    ┌─────────┐         ┌─────────┐         ┌──────────┐
    │ Register │ ──────> │  Login  │ ──────> │ Use Token│
    └─────────┘         └─────────┘         └──────────┘
         │                    │                    │
    Create account     Get JWT token      Send token with
    with username      (valid 30 min)     every request to
    and password                          protected endpoints
```

### Step 1: Register

Create an account with a username and password. The password is hashed with bcrypt before storage — the plain text is never saved.

```bash
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "learning123"}'
```

**Response (201 Created):**
```json
{
  "id": 1,
  "username": "student",
  "is_active": true,
  "created_at": "2025-01-15T10:30:00"
}
```

### Step 2: Login

Authenticate with your credentials to receive a JWT access token.

```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "learning123"}'
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Step 3: Use the Token

Include the token in the `Authorization` header for protected endpoints:

```bash
curl -X POST http://localhost:8001/recipes \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"name": "Toast", "ingredients": [...], "instructions": [...]}'
```

### Using the Swagger UI

1. Open http://localhost:8001/docs
2. Use **POST /auth/register** to create an account
3. Use **POST /auth/login** to get a token
4. Click the **"Authorize"** button (lock icon at the top)
5. Paste your `access_token` value and click "Authorize"
6. All protected endpoints will now include your token automatically

---

## Endpoint Reference

### Authentication Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | Public | Create a new user account |
| POST | `/auth/login` | Public | Login and get a JWT token |
| GET | `/auth/me` | Protected | Get current user info |

### Recipe Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/recipes` | Public | List all recipes (with filters) |
| GET | `/recipes/makeable` | Public | Recipes with all ingredients available |
| GET | `/recipes/almost-makeable` | Public | Recipes missing few ingredients |
| GET | `/recipes/with-substitutions` | Public | Recipes with substitute options |
| GET | `/recipes/{id}` | Public | Get a single recipe |
| POST | `/recipes` | **Protected** | Create a new recipe |
| PUT | `/recipes/{id}` | **Protected** | Update a recipe |
| DELETE | `/recipes/{id}` | **Protected** | Delete a recipe |

### Inventory Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/inventory` | Public | List inventory items (with filters) |
| GET | `/inventory/expiring` | Public | Items expiring within N days |
| GET | `/inventory/summary` | Public | Inventory statistics |
| GET | `/inventory/{id}` | Public | Get a single inventory item |
| POST | `/inventory/refresh` | **Protected** | Rebuild inventory from source data |
| DELETE | `/inventory/{id}` | **Protected** | Remove an inventory item |

### Matching Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/matching/summary` | Public | Match summary for all recipes |
| GET | `/matching/recipe/{id}` | Public | Ingredient-level match detail |
| GET | `/matching/shopping-list` | Public | Consolidated shopping list |
| POST | `/matching/refresh` | **Protected** | Rebuild matching tables |

### Ingestion Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/ingest/recipes` | **Protected** | Ingest recipe files |
| POST | `/ingest/receipts` | **Protected** | Ingest receipt files |
| POST | `/ingest/pantry` | **Protected** | Ingest pantry files |
| POST | `/ingest/all` | **Protected** | Run full ingestion pipeline |

---

## Common Auth Errors

### 401 Unauthorized — "Not authenticated"

**Cause:** You tried to access a protected endpoint without a token.

```bash
# This will fail — no token:
curl -X DELETE http://localhost:8001/recipes/1
```

**Fix:** Include the `Authorization: Bearer <token>` header.

### 401 Unauthorized — "Could not validate credentials"

**Cause:** Your token is expired (older than 30 minutes) or malformed.

**Fix:** Login again to get a fresh token:
```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "learning123"}'
```

### 401 Unauthorized — "Incorrect username or password"

**Cause:** Wrong username or password during login.

**Fix:** Check your credentials. If you haven't registered yet, do that first.

### 400 Bad Request — "Username already taken"

**Cause:** Someone already registered with that username.

**Fix:** Choose a different username, or login with the existing one.

### 422 Unprocessable Entity

**Cause:** Request body validation failed (e.g., password too short, missing fields).

**Fix:** Check the error details — they explain exactly what's wrong.

---

## Security Notes (Educational)

This API is designed for **learning**, not production use. Here's what a production API would add:

| Feature | This API | Production |
|---------|----------|------------|
| HTTPS | No (HTTP only) | Yes — encrypts all traffic |
| Secret key | Hardcoded in code | Environment variable, rotated regularly |
| Token refresh | No — login again after 30 min | Yes — refresh tokens extend sessions |
| Rate limiting | No | Yes — prevents brute-force attacks |
| Password requirements | Minimum 6 chars | Complexity rules, breach database checks |
| Account lockout | No | Yes — lock after N failed attempts |
| Token revocation | No | Yes — blacklist compromised tokens |
| Audit logging | No | Yes — log all auth events |

---

## Architecture

```
src/api/authenticated/
├── main.py          ← FastAPI app, CORS, router setup (like simple + auth router)
├── auth.py          ← User model, password hashing, JWT tokens, auth dependency
├── schemas.py       ← Re-exports simple schemas + adds auth schemas
└── routes/
    ├── auth.py      ← NEW: register, login, get-me endpoints
    ├── recipes.py   ← Same as simple + auth on POST/PUT/DELETE
    ├── inventory.py ← Same as simple + auth on POST/DELETE
    ├── matching.py  ← Same as simple + auth on POST
    └── ingestion.py ← Same as simple + auth on ALL endpoints
```

**Shared with the simple API:**
- Database models (`src/models/`)
- Database connection (`src/database.py`)
- SQLite database file (`db/whattoeat.db`)
- Ingestion and normalization pipelines (`src/ingestion/`, `src/normalization/`)
