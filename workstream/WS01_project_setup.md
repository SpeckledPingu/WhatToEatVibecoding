# Workstream 01: Project Setup & Environment

Set up this project's Python environment and install all necessary dependencies. This is the foundation for everything that follows.

## Instructions

1. **Verify uv is installed** by running `uv --version`. If it's not installed, tell me and provide installation instructions for my operating system.

2. **Initialize the Python environment** using the existing `pyproject.toml`. Run `uv sync` to create the virtual environment.

3. **Install the required dependencies** using `uv add`:
   - `fastapi` — REST API framework for building web APIs
   - `uvicorn[standard]` — ASGI server to run the FastAPI application
   - `sqlmodel` — Combines SQLAlchemy (database toolkit) and Pydantic (data validation) for Python database models
   - `streamlit` — Framework for building interactive web applications in pure Python
   - `pandas` — Data analysis and manipulation library
   - `jupyter` — Interactive notebook environment for data exploration
   - `matplotlib` — Data visualization and charting library
   - `httpx` — Modern HTTP client (used by Streamlit to call the REST APIs)
   - `python-multipart` — Handles form data and file uploads in FastAPI
   - `passlib[bcrypt]` — Password hashing library for the authenticated API
   - `python-jose[cryptography]` — JWT (JSON Web Token) creation and validation for authentication

4. **Verify the folder structure** exists as described in CLAUDE.md. Create any missing directories:
   ```
   data/recipes/json/
   data/recipes/markdown/
   data/receipts/
   data/pantry/
   data/synthetic/receipts/
   data/synthetic/pantry/
   db/
   src/models/
   src/ingestion/
   src/normalization/
   src/analytics/
   src/api/simple/routes/
   src/api/authenticated/routes/
   src/app/pages/
   src/synthetic/
   notebooks/
   docs/data_models/
   docs/api/
   docs/guides/
   scripts/
   ```

5. **Create `__init__.py` files** in `src/` and every subdirectory under `src/` so Python can import modules from them. These can be empty files, but add a brief comment in each one explaining what that package contains.

6. **Create `src/database.py`** with:
   - A function `get_engine()` that creates and returns a SQLModel engine pointing to `db/whattoeat.db`
   - A function `create_db_and_tables(engine)` that calls `SQLModel.metadata.create_all(engine)`
   - A function `get_session()` that yields a SQLModel Session (for use as a FastAPI dependency later)
   - Include educational comments explaining:
     - What a database engine is (the connection manager between Python and SQLite)
     - Why we centralize the database connection in one file
     - What a session is (a conversation with the database)
     - What `create_all` does (creates tables that don't exist yet, leaves existing ones alone)

7. **Verify everything works** by running:
   ```python
   from sqlmodel import SQLModel
   import fastapi
   import streamlit
   import pandas
   print("All dependencies installed successfully!")
   ```

8. **Update the `pyproject.toml`** description to: "Educational vibecoding project: food inventory and recipe recommendation app"

## Things to Try After This Step

- Run `uv run python -c "import sqlmodel; print(sqlmodel.__version__)"` to see your SQLModel version
- Run `uv run python -c "import fastapi; print(fastapi.__version__)"` to see your FastAPI version
- Explore the project directories with `ls` — they're mostly empty but organized for what's coming
- Open `CLAUDE.md` and read through it to understand the project conventions
- Try `uv run jupyter notebook` to open Jupyter and confirm it works (you can close it after)
- Look at `docs/guides/terminal_basics.md` if you're new to using the terminal
- Look at `docs/guides/data_formats.md` to understand what data you'll need to provide
- Try creating a simple test: `uv run python -c "from src.database import get_engine; print(get_engine())"` — this should show the engine object pointing to your database file
