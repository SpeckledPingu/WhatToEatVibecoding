# Create Your Own Project

This file is a guide and template for creating your own vibecoding project from scratch, using the same approach that built this WhatToEat application. The method — writing a detailed project description and using a series of Workstream prompts to build it out with an AI coding assistant — can be applied to any personal project idea.

---

## How This Project Was Created

The WhatToEat project started with a single, detailed prompt given to Claude Code. That prompt described:

1. What the application should do
2. What data sources it would use and where they come from
3. How data should be stored, cleaned, and processed
4. What technologies to use
5. What the outputs should be (CLAUDE.md, README, workstream prompts, folder structure, config files, extraction prompts)

Claude Code then generated the entire project scaffold: folder structure, documentation, configuration files, standardized AI extraction prompts, and 11 workstream prompts. Running those workstream prompts in order — each time with the student's actual data — built out the complete application.

**You can do the same thing for your own project idea.**

---

## Step 1: Choose Your Project Idea

Pick a project that:

- **Uses data you can actually get** — photos you can take, files you can export, APIs that are free to access
- **Solves a real problem you have** — personal projects are far more motivating when they're useful to you
- **Combines 2-3 different data sources** — this teaches data integration, the most valuable and transferable skill
- **Can run locally** — no deployment complexity to deal with while learning (a Raspberry Pi on your home network is a great target)

### Example Project Ideas

| Project | Data Sources | What It Does |
|---------|-------------|--------------|
| **Book Library Tracker** | Goodreads export CSV, photos of bookshelves (AI extraction), manual entries | Track your book collection, get reading recommendations based on genres, visualize reading habits |
| **Workout Logger** | Apple Health/Google Fit export, gym app CSV, manual workout notes | Track exercises, analyze progress over time, suggest routines based on what equipment you have |
| **Plant Care Manager** | Photos of plants (AI identification), watering schedule CSV, weather API | Track plant health, remind you to water, adjust watering for weather and seasons |
| **Budget Analyzer** | Bank statement CSVs, receipt photos (AI extraction), manual subscription list | Categorize spending, find trends, set and track budgets, compare stores |
| **Music Collection** | Spotify/Last.fm export, vinyl collection photos, concert ticket history | Catalog your music, find listening patterns, discover connections between artists |
| **Travel Planner** | Flight price API, hotel booking CSV, destination research notes (JSON) | Compare trip options, track price changes, plan itineraries with budget constraints |
| **Home Maintenance Log** | Photos of appliances/systems, maintenance schedule CSV, weather data | Track when things were last serviced, predict maintenance needs, log repairs |
| **Pet Health Tracker** | Vet visit records, food purchase receipts, daily observation notes | Track pet health over time, monitor food costs, log medications and symptoms |

---

## Step 2: Write Your Project Initialization Prompt

Copy the template below, replace everything in `[BRACKETS]` with your details, and give it to Claude Code. This single prompt will generate your entire project scaffold.

### Prompt Template

```
I am creating a [TYPE: e.g., "personal project", "tutorial", "learning exercise"]
for [PURPOSE: e.g., "tracking my book collection and getting reading recommendations"].

I need help creating:
1. A CLAUDE.md file with project rules and conventions
2. A README.md that describes the project and how to set it up
3. A set of sequential Workstream prompts that build the application step by step
4. A folder structure for data, code, documentation, and configuration
5. Configuration files (JSON) for data mappings, normalization rules, and
   business logic — NOT hardcoded in Python
6. Standardized AI extraction prompts in a prompts/ directory that users can
   give to AI tools (browser plugins, Claude, ChatGPT) to extract data from
   their sources into the expected formats
7. A .gitignore file appropriate for the project

The Workstream prompts are meant to be used over and over again. They contain
instructions for how to read supplied data and create the database tables and
Python code necessary. That means schemas must be created when those workstream
prompts are run based on the actual data provided, rather than defining schemas
abstractly ahead of time.

---

## The Application

[DESCRIBE YOUR APP IN 2-4 SENTENCES:
- What does it do?
- Who is it for?
- What problem does it solve?]

---

## Data Sources

This application will use [NUMBER] different data sources:

### Data Source 1: [NAME]
- **Format**: [JSON / CSV / API response / photos / etc.]
- **Location**: [where it comes from — a website, a photo, an app export, etc.]
- **What it contains**: [describe the fields/information]
- **How it's obtained**: [manual entry, AI extraction from photos, API call,
  file download, browser plugin, etc.]
- **Expected volume**: [how many files/records, how often new data arrives]

### Data Source 2: [NAME]
- [same structure as above]

### Data Source 3: [NAME, if applicable]
- [same structure]

Note: These data sources will NOT have matching schemas. They describe similar
things from different perspectives and will need normalization to be combined.
The Workstream prompts should handle this alignment when they are run, based on
the actual data provided.

---

## Data Storage

The data will be stored in SQLite using SQLModel. The database should:
- [Describe the main tables and their purpose]
- [Describe key relationships between tables]
- [Describe any derived/computed tables that get rebuilt]
- [Describe any join requirements across data sources]
- Use JSON fields where nested data appears in a relational table
- Have primary keys and foreign keys
- Have data model documentation generated after the models are built

---

## Data Processing

The data needs the following processing:

### Normalization
- [Describe how different data sources need to be aligned]
- [Describe what "join keys" are needed to connect data across sources]
- [Describe what cleaning operations are needed and why]

### Derived Data
- [Describe any computed fields, scores, or rankings]
- [Describe any tables that get rebuilt from source data]
- [Describe any external data enrichment (APIs, lookups)]

### Configuration Over Code
All normalization rules, mappings, and business logic parameters should be stored
in JSON configuration files in a config/ directory — NOT hardcoded in Python.
The Python code should READ these configuration files. The configuration files
should also be loadable into SQL tables for demonstrating data-driven joins and
lookups. This means students can customize behavior by editing JSON files without
touching Python code.

Configuration files should include:
- [Name/alias mappings for your domain]
- [Category definitions and assignments]
- [Any threshold values, scoring weights, or business rules]
- [External API settings (URLs, thresholds, mappings)]
- [Synthetic data generation parameters]

---

## APIs

The application should have REST APIs using FastAPI:

### Simple API (no authentication)
- [List the main endpoint groups: e.g., "recipes CRUD", "inventory queries"]
- [Describe what operations each group supports]
- [This demonstrates the basics of REST APIs]

### Authenticated API
- [Same endpoints but with basic JWT authentication]
- [Describe which endpoints should be public vs. protected and why]
- [This demonstrates what changes when you add security]

The APIs should use a mix of GET, POST, PUT, and DELETE operations.
Documentation that educates is paramount — comments should explain HTTP methods,
status codes, and REST conventions.

---

## Web Application

The web application will be built with Streamlit and should have these sections:

- [PAGE 1: What it shows, what users can do]
- [PAGE 2: What it shows, what users can do]
- [PAGE 3: What it shows, what users can do]
- [DASHBOARD: Summary metrics and charts]

The Streamlit app must communicate with the database ONLY through the REST APIs,
never directly. This demonstrates separation of concerns.

Include data validation in any forms — show required vs. missing fields.

---

## Analytics

The project should include:
- Analytics scripts using pandas for [what analyses]
- Jupyter notebooks for interactive exploration of [what data]
- Visualizations using matplotlib showing [what charts/insights]
- Each notebook should have markdown cells explaining concepts and end with
  "exercises to try" for further learning

---

## Additional Features

- **Synthetic data generation**: Scripts that generate realistic test data for
  [your domain] so users can experiment with analytics without needing [weeks/
  months] of real data. Generation parameters should be in config files.
- **External API integration**: [Which API, what it adds, how it enriches the data]
- [Any other features specific to your project]

---

## AI Extraction Prompts

Create standardized prompts in a prompts/ directory that users can give to AI
tools (browser plugins, Claude, ChatGPT) to extract data from their sources:

- [Prompt 1: For extracting DATA TYPE from SOURCE — e.g., "extracting book info
  from a Goodreads page"]
- [Prompt 2: For extracting DATA TYPE from SOURCE — e.g., "extracting items from
  a receipt photo"]
- [Prompt 3: For extracting DATA TYPE from SOURCE — e.g., "identifying plants
  from a photo of a shelf"]

Each prompt should:
- Specify the exact output format (JSON or CSV matching the expected schema)
- Include normalization rules so the AI cleans data at the point of extraction
- Include the category system used by the project
- Be copy-pasteable directly into an AI assistant

---

## Technical Stack

- Python managed with uv
- SQLite via SQLModel for the database
- FastAPI + Uvicorn for REST APIs
- Streamlit for the web frontend
- Pandas for data analysis
- Jupyter notebooks for interactive exploration
- Matplotlib for visualizations
- Dependencies should be minimal — only what's needed

---

## Workstream Design Requirements

The Workstream prompts should:
- Be sequential (each builds on the previous)
- Be re-runnable (safe to execute again when new data is added)
- Be data-driven (read actual data files to determine schemas — do NOT define
  schemas abstractly in the prompts)
- Include "Things to Try" suggestions after each step for further learning
- Create educational documentation alongside code
- Reference configuration files (config/) for all business rules, mappings, and
  thresholds — Python code reads config, it does not hardcode these values
- Create analysis scripts that both validate data quality AND teach analytics
  techniques

---

## Educational Philosophy

This is a learning project. Code should be:
- Readable over clever
- Well-documented with educational comments explaining "why" not just "what"
- Structured to demonstrate concepts progressively
- Accompanied by suggestions for experimentation and extension
- Using configuration files that students can edit without touching code
```

---

## Step 3: Review What Was Generated

After Claude Code generates your project scaffold, check:

1. **CLAUDE.md** — Does it accurately capture your project's rules and conventions?
2. **README.md** — Would a brand new person understand how to get started?
3. **Folder structure** — Does it organize data, code, config, and docs logically?
4. **Workstream prompts** — Do they build in a logical order? Do they reference config files instead of hardcoding rules?
5. **Config files** — Do the mappings make sense for your domain?
6. **Extraction prompts** — Will they produce data in the right format?
7. **Data format docs** — Are the expected formats clearly documented with examples?

Adjust anything that doesn't fit. The scaffold is a starting point — refine it before running the workstreams.

---

## Step 4: Add Your Data and Run the Workstreams

1. Put your data files in the appropriate directories
2. Run WS01 to set up the environment and install dependencies
3. Run each subsequent workstream in order
4. After each workstream, review the generated code and try the "Things to Try" suggestions
5. Ask Claude Code to modify or extend anything that doesn't work for your specific data
6. Edit the config files to refine normalization rules based on what you observe

---

## Tips for Writing Good Project Prompts

### Be Specific About Your Data

Bad:
> "The app will use some book data"

Good:
> "Book data comes from Goodreads CSV exports with columns: Title, Author, ISBN, My Rating, Date Read, Shelves. It also comes from photos of bookshelves where an AI extracts title and author. These two sources use different title formats ('The Great Gatsby' vs 'GREAT GATSBY, THE') and need normalization."

### Describe the Relationships Between Data Sources

Bad:
> "The data needs to be combined"

Good:
> "Goodreads exports use ISBN as a unique identifier, but photos don't capture ISBNs. A normalization pipeline should create join keys from normalized title + author combinations so books from both sources can be matched. A RIGHT JOIN from a 'want to read' list against the physical bookshelf identifies books you want but don't own."

### Specify What Should Be Configurable

Bad:
> "Clean up the book titles"

Good:
> "Title normalization rules (stripping 'The', 'A', 'An' prefixes, handling subtitles, series numbering patterns) should be stored in config/normalization_mappings.json, not hardcoded in Python. The Python code reads this config. The config should also be loadable into a SQL table for demonstrating data-driven lookups."

### Think About the Workstream Order

The natural order for most data projects:

1. **Environment setup** — dependencies, folder structure, database connection
2. **Data ingestion** — one workstream per major data source
3. **Data cleaning and normalization** — aligning data across sources
4. **Core business logic** — matching, scoring, computing derived data
5. **Simple API** — basic CRUD endpoints
6. **Authenticated API** — showing what changes with security
7. **Frontend** — the interactive web application
8. **Analytics and notebooks** — data exploration and visualization
9. **Advanced features** — synthetic data, external APIs, recommendations

---

## Key Principles

These principles make vibecoding projects more maintainable, educational, and reusable:

1. **Data-driven schemas**: Don't define database tables in the abstract. Read the actual data files and build schemas to match. This means workstreams can be re-run when data changes.

2. **Configuration over code**: Business rules (normalization mappings, category definitions, thresholds, scoring weights) belong in JSON config files, not Python constants. Students can customize behavior by editing a JSON file without understanding the code. Config files can also be loaded into SQL tables for demonstrating data-driven joins.

3. **Clean at the source**: Provide AI extraction prompts that normalize data at the point of extraction. Automated cleanup in the pipeline is a safety net, not the primary strategy.

4. **Separation of concerns**: Frontend talks to APIs. APIs talk to the database. Never skip a layer. This mirrors real-world architecture.

5. **Rebuild over update**: Derived tables (like "which recipes can I make?") should be rebuilt from source data, not incrementally patched. This is simpler, more correct, and demonstrates an important data engineering pattern.

6. **Document the "why"**: Comments and documentation should teach concepts. "This is a RIGHT JOIN because we want to start from what recipes NEED and find what's available, so missing ingredients show up as NULL" is far more valuable than "# do the join".

7. **Suggest experiments**: Every workstream should end with "Things to Try" that encourage students to explore, break things, and discover on their own. Learning happens through experimentation, not just following instructions.
