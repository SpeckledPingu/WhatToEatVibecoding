# Workstream 07: Authenticated REST API

Build a second FastAPI application that adds basic user authentication. By keeping both the simple API (WS06) and this authenticated API side by side, you can clearly see exactly what changes when you secure an API.

## Context

The simple API from WS06 has no authentication — anyone who can reach it can read, modify, or delete all data. In the real world, APIs need to verify:
1. **Authentication**: WHO is making the request? (Are you who you say you are?)
2. **Authorization**: WHAT are they allowed to do? (Are you permitted to do this?)

This workstream adds the simplest viable authentication:
- Users **register** with a username and password
- **Login** returns a JWT (JSON Web Token)
- **Protected endpoints** require that token in the request header
- Some endpoints are **public** (browsing recipes), others are **protected** (adding/deleting)

> **Important**: This is NOT production-grade security. It's designed to teach the CONCEPTS. Real applications need additional layers (HTTPS, token refresh, rate limiting, etc.).

## Instructions

1. **Create the authenticated API application** at `src/api/authenticated/main.py`:
   - A separate FastAPI app (runs on port 8001 alongside the simple API on 8000)
   - Title: `"WhatToEat API (Authenticated)"`
   - Description: Explain that this is the secured version and what's different
   - Version: `"1.0.0"`
   - Same CORS configuration as the simple API
   - Include a comment block at the top of the file that explicitly lists every difference from the simple API:
     ```python
     # DIFFERENCES FROM THE SIMPLE API (src/api/simple/main.py):
     # 1. User registration and login endpoints
     # 2. JWT token-based authentication
     # 3. Some endpoints require a valid token
     # 4. Password hashing (never store plain text passwords)
     # ...
     ```

2. **Create user model and auth utilities** at `src/api/authenticated/auth.py`:

   **User model:**
   - `User` SQLModel: `id`, `username` (unique), `hashed_password`, `is_active` (default True), `created_at`
   - Comment: Note that we store `hashed_password`, NEVER the plain text password

   **Password functions:**
   - `hash_password(password: str) -> str` — uses passlib bcrypt
   - `verify_password(plain_password: str, hashed_password: str) -> bool`
   - Comments explaining:
     - What hashing is (one-way transformation — you can verify but never reverse)
     - Why bcrypt specifically (slow by design, resistant to brute force)
     - Why plain text passwords are catastrophically dangerous

   **JWT Token functions:**
   - `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str`
     - Creates a JWT containing the user data and an expiration time
     - Uses a SECRET_KEY (hardcoded for educational purposes — comment that in production this comes from environment variables)
   - `decode_token(token: str) -> dict`
     - Validates and decodes a JWT, raises an error if expired or invalid
   - Comments explaining:
     - What a JWT is (a signed JSON object the server gives to the client to prove identity)
     - The three parts of a JWT: header, payload, signature
     - Why tokens expire (limits damage if a token is stolen)
     - What "stateless" authentication means (the server doesn't need to remember sessions)

   **Auth dependency:**
   - `get_current_user(token: str = Depends(oauth2_scheme)) -> User`
     - Extracts the token from the Authorization header
     - Decodes and validates it
     - Looks up the user in the database
     - Returns the User or raises 401 Unauthorized
   - Comments explaining:
     - What a dependency is in FastAPI (automatic injection of shared logic)
     - How `Depends()` works (FastAPI calls this function before your endpoint)
     - The Authorization header format: `Bearer <token>`

3. **Create auth schemas** at `src/api/authenticated/schemas.py`:
   - Copy the schemas from `src/api/simple/schemas.py` (reuse them)
   - Add auth-specific schemas:
     - `UserCreate` — username and password for registration
     - `UserLogin` — username and password for login
     - `UserResponse` — user info (WITHOUT password) for responses
     - `TokenResponse` — the JWT token and token type
   - Comments: Note that UserResponse deliberately excludes the password hash

4. **Create auth endpoints** at `src/api/authenticated/routes/auth.py`:
   - `POST /auth/register` — Create a new user account
     - Accepts username and password
     - Hashes the password
     - Stores the user
     - Returns 201 with user info (no password)
     - Returns 400 if username already taken
   - `POST /auth/login` — Authenticate and get a token
     - Accepts username and password
     - Verifies password against stored hash
     - Returns a JWT token if valid
     - Returns 401 if credentials are wrong
     - Comment: Login uses POST because it creates a new token (a resource), and because GET parameters would put the password in the URL (visible in logs!)
   - `GET /auth/me` — Get current user info (REQUIRES authentication)
     - Uses `Depends(get_current_user)` to require a valid token
     - Returns the authenticated user's info
     - This demonstrates the simplest protected endpoint

5. **Recreate ALL route files** from WS06 but with auth annotations, in `src/api/authenticated/routes/`:
   - Copy each route file from the simple API as a starting point
   - Add authentication requirements to appropriate endpoints:

   **Public endpoints** (NO token required — same as simple API):
   - `GET /recipes` — anyone can browse recipes
   - `GET /recipes/{id}` — anyone can view a recipe
   - `GET /recipes/makeable` — anyone can see what's makeable
   - `GET /recipes/almost-makeable` — anyone can see almost-makeable
   - `GET /recipes/with-substitutions` — anyone can see substitutions
   - `GET /inventory` — anyone can view inventory
   - `GET /inventory/expiring` — anyone can see expiring items
   - `GET /inventory/summary` — anyone can see summary
   - `GET /matching/summary` — anyone can see match results
   - `GET /matching/recipe/{id}` — anyone can see match details

   **Protected endpoints** (token REQUIRED — `current_user: User = Depends(get_current_user)`):
   - `POST /recipes` — only authenticated users can add recipes
   - `PUT /recipes/{id}` — only authenticated users can modify
   - `DELETE /recipes/{id}` — only authenticated users can delete
   - `POST /inventory/refresh` — only authenticated users can rebuild inventory
   - `DELETE /inventory/{id}` — only authenticated users can remove items
   - `POST /matching/refresh` — only authenticated users can rebuild matching
   - `POST /ingest/*` — all ingestion endpoints require authentication

   - On EVERY protected endpoint, add a comment explaining WHY it's protected (e.g., "DELETE is destructive — only authenticated users should be able to remove data")
   - On EVERY public endpoint, add a comment explaining WHY it's public (e.g., "Reading recipes is safe and non-destructive — no auth needed")
   - The ONLY code difference between a public and protected endpoint should be the `current_user` parameter — highlight this!

6. **Wire up all routes** in the authenticated `main.py` with clear tags and prefixes.

7. **Create a side-by-side comparison document** at `docs/api/auth_comparison.md`:
   - Show the SAME endpoint (e.g., POST /recipes) in both APIs:
     - Simple version: the function signature, the request, the response
     - Authenticated version: the function signature (with `Depends`), the request (with Authorization header), the response
   - Highlight what EXACTLY changed (it's surprisingly little code!)
   - Explain the request flow: Client → sends token in header → FastAPI calls `get_current_user` dependency → validates token → allows/denies the endpoint
   - Show example curl commands:
     ```bash
     # Simple API (no auth needed):
     curl -X POST http://localhost:8000/recipes -H "Content-Type: application/json" -d '{...}'

     # Authenticated API (need to login first):
     # Step 1: Register
     curl -X POST http://localhost:8001/auth/register -H "Content-Type: application/json" -d '{"username":"student","password":"learning123"}'
     # Step 2: Login and get token
     TOKEN=$(curl -s -X POST http://localhost:8001/auth/login -H "Content-Type: application/json" -d '{"username":"student","password":"learning123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
     # Step 3: Use token
     curl -X POST http://localhost:8001/recipes -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{...}'
     ```

8. **Test the authenticated API**:
   ```bash
   uv run uvicorn src.api.authenticated.main:app --reload --port 8001
   ```
   - Register a user, login, use the token
   - Try accessing a protected endpoint without a token (observe 401)
   - Try with an invalid token (observe 401)
   - Try with a valid token (observe success)
   - Print test curl commands for each scenario

9. **Create documentation** at `docs/api/authenticated_api.md`:
   - Everything from the simple API docs PLUS:
   - Authentication flow explanation with diagrams
   - How to register, login, and use tokens
   - Which endpoints are public vs protected and why
   - Common auth errors and what they mean

## Things to Try After This Step

- Start BOTH APIs simultaneously (`port 8000` and `port 8001`) and open both Swagger docs side by side in your browser
- Register a user, login, and use the token to add a recipe through the authenticated API
- Try accessing `POST /recipes` on the authenticated API WITHOUT a token — observe the 401 Unauthorized response
- Copy your JWT token and paste it into https://jwt.io — you can see the payload (username, expiration) without needing the secret key. This is by design — JWTs are signed, not encrypted
- Compare `src/api/simple/routes/recipes.py` and `src/api/authenticated/routes/recipes.py` side by side — count the lines that are different
- Think about: what would you need for ROLE-based access? (admin can delete, regular users can only add)
- Notice that login uses POST, not GET — WHY? (Because GET parameters appear in URLs, which show up in browser history and server logs)
- Ask Claude Code: "Add a /auth/change-password endpoint to the authenticated API"
- Think about what happens when a token expires — how would you handle token refresh?
