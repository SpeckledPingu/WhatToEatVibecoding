"""
database.py — Centralized database connection management for the WhatToEat application.

WHY ONE FILE?
We put all database connection logic in a single file so that every part of the
application (ingestion scripts, API endpoints, analytics) connects to the same
database in the same way. If we ever need to change the database location or
settings, we only change this one file instead of hunting through the entire codebase.
"""

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# ---------------------------------------------------------------------------
# Database file path
# ---------------------------------------------------------------------------
# We store the SQLite database in the db/ directory at the project root.
# Path(__file__).parent.parent resolves to the project root (one level up from src/).
DB_DIR = Path(__file__).parent.parent / "db"
DB_PATH = DB_DIR / "whattoeat.db"

# The SQLite connection string follows the format: sqlite:///path/to/file.db
# The three slashes are part of the SQLAlchemy URL scheme; the path after them
# is the file location on disk.
DATABASE_URL = f"sqlite:///{DB_PATH}"


def get_engine():
    """
    Create and return a SQLModel/SQLAlchemy Engine.

    WHAT IS AN ENGINE?
    An engine is the connection manager between your Python code and the SQLite
    database file on disk. Think of it like a phone line — it doesn't make calls
    by itself, but every call (query) goes through it. The engine handles:
      - Opening and closing connections to the database file
      - Connection pooling (reusing connections for efficiency)
      - Translating Python/SQLModel operations into SQL statements

    WHY echo=False?
    Setting echo=True would print every SQL statement to the console, which is
    great for debugging but noisy in normal use. Flip it to True when you want
    to see exactly what SQL is being run behind the scenes.
    """
    # Ensure the db/ directory exists before SQLite tries to create the file
    DB_DIR.mkdir(parents=True, exist_ok=True)

    return create_engine(DATABASE_URL, echo=False)


def create_db_and_tables(engine):
    """
    Create all database tables that have been defined as SQLModel classes.

    WHAT DOES create_all DO?
    SQLModel.metadata keeps a registry of every table class you've defined
    (any class that inherits from SQLModel with table=True). Calling create_all
    tells the engine: "Look at every registered table model. If a table with
    that name doesn't exist in the database yet, create it. If it already
    exists, leave it alone."

    This is safe to call repeatedly — it will never delete or overwrite existing
    tables or data. It only adds what's missing.
    """
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Yield a SQLModel Session for database operations.

    WHAT IS A SESSION?
    A session is like a conversation with the database. During a session you can:
      - Read data (SELECT queries)
      - Add new rows (INSERT)
      - Update existing rows (UPDATE)
      - Delete rows (DELETE)

    The session keeps track of all your changes and sends them to the database
    together when you commit. If something goes wrong, it can roll everything back
    so the database stays consistent.

    WHY A GENERATOR (yield)?
    Using "yield" makes this a generator function, which is exactly what FastAPI
    expects for a "dependency". FastAPI will:
      1. Call this function to get a session (the "yield" hands it over)
      2. Use the session to handle the API request
      3. Automatically close the session when the request is done
    This pattern ensures sessions are always properly closed, even if an error occurs.
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session
