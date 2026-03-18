# WhatToEat - Educational Vibecoding Project

## Project Overview

An educational repository for learning vibecoding, data management, databases, APIs, and personal project development. Students build a food inventory and recipe recommendation application using Claude Code and a series of guided "Workstream" prompts.

## Tech Stack

- **Python 3.12+** managed with **uv**
- **SQLite** via **SQLModel** for database operations
- **FastAPI** + **Uvicorn** for REST APIs
- **Streamlit** for the web frontend
- **Pandas** for data analysis and manipulation
- **Jupyter Notebooks** for interactive exploration
- **Matplotlib** for visualizations

## Project Structure

```
├── data/                  # Input data files
│   ├── recipes/json/      # Recipe JSON files (one per recipe)
│   ├── recipes/markdown/  # Recipe full-text Markdown (paired with JSON by filename)
│   ├── receipts/          # Receipt CSV files
│   ├── pantry/            # Pantry inventory CSV files
│   └── synthetic/         # Generated synthetic data
├── config/                # JSON configuration files (normalization, mappings, rules)
├── prompts/               # AI extraction prompts for data collection
├── db/                    # SQLite database files (auto-generated)
├── src/                   # Application source code
│   ├── models/            # SQLModel data models
│   ├── ingestion/         # Data ingestion scripts
│   ├── normalization/     # Data cleaning & normalization
│   ├── analytics/         # Analysis scripts
│   ├── api/simple/        # Unsecured FastAPI application
│   ├── api/authenticated/ # Authenticated FastAPI application
│   ├── app/               # Streamlit application
│   └── synthetic/         # Synthetic data generation
├── notebooks/             # Jupyter notebooks for learning
├── docs/                  # Documentation and guides
│   ├── data_models/       # Data model documentation
│   ├── api/               # API documentation
│   └── guides/            # Learning guides
├── workstream/            # Sequential build prompts (WS01-WS11)
└── scripts/               # Utility scripts
```

## How to Use This Repository

### For Students

1. Install uv (see README.md for instructions)
2. Place your data files in the appropriate `data/` subdirectories
3. Open Claude Code in this project directory
4. Run each Workstream prompt (WS01 through WS11) in order by copying its contents into Claude Code
5. Review generated code, read the documentation, and try the "Things to Try" suggestions

### Workstream Prompts

The `workstream/` directory contains 11 sequential prompts that progressively build the application:

- **WS01**: Project setup and environment
- **WS02**: Recipe data ingestion
- **WS03**: Purchase and pantry data ingestion
- **WS04**: Data cleaning and normalization
- **WS05**: Recipe matching and inventory views
- **WS06**: Simple REST API
- **WS07**: Authenticated REST API
- **WS08**: Streamlit web application
- **WS09**: Analytics and Jupyter notebooks
- **WS10**: Synthetic data generation
- **WS11**: Weather integration and recommendations

Each prompt is designed to be re-run when new data is added.

## Development Guidelines

### Database

- Use SQLModel for all database models and operations
- SQLite database files live in `db/`; never edit them manually
- Use JSON fields in SQLModel where nested data structures appear (e.g., ingredient lists)
- All tables require primary keys; use foreign keys to express relationships
- Schemas are derived from actual data files, not defined abstractly
- Derived tables (like recipe matching results) are rebuilt on each ingestion

### Configuration Over Code

- **All normalization rules, mappings, and business logic parameters live in `config/normalization_mappings.json`**, not hardcoded in Python
- Python code reads the configuration file at runtime; students customize behavior by editing JSON, not code
- The configuration file should also be loaded into a SQL table (during WS04) to demonstrate data-driven joins and lookups
- Configuration covers: food name aliases, category mappings, abbreviations, qualifiers to strip, shelf life defaults, substitution rules, weather mappings, and city locations
- When a new normalization rule is needed, add it to the config file first — code should be generic, data should be specific

### Data Ingestion

- Recipe data: `data/recipes/json/` (structured JSON) and `data/recipes/markdown/` (full-text companion, paired by filename)
- JSON files are the primary structured data source; Markdown files store the full human-readable recipe text
- Receipt data: `data/receipts/` (CSV) — may include a `normalized_name` column from AI extraction prompts
- Pantry inventory: `data/pantry/` (CSV) — names should be pre-normalized using the extraction prompts in `prompts/`
- Always read and analyze actual data files before creating or modifying schemas
- Normalization functions read their rules from `config/normalization_mappings.json`, not hardcoded lists
- Create normalization scripts that build standardized join keys across sources
- Receipt and pantry schemas will differ; keep them in separate tables and normalize into a unified view

### Join Strategy

- Use a RIGHT JOIN between active inventory and recipe ingredients to detect missing ingredients
- Build a recipe matching table that is rebuilt on each ingestion (not a database view, but a rebuilt table to demonstrate the concept)
- Create additional views for: N-missing ingredients filtering, category-based fuzzy matching
- Document join logic thoroughly for educational purposes

### Expiration Tracking

- Each food item has an "inventoried date" and a shelf life (weeks)
- A reference table maps food items to their expected shelf life in weeks
- Active inventory = items where (inventoried_date + shelf_life_weeks) > today

### APIs

- Simple API (`src/api/simple/`): Minimal configuration, no authentication
- Authenticated API (`src/api/authenticated/`): Basic user authentication
- Use GET, POST, DELETE, and PUT operations as appropriate
- The Streamlit app must communicate through APIs, never directly to the database
- Educational comments explaining each endpoint's purpose and HTTP method choice

### Frontend (Streamlit)

- All data access goes through the REST APIs
- Sections: Recipe browser/adder, Inventory viewer, Recipe matcher, Data validation
- Include field validation that shows required vs. missing fields

### Code Style

- **Educational documentation is the top priority**
- Inline comments should teach concepts, not just describe code
- Docstrings explain "why" and "how", not just "what"
- Keep external dependencies minimal
- Prefer clarity and readability over clever or compact code

### Analytics

- Use pandas for all data manipulation in analytics scripts
- Matplotlib for visualizations
- Jupyter notebooks should be self-contained learning exercises
- Include explanatory markdown cells in notebooks
- Analytics scripts should print informative output about what they find

### Package Management

- Use `uv` for all Python package management
- Run scripts: `uv run python -m src.module_name` or `uv run python scripts/script.py`
- Add packages: `uv add package_name`
- API server (simple): `uv run uvicorn src.api.simple.main:app --reload --port 8000`
- API server (auth): `uv run uvicorn src.api.authenticated.main:app --reload --port 8001`
- Streamlit: `uv run streamlit run src/app/main.py`
- Jupyter: `uv run jupyter notebook`

### Testing

- This is an educational project; formal test suites are not required
- Scripts should include sanity checks and print validation output
- Ingestion scripts should report row counts and any data quality issues found
