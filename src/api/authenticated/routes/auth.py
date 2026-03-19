"""
auth.py — Authentication endpoints: register, login, and get current user.

THESE ENDPOINTS ARE NEW — they don't exist in the simple API.
They handle user account management and token issuance:
  - POST /auth/register — create a new user account
  - POST /auth/login — authenticate and receive a JWT token
  - GET /auth/me — get the current user's info (requires a valid token)

AUTHENTICATION FLOW (the full picture):
  1. Client registers: POST /auth/register with username + password
  2. Server hashes the password and stores the user
  3. Client logs in: POST /auth/login with username + password
  4. Server verifies the password, creates a JWT token, returns it
  5. Client stores the token (in memory, localStorage, etc.)
  6. Client includes token in every request: Authorization: Bearer <token>
  7. Server validates the token before allowing access to protected endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.database import get_session
from src.api.authenticated.auth import (
    User,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from src.api.authenticated.schemas import (
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

router = APIRouter()


# ==========================================================================
# POST /auth/register — Create a new user account
# ==========================================================================
# Registration is the first step. The user provides a username and password,
# we hash the password and store the account. After this, they can log in.

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_data: UserCreate, session: Session = Depends(get_session)):
    """
    Create a new user account.

    Accepts a username and password. The password is immediately hashed
    using bcrypt — the plain text password is never stored.

    **HTTP 201 Created** — account was created successfully.
    **HTTP 400 Bad Request** — username is already taken.
    **HTTP 422 Unprocessable Entity** — validation failed (e.g., password too short).
    """
    # Check if the username is already taken
    existing = session.exec(
        select(User).where(User.username == user_data.username)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_data.username}' is already taken",
        )

    # Create the user with a HASHED password — never store plain text!
    user = User(
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return UserResponse.model_validate(user)


# ==========================================================================
# POST /auth/login — Authenticate and get a JWT token
# ==========================================================================
# WHY POST AND NOT GET?
# Login uses POST (not GET) for two important reasons:
#   1. POST creates a new resource (a token) — this fits REST semantics
#   2. GET parameters appear in the URL: GET /auth/login?password=secret123
#      URLs show up in browser history, server logs, proxy logs, and
#      network monitoring tools. Putting passwords in URLs is a security disaster.
#      POST sends data in the request BODY, which is not logged in URLs.

@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, session: Session = Depends(get_session)):
    """
    Authenticate with username and password to receive a JWT access token.

    The token should be included in the Authorization header of subsequent
    requests to protected endpoints:

        Authorization: Bearer <your_token_here>

    **HTTP 200 OK** — login successful, token returned.
    **HTTP 401 Unauthorized** — wrong username or password.
    """
    # Look up the user by username
    user = session.exec(
        select(User).where(User.username == login_data.username)
    ).first()

    # SECURITY: Give the same error for "user not found" and "wrong password"
    # If we said "user not found" vs "wrong password" separately, an attacker
    # could enumerate valid usernames. A generic message prevents this.
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create a JWT token with the username as the "subject" claim
    # The token is self-contained — the server doesn't need to store it
    access_token = create_access_token(data={"sub": user.username})

    return TokenResponse(access_token=access_token, token_type="bearer")


# ==========================================================================
# GET /auth/me — Get current user info (PROTECTED)
# ==========================================================================
# This is the simplest possible protected endpoint. It demonstrates how
# adding a single parameter — `current_user: User = Depends(get_current_user)` —
# makes an endpoint require authentication.
#
# 🔒 PROTECTED: Requires a valid JWT token in the Authorization header.
# Without a token, FastAPI returns 401 before this function even runs.

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user's information.

    This endpoint requires a valid JWT token. It's a simple way to verify
    that your token is working — if you get back your user info, you're
    authenticated. If you get a 401 error, your token is missing, expired,
    or invalid.

    **HTTP 200 OK** — returns your user info.
    **HTTP 401 Unauthorized** — token is missing, invalid, or expired.
    """
    return UserResponse.model_validate(current_user)
