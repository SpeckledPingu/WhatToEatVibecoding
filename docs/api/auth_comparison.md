# Authentication Comparison: Simple API vs Authenticated API

This document shows the **exact differences** between the simple and authenticated APIs. The key takeaway: **adding authentication requires surprisingly little code change**.

## Side-by-Side: POST /recipes (Create a Recipe)

### Simple API Version

```python
# src/api/simple/routes/recipes.py

@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe_data: RecipeCreate,
    session: Session = Depends(get_session),
):
    # ... endpoint logic ...
```

**Request:**
```bash
curl -X POST http://localhost:8000/recipes \
  -H "Content-Type: application/json" \
  -d '{"name": "Toast", "ingredients": [{"name": "bread", "quantity": 2, "unit": "slices", "category": "grain"}], "instructions": ["Toast the bread"]}'
```

### Authenticated API Version

```python
# src/api/authenticated/routes/recipes.py

@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe_data: RecipeCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # ← THIS IS THE ONLY DIFFERENCE!
):
    # ... endpoint logic is EXACTLY the same ...
```

**Request (requires a token):**
```bash
curl -X POST http://localhost:8001/recipes \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -d '{"name": "Toast", "ingredients": [{"name": "bread", "quantity": 2, "unit": "slices", "category": "grain"}], "instructions": ["Toast the bread"]}'
```

### What Changed?

| Aspect | Simple API | Authenticated API |
|--------|-----------|-------------------|
| Function parameters | `recipe_data`, `session` | `recipe_data`, `session`, **`current_user`** |
| Request headers | `Content-Type` only | `Content-Type` + **`Authorization: Bearer <token>`** |
| Endpoint logic | Unchanged | **Unchanged** |
| Response format | Same | **Same** |

**That's it.** One extra parameter. One extra header. The endpoint logic is identical.

---

## How the Authentication Flow Works

```
Client                                 Server
  |                                      |
  |  POST /auth/register                 |
  |  {"username":"student",              |
  |   "password":"learning123"}          |
  |  ─────────────────────────────────>  |
  |                                      |  Hash password with bcrypt
  |                                      |  Store user in database
  |  <─────────────────────────────────  |
  |  201 Created                         |
  |  {"id":1, "username":"student"}      |
  |                                      |
  |  POST /auth/login                    |
  |  {"username":"student",              |
  |   "password":"learning123"}          |
  |  ─────────────────────────────────>  |
  |                                      |  Verify password against hash
  |                                      |  Create JWT token
  |  <─────────────────────────────────  |
  |  200 OK                              |
  |  {"access_token":"eyJhbG...",        |
  |   "token_type":"bearer"}             |
  |                                      |
  |  POST /recipes                       |
  |  Authorization: Bearer eyJhbG...     |
  |  {"name":"Toast", ...}               |
  |  ─────────────────────────────────>  |
  |                                      |  Extract token from header
  |                                      |  Decode & validate JWT
  |                                      |  Look up user in database
  |                                      |  ✅ User is valid → allow
  |  <─────────────────────────────────  |
  |  201 Created                         |
  |  {"id":5, "name":"Toast", ...}       |
  |                                      |
  |  POST /recipes (no token!)           |
  |  {"name":"Toast", ...}               |
  |  ─────────────────────────────────>  |
  |                                      |  No Authorization header
  |                                      |  ❌ 401 Unauthorized
  |  <─────────────────────────────────  |
  |  401 Unauthorized                    |
  |  {"detail":"Not authenticated"}      |
```

---

## Example curl Commands

### Simple API (no auth needed)

```bash
# List recipes — works immediately
curl http://localhost:8000/recipes

# Create a recipe — works immediately (no auth!)
curl -X POST http://localhost:8000/recipes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Simple Toast",
    "ingredients": [{"name": "bread", "quantity": 2, "unit": "slices", "category": "grain"}],
    "instructions": ["Put bread in toaster", "Wait until golden"]
  }'

# Delete a recipe — works immediately (no auth!)
curl -X DELETE http://localhost:8000/recipes/1
```

### Authenticated API (need to login first)

```bash
# Step 1: Register a user account
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"learning123"}'

# Step 2: Login and save the token
TOKEN=$(curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"learning123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Your token: $TOKEN"

# Step 3: Use the token for protected endpoints
# List recipes — still works without a token (public endpoint)
curl http://localhost:8001/recipes

# Create a recipe — REQUIRES the token
curl -X POST http://localhost:8001/recipes \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Auth Toast",
    "ingredients": [{"name": "bread", "quantity": 2, "unit": "slices", "category": "grain"}],
    "instructions": ["Put bread in toaster", "Wait until golden"]
  }'

# Delete a recipe — REQUIRES the token
curl -X DELETE http://localhost:8001/recipes/1 \
  -H "Authorization: Bearer $TOKEN"

# Try WITHOUT a token — observe the 401 error:
curl -X POST http://localhost:8001/recipes \
  -H "Content-Type: application/json" \
  -d '{"name": "Unauthorized Toast", "ingredients": [{"name": "bread", "quantity": 1, "unit": "slice", "category": "grain"}], "instructions": ["Fail"]}'
# Response: {"detail":"Not authenticated"}
```

---

## Public vs Protected Endpoints

| Endpoint | Method | Simple API | Authenticated API | Why? |
|----------|--------|-----------|-------------------|------|
| `/recipes` | GET | Open | **Public** | Reading is safe |
| `/recipes/{id}` | GET | Open | **Public** | Reading is safe |
| `/recipes/makeable` | GET | Open | **Public** | Reading is safe |
| `/recipes/almost-makeable` | GET | Open | **Public** | Reading is safe |
| `/recipes/with-substitutions` | GET | Open | **Public** | Reading is safe |
| `/recipes` | POST | Open | **Protected** | Creates data |
| `/recipes/{id}` | PUT | Open | **Protected** | Modifies data |
| `/recipes/{id}` | DELETE | Open | **Protected** | Destroys data |
| `/inventory` | GET | Open | **Public** | Reading is safe |
| `/inventory/expiring` | GET | Open | **Public** | Reading is safe |
| `/inventory/summary` | GET | Open | **Public** | Reading is safe |
| `/inventory/{id}` | GET | Open | **Public** | Reading is safe |
| `/inventory/refresh` | POST | Open | **Protected** | Rebuilds table |
| `/inventory/{id}` | DELETE | Open | **Protected** | Destroys data |
| `/matching/summary` | GET | Open | **Public** | Reading is safe |
| `/matching/recipe/{id}` | GET | Open | **Public** | Reading is safe |
| `/matching/shopping-list` | GET | Open | **Public** | Reading is safe |
| `/matching/refresh` | POST | Open | **Protected** | Rebuilds tables |
| `/ingest/recipes` | POST | Open | **Protected** | Bulk data load |
| `/ingest/receipts` | POST | Open | **Protected** | Bulk data load |
| `/ingest/pantry` | POST | Open | **Protected** | Bulk data load |
| `/ingest/all` | POST | Open | **Protected** | Full pipeline |
| `/auth/register` | POST | N/A | **Public** | Need to create accounts |
| `/auth/login` | POST | N/A | **Public** | Need to get tokens |
| `/auth/me` | GET | N/A | **Protected** | Proves authentication |

**Pattern:** GET = public, POST/PUT/DELETE = protected (except register and login).

---

## Key Concepts Recap

### What is a JWT?
A JSON Web Token is a signed, self-contained piece of data. After login, the server creates a JWT containing your username and an expiration time, signs it with a secret key, and returns it. You send it back with every request to prove your identity.

### What does "stateless" mean?
The server doesn't store sessions. Everything needed to verify your identity is in the token itself. No session table, no server-side memory — just decode the token and check the signature.

### Why do tokens expire?
If someone steals your token, they can impersonate you. Expiration limits the damage window — a stolen token stops working after 30 minutes.

### Why bcrypt for passwords?
Bcrypt is intentionally slow, making brute-force attacks impractical. Fast algorithms like MD5 let attackers try billions of passwords per second. Bcrypt's slowness is a feature, not a bug.
