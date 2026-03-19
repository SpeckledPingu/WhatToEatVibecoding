"""
auth.py — User model, password hashing, JWT tokens, and authentication dependency.

THIS IS THE HEART OF AUTHENTICATION
This file contains everything that makes the authenticated API different from
the simple API. Every other file in the authenticated API is nearly identical
to its simple counterpart — the difference is just a few lines that call the
functions defined here.

OVERVIEW OF WHAT'S IN THIS FILE:
  1. User model — the database table that stores registered users
  2. Password hashing — turning plain text passwords into safe, irreversible hashes
  3. JWT token creation — generating signed tokens that prove who you are
  4. JWT token decoding — verifying tokens are valid and extracting user info
  5. Auth dependency — a FastAPI function that protects endpoints by requiring a token

CONCEPTS YOU'LL LEARN:
  - Why we NEVER store plain text passwords (and what we store instead)
  - What a JWT is and how it works
  - What "stateless" authentication means
  - How FastAPI dependencies automate repeated logic
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt
import jwt
from jwt.exceptions import PyJWTError
from sqlmodel import Field, Session, SQLModel, select

from src.database import get_session


# ==========================================================================
# SECRET KEY AND ALGORITHM
# ==========================================================================
# The SECRET_KEY is used to SIGN JWT tokens. It's like a stamp that proves
# the token was issued by THIS server (and not forged by someone else).
#
# ⚠️ EDUCATIONAL ONLY: In a real application, NEVER put secrets in your code!
# Instead, use environment variables:
#     import os
#     SECRET_KEY = os.environ["JWT_SECRET_KEY"]
#
# If this key leaks, anyone can forge valid tokens and impersonate any user.

SECRET_KEY = "whattoeat-educational-secret-key-change-in-production"
ALGORITHM = "HS256"  # HMAC-SHA256 — a common, secure signing algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Tokens expire after 30 minutes


# ==========================================================================
# OAuth2 Password Bearer scheme
# ==========================================================================
# This tells FastAPI how clients will send their authentication token.
# OAuth2PasswordBearer means:
#   - The client sends a token in the HTTP header: Authorization: Bearer <token>
#   - The "tokenUrl" tells the Swagger docs where to get a token (the login endpoint)
#
# FastAPI uses this to:
#   1. Show a "lock" icon on protected endpoints in /docs
#   2. Add an "Authorize" button to the Swagger UI
#   3. Automatically extract the token from the Authorization header

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ==========================================================================
# User Model — the database table for registered users
# ==========================================================================
# This SQLModel class creates a "user" table in the database.
#
# CRITICAL SECURITY NOTE:
# We store hashed_password, NEVER the plain text password. If someone steals
# the database, they get hashes — not passwords. Hashes are one-way: you can
# check "does this password match this hash?" but you can't reverse the hash
# back into the password.

class User(SQLModel, table=True):
    """
    A registered user of the WhatToEat API.

    Stores the username and a HASHED version of their password.
    The plain text password is never stored anywhere — not in the database,
    not in logs, not in memory longer than necessary.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, description="Unique username")
    hashed_password: str = Field(description="Bcrypt hash of the password — NEVER the plain text")
    is_active: bool = Field(default=True, description="Whether this account is active")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this user registered",
    )


# ==========================================================================
# Password Hashing — one-way transformation for safe storage
# ==========================================================================
# WHAT IS HASHING?
# Hashing is a ONE-WAY transformation. Given a password, you can compute its
# hash — but given a hash, you CANNOT compute the original password. It's like
# putting a document through a shredder: you can verify "this is the same
# document" by shredding a copy and comparing the confetti, but you can't
# un-shred the confetti back into a readable document.
#
# WHY BCRYPT?
# Not all hash functions are equal for passwords. MD5 and SHA-256 are FAST,
# which is BAD for passwords — an attacker can try billions of guesses per
# second. Bcrypt is intentionally SLOW (and configurable), making brute-force
# attacks impractical. It also includes a random "salt" so that two users with
# the same password get different hashes.
#
# WHY NOT PLAIN TEXT?
# If you store passwords in plain text, a single database breach exposes
# every user's password. Since people reuse passwords across sites, one
# breach could compromise their email, banking, and social media accounts.
# This is why storing plain text passwords is considered a catastrophic
# security failure — it's not just bad practice, it's negligent.

def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    The result is a string like "$2b$12$LJ3m4y..." that includes:
      - The algorithm identifier ($2b$ = bcrypt)
      - The cost factor ($12$ = 2^12 = 4096 iterations)
      - A random salt (unique per hash)
      - The hash itself

    This is what gets stored in the database. The original password
    is not recoverable from this hash.
    """
    # bcrypt.hashpw expects bytes, so we encode the password string to UTF-8.
    # bcrypt.gensalt() creates a random salt — this means hashing the same
    # password twice gives different results (which is a security feature).
    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Check if a plain text password matches a stored hash.

    Bcrypt extracts the salt from the stored hash, re-hashes the plain
    password with the same salt, and compares the results. If they match,
    the password is correct — without ever storing the plain password.

    Returns True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ==========================================================================
# JWT Token Functions — creating and validating identity tokens
# ==========================================================================
# WHAT IS A JWT (JSON Web Token)?
# A JWT is a small, signed piece of data that the server gives to the client
# after successful login. The client then sends it back with every request
# to prove who they are — like a concert wristband that proves you paid.
#
# A JWT HAS THREE PARTS (separated by dots):
#   1. Header — says which algorithm was used to sign it (e.g., HS256)
#   2. Payload — the actual data (username, expiration time, etc.)
#   3. Signature — a hash of header+payload using our SECRET_KEY
#
# Example: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzdHVkZW50In0.abc123signature
#          [    header    ]  [     payload      ]  [ signature ]
#
# IMPORTANT: The payload is NOT encrypted — anyone can decode it and read
# the username and expiration. The signature just proves it wasn't tampered
# with. Never put secrets (passwords, SSNs) in a JWT!
#
# WHY TOKENS EXPIRE
# If someone steals a token (from a log file, network sniffing, etc.), they
# can impersonate that user. Expiration limits the damage window — a stolen
# token only works for 30 minutes, not forever.
#
# WHAT "STATELESS" MEANS
# The server doesn't need to remember active sessions in a database.
# Everything needed to verify identity is IN the token itself. This means:
#   - No session table to manage
#   - Easy to scale across multiple servers
#   - But: you can't easily "revoke" a token before it expires
#   (For revocation, you'd need a token blacklist — beyond our scope here)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a new JWT access token.

    Args:
        data: The payload data to encode (typically {"sub": username}).
              "sub" (subject) is a standard JWT claim meaning "who this token is for."
        expires_delta: How long until the token expires. Defaults to 30 minutes.

    Returns:
        A signed JWT string that the client will send in the Authorization header.
    """
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # "exp" is a standard JWT claim — the token library automatically rejects
    # tokens where the current time is past the "exp" value
    to_encode.update({"exp": expire})

    # jwt.encode creates the three-part token: header.payload.signature
    # The SECRET_KEY is used to create the signature — only our server can
    # create valid signatures, so clients can't forge tokens
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    This function:
      1. Splits the token into header, payload, and signature
      2. Verifies the signature using our SECRET_KEY (was it issued by us?)
      3. Checks the expiration time (has it expired?)
      4. Returns the payload data if everything is valid

    Raises HTTPException (401 Unauthorized) if the token is invalid or expired.
    """
    try:
        # jwt.decode handles signature verification AND expiration checking
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        # PyJWTError covers: invalid signature, expired token, malformed token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials — token is invalid or expired",
            # This header tells the client "you need to authenticate using Bearer token"
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==========================================================================
# Authentication Dependency — the "gatekeeper" for protected endpoints
# ==========================================================================
# WHAT IS A FASTAPI DEPENDENCY?
# A dependency is a function that FastAPI calls BEFORE your endpoint runs.
# It's like a security guard at a door — the guard checks your ID before
# letting you into the building. If the check fails, you never reach the
# endpoint; you get a 401 error instead.
#
# HOW Depends() WORKS
# When you write: current_user: User = Depends(get_current_user)
# FastAPI automatically:
#   1. Looks at the Authorization header for "Bearer <token>"
#   2. Passes the token to get_current_user()
#   3. get_current_user() validates the token and looks up the user
#   4. If valid, injects the User object into your endpoint function
#   5. If invalid, returns 401 BEFORE your endpoint code runs
#
# THE AUTHORIZATION HEADER FORMAT
# Clients send tokens like this:
#   Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIi...
# The word "Bearer" is the authentication scheme — it means "I'm bearing
# (carrying) a token that proves my identity."


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """
    FastAPI dependency that extracts and validates the user from a JWT token.

    This function is the single point of authentication for all protected
    endpoints. Adding `current_user: User = Depends(get_current_user)` to
    any endpoint function signature makes that endpoint require a valid token.

    Flow:
      1. oauth2_scheme extracts the token from the Authorization header
      2. decode_token validates the signature and checks expiration
      3. We look up the username in the database
      4. If everything checks out, return the User object
      5. If anything fails, raise 401 Unauthorized

    Returns:
        The authenticated User object (database record).

    Raises:
        HTTPException (401): If the token is missing, invalid, expired,
        or the user doesn't exist in the database.
    """
    # Step 1: Decode and validate the token
    payload = decode_token(token)

    # Step 2: Extract the username from the token payload
    # "sub" (subject) is the standard JWT claim we set during login
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing the 'sub' (subject) claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 3: Look up the user in the database
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User '{username}' not found — account may have been deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 4: Check if the account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account has been deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
