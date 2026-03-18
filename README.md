# WhatToEat: A Vibecoding Tutorial for Data, APIs, and Personal Projects

Welcome! This repository is an educational guide that teaches you how to build a real application using **vibecoding** — the practice of building software by describing what you want to an AI coding assistant and iterating on the results.

You'll build a **food inventory and recipe recommendation app** that:

- Ingests recipes from JSON and Markdown files
- Tracks pantry inventory and store purchases from CSV data
- Stores everything in a SQLite database
- Serves data through REST APIs (with and without authentication)
- Presents an interactive web interface with Streamlit
- Recommends recipes based on what you have on hand
- Tracks expiration dates to reduce food waste
- Suggests recipes based on current weather conditions

Along the way, you'll learn about:

- **Data ingestion** — loading structured and semi-structured data
- **Data cleaning** — normalizing messy real-world data so it can be combined
- **Databases** — relational tables, primary/foreign keys, joins, and JSON fields
- **APIs** — RESTful design, HTTP methods, and basic authentication
- **Web apps** — building interactive frontends that talk to APIs
- **Analytics** — exploring data with pandas and Jupyter notebooks
- **Synthetic data** — generating realistic test data for experimentation

---

## Prerequisites

- A computer running macOS, Linux, or Windows (with WSL)
- A terminal application (Terminal on Mac, or your preferred terminal)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and configured
- Basic familiarity with using a terminal (see `docs/guides/terminal_basics.md`)

---

## Getting Started

### Step 1: Install uv (Python Package Manager)

**uv** is a fast Python package manager that replaces pip, virtualenv, and more.

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, **restart your terminal** and verify:

```bash
uv --version
```

> **What is uv?** It's a tool that manages Python versions and packages for your project. Think of it like an app store for Python libraries. When you run `uv add pandas`, it downloads the pandas library and records it as a project dependency. When you run `uv run python script.py`, it makes sure all dependencies are available before running your script.

### Step 2: Clone This Repository

```bash
git clone <repository-url>
cd WhatToEatVibecoding
```

### Step 3: Add Your Data

Place your data files in the appropriate directories:

| Data Type | Directory | Format | Example |
|-----------|-----------|--------|---------|
| Recipes | `data/recipes/json/` | One JSON file per recipe | `chicken_soup.json` |
| Recipes | `data/recipes/markdown/` | One Markdown file per recipe | `chicken_soup.md` |
| Receipts | `data/receipts/` | CSV files of store purchases | `trader_joes_2024_03.csv` |
| Pantry | `data/pantry/` | CSV files of pantry inventory | `pantry_march_2024.csv` |

See `docs/guides/data_formats.md` for detailed format descriptions with full examples.

**Where does this data come from?**

We've created standardized AI extraction prompts in the `prompts/` directory to make data collection easy and consistent:

- **Recipes**: Use `prompts/recipe_extraction.md` with a browser-connected AI to extract recipes from any webpage into JSON. Optionally save the full recipe text as a paired Markdown file, or paste it in the Streamlit app.
- **Receipts**: Use `prompts/receipt_extraction.md` — photograph your receipt, send it to an AI with this prompt, and get a CSV with both raw and pre-normalized item names.
- **Pantry**: Use `prompts/pantry_extraction.md` — photograph your fridge/pantry, send it to an AI with this prompt, and get a CSV with normalized names and categories.

These prompts normalize data **at the point of extraction**, which makes the automated cleanup pipeline more accurate. You can also create data files manually — see `docs/guides/data_formats.md` for the expected formats.

### Step 4: Run the Workstream Prompts

Open Claude Code in this directory:

```bash
claude
```

Then run each Workstream prompt in order (WS01 through WS11). You can do this by:

1. Opening the workstream file (e.g., `workstream/WS01_project_setup.md`)
2. Copying the entire contents
3. Pasting it into Claude Code as your prompt

Each workstream builds on the previous one. After each step, **review the generated code** and try the "Things to Try" suggestions to deepen your learning.

| Workstream | What It Builds |
|-----------|----------------|
| **WS01** | Project setup, dependencies, environment |
| **WS02** | Recipe ingestion (JSON + Markdown into database) |
| **WS03** | Receipt and pantry ingestion (CSV into database) |
| **WS04** | Data cleaning, normalization, unified inventory |
| **WS05** | Recipe matching, expiration tracking, views |
| **WS06** | Simple REST API (no authentication) |
| **WS07** | Authenticated REST API |
| **WS08** | Streamlit web application |
| **WS09** | Analytics scripts and Jupyter notebooks |
| **WS10** | Synthetic data generation |
| **WS11** | Weather API integration and recommendations |

### Step 5: Run the Application

After completing the workstream prompts:

```bash
# Start the simple API server (terminal 1)
uv run uvicorn src.api.simple.main:app --reload --port 8000

# Start the authenticated API server (terminal 2)
uv run uvicorn src.api.authenticated.main:app --reload --port 8001

# Start the Streamlit web app (terminal 3)
uv run streamlit run src/app/main.py

# Launch Jupyter notebooks (terminal 4)
uv run jupyter notebook
```

> **Tip:** You'll need multiple terminal windows or tabs open simultaneously. The API servers need to be running for the Streamlit app to work. See `docs/guides/terminal_basics.md` for how to manage multiple terminals.

---

## Project Structure

```
WhatToEatVibecoding/
├── CLAUDE.md              # Claude Code project rules and conventions
├── README.md              # This file
├── pyproject.toml         # Python project config and dependencies
├── .gitignore             # Files git should ignore
│
├── data/                  # YOUR DATA GOES HERE
│   ├── recipes/
│   │   ├── json/          # Recipe JSON files (structured data, one per recipe)
│   │   └── markdown/      # Recipe full-text Markdown (paired with JSON by filename)
│   ├── receipts/          # Store receipt CSVs
│   ├── pantry/            # Pantry inventory CSVs
│   └── synthetic/         # Generated synthetic data
│
├── config/                # Configuration files (normalization rules, mappings)
├── prompts/               # AI extraction prompts for data collection
├── db/                    # SQLite databases (auto-generated by workstreams)
│
├── src/                   # Application source code (built by workstreams)
│   ├── models/            # Database table definitions (SQLModel)
│   ├── ingestion/         # Scripts that load data files into the database
│   ├── normalization/     # Scripts that clean and standardize data
│   ├── analytics/         # Analysis and reporting scripts
│   ├── api/
│   │   ├── simple/        # FastAPI app without authentication
│   │   └── authenticated/ # FastAPI app with authentication
│   ├── app/               # Streamlit web application
│   └── synthetic/         # Synthetic data generation scripts
│
├── notebooks/             # Jupyter notebooks for interactive analysis
│
├── docs/                  # Documentation and learning guides
│   ├── data_models/       # Database table documentation
│   ├── api/               # API endpoint documentation
│   └── guides/            # Getting started guides
│
├── workstream/            # The sequential build prompts (WS01-WS11)
└── scripts/               # Utility scripts
```

---

## Key Concepts You'll Learn

### Data Ingestion

Raw data comes in many formats. You'll parse JSON, Markdown, and CSV files and load them into structured database tables. This is the first step in any data pipeline.

### Data Normalization

Real-world data is messy. A store receipt says "Organic Whole Milk 1gal" while your pantry scan says "milk." You'll build normalization scripts that create standardized **join keys** so data from different sources can be combined — one of the most important skills in working with data. Normalization rules live in `config/normalization_mappings.json`, not hardcoded in Python, so you can customize them without touching code.

### Configuration Over Code

Business rules (food name aliases, category mappings, shelf life data, substitution rules) live in JSON configuration files, not Python constants. This means you can customize the system's behavior by editing `config/normalization_mappings.json` — a skill that transfers to many real-world data systems. These configuration files can also be loaded into SQL tables, demonstrating data-driven joins and lookups.

### Relational Databases

SQLite is a database that lives in a single file — no server setup needed. You'll learn about tables, primary keys, foreign keys, JSON fields for nested data, and different types of JOINs. The RIGHT JOIN used for finding missing recipe ingredients is a particularly powerful technique.

### REST APIs

APIs are how different parts of an application communicate. You'll build FastAPI endpoints that handle GET (read), POST (create), PUT (update), and DELETE (remove) operations — the same patterns used by every website and app you use daily.

### Authentication

You'll build two versions of the same API: one open, one secured. Comparing them side-by-side demystifies authentication — you'll see exactly what code changes when you add user login, password hashing, and JWT tokens.

### Web Applications

Streamlit turns Python scripts into web apps. Your app talks to the APIs (not the database directly), showing **separation of concerns** — the same architecture pattern used by professional applications.

### Analytics

Pandas and Jupyter notebooks are the tools data scientists use every day. You'll explore your own food data, create visualizations, and learn patterns you can apply to any dataset.

### Synthetic Data

Real data takes time to accumulate. You'll build scripts that generate realistic fake receipt and pantry data, letting you experiment with analytics that need weeks or months of history.

---

## Troubleshooting

**"uv: command not found"**
Restart your terminal after installing uv. If it still doesn't work, add `~/.local/bin` to your PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**"Module not found"**
Make sure you're using `uv run` before your Python commands. This activates the virtual environment with all dependencies.

**"Connection refused" in Streamlit**
The API server needs to be running in another terminal before you start Streamlit.

**"Database is locked"**
SQLite allows only one writer at a time. Make sure you're not running two ingestion scripts simultaneously.

**"No data files found"**
Make sure your data files are in the correct directories under `data/`. Check `docs/guides/data_formats.md` for the expected formats.

---

## Extending the Project

After completing all workstreams, here are ideas for continuing your learning:

- **Nutrition tracking**: Add nutritional data to ingredients and calculate per-recipe nutrition
- **Meal planning**: Generate a weekly meal plan that minimizes waste and maximizes variety
- **Price tracking**: Analyze spending trends over time across different stores
- **Raspberry Pi deployment**: Run the app on a Raspberry Pi on your home network
- **Recipe scraping**: Build a browser extension that extracts recipes from websites
- **Multi-user**: Extend the authenticated API to support household members with shared inventory
- **Mobile-friendly**: Make the Streamlit app work well on phone browsers
- **Shopping list**: Auto-generate shopping lists based on planned meals

---

## Creating Your Own Project

Want to build a project like this for a different domain? See **`CREATE_PROJECT.md`** — it contains a step-by-step guide and a prompt template for generating your own vibecoding project scaffold from scratch. The same approach that built WhatToEat (detailed description → CLAUDE.md + workstream prompts → data-driven build) works for any personal project idea.

## License

This project is for educational purposes. Feel free to use, modify, and share.
