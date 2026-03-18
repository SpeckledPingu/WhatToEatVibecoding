# Workstream 08: Streamlit Web Application

Build an interactive web application using Streamlit that communicates with the REST APIs to display and manage your food inventory and recipes.

## Context

Streamlit is a Python library that turns scripts into web applications. Instead of writing HTML, CSS, and JavaScript, you write Python code and Streamlit handles the UI. Our app talks to the database **exclusively through the REST APIs** built in WS06/07 — it never queries the database directly. This demonstrates **separation of concerns**:
- **Frontend** (Streamlit): Displays data and handles user interaction
- **Backend** (FastAPI): Handles business logic and database operations
- **Database** (SQLite): Stores the data

This is the same architecture used by professional web applications.

## Instructions

1. **Create the main Streamlit application** at `src/app/main.py`:
   - Page configuration:
     - Title: "WhatToEat"
     - Layout: "wide"
     - Page icon: a food-related emoji
   - **Sidebar navigation** with these pages:
     - Recipe Browser
     - Add Recipe
     - Inventory
     - What Can I Make?
     - Dashboard
   - **Sidebar configuration section** (at the bottom):
     - API URL input (default: `http://localhost:8000`) — so users can switch between simple and authenticated API
     - A "Test Connection" button that pings the API root endpoint
     - Display connection status (connected/disconnected)
   - Educational comments explaining:
     - Streamlit's execution model: the ENTIRE script re-runs on every user interaction (click, type, select)
     - Why `st.session_state` exists (to preserve data across re-runs)
     - How the sidebar navigation works

2. **Create an API client** at `src/app/api_client.py`:
   - A class `WhatToEatAPI` that wraps all API calls using httpx:
     - `__init__(self, base_url: str)` — stores the API base URL
     - Recipe methods: `list_recipes()`, `get_recipe(id)`, `create_recipe(data)`, `update_recipe(id, data)`, `delete_recipe(id)`, `get_makeable()`, `get_almost_makeable(max_missing)`, `get_with_substitutions()`
     - Inventory methods: `list_inventory()`, `get_expiring()`, `get_summary()`, `refresh_inventory()`
     - Matching methods: `get_match_summary()`, `get_recipe_match(id)`, `get_shopping_list(ids)`, `refresh_matching()`
     - Ingestion methods: `ingest_all()`, `ingest_recipes()`, `ingest_receipts()`, `ingest_pantry()`
   - Error handling: catch httpx errors and return user-friendly messages
   - Include educational comments explaining:
     - What an API client is (a helper that wraps HTTP calls so the rest of the app doesn't deal with URLs and headers)
     - Why centralize API calls (DRY principle, easy to change the URL or add auth headers)
     - How httpx works (similar to requests, but with async support)

3. **Build the Recipe Browser page** at `src/app/pages/recipe_browser.py`:
   - Create a function that the main app calls to render this page
   - **Filters** in a row at the top:
     - Text search (searches recipe names)
     - Weather temperature dropdown (All / Warm / Cold)
     - Weather condition dropdown (All / Sunny / Rainy / Cloudy)
   - **Recipe list** displayed as cards or an expandable list:
     - Recipe name (large)
     - Description (if available)
     - Weather tags as colored badges
     - Prep/cook time and servings
     - A colored indicator: green = "Can Make", yellow = "Almost" (1-2 missing), red = "Can't Make"
   - **Click/expand to see full details**:
     - Full ingredient list (with checkmarks for available, X for missing)
     - Step-by-step instructions
     - If `full_text_markdown` exists, a "Full Recipe" tab showing the rendered markdown (the complete recipe with tips, stories, and detailed descriptions)
     - Source information
   - Educational comments about Streamlit layout (columns, expanders, containers)

4. **Build the Add Recipe page** at `src/app/pages/add_recipe.py`:
   - **Section 1: Structured Data (JSON)** — required:
     - A large text area for pasting recipe JSON (extracted using `prompts/recipe_extraction.md`)
     - A "Preview" button that parses the JSON and shows a formatted preview
     - A "Validate" section that checks:
       - Is it valid JSON?
       - Does it have required fields (name, ingredients, instructions)?
       - Are ingredient objects properly structured (name, quantity, unit)?
       - Are ingredient categories valid (check against `config/normalization_mappings.json` categories)?
       - Are weather fields filled in?
     - Show green checkmarks for passing checks, red X for failing, yellow warnings for optional missing fields
     - Include a collapsible "Example JSON format" section and a link to `prompts/recipe_extraction.md`
   - **Section 2: Full Recipe Text (Markdown)** — optional:
     - A large text area for pasting or writing the full recipe in Markdown
     - A rendered preview (using st.markdown) showing how it will look
     - Help text: "This is the full human-readable recipe. Get it from your browser's markdown extension or paste the original text."
     - This content is stored in the `full_text_markdown` field
   - **Submit button** that sends both structured JSON and optional markdown to the API
   - **After submission**: show success/error message and offer to view the new recipe
   - Include example templates the user can copy and modify
   - Educational comments about form validation and why it matters for data quality

5. **Build the Inventory page** at `src/app/pages/inventory.py`:
   - **Summary cards** at the top: total items, items by category, expiring soon count, expired count
   - **Filters**: category dropdown, source (receipt/pantry/all), expiration status (all/expiring soon/expired/good)
   - **Inventory table** with columns: Item Name, Category, Quantity, Unit, Source, Date Acquired, Expiration Date, Status
     - Color-code the Status column:
       - Green: Good (>7 days until expiration)
       - Yellow: Expiring soon (3-7 days)
       - Red: Expiring very soon (<3 days)
       - Gray: Expired
   - **Sortable** by any column (use pandas DataFrame display)
   - **Refresh button** that triggers an inventory rebuild via the API
   - Educational comments about data display, color coding for UX, and how Streamlit handles DataFrames

6. **Build the What Can I Make? page** at `src/app/pages/what_can_i_make.py`:
   - **Three sections**, each in its own tab or expander:

   **Section 1: "Ready to Make"**
   - Recipes where all ingredients are available
   - Display as cards with recipe name, description, weather tags
   - Highlight any that use expiring ingredients with a "Use it up!" badge
   - Button to see full recipe details

   **Section 2: "Almost Ready"**
   - A slider: "Show recipes missing up to N ingredients" (range 1-5, default 2)
   - Display matching recipes sorted by fewest missing ingredients
   - For each recipe show: name, what's available (checked), what's missing (unchecked with names)
   - Checkboxes to select recipes for shopping list generation

   **Section 3: "With Substitutions"**
   - Recipes where missing ingredients have a same-category substitute in inventory
   - For each recipe: show the missing ingredient and the suggested substitute
   - Help text explaining that category substitutions are approximate (mozzarella might substitute for cheddar, but parmesan might not)

   **Shopping List Generator**:
   - A "Generate Shopping List" button that consolidates missing ingredients from selected recipes
   - Display the shopping list grouped by category
   - Option to copy the list to clipboard

7. **Build the Dashboard page** at `src/app/pages/dashboard.py`:
   - **Summary metrics** in a row (using `st.metric`):
     - Total recipes
     - Total inventory items
     - Makeable recipes / Total recipes
     - Items expiring this week
   - **Charts** (using matplotlib or Streamlit's built-in charting):
     - Inventory by category (bar chart)
     - Recipe coverage: pie chart of makeable vs almost vs can't make
     - Expiration timeline: items expiring over the next 2 weeks
   - **Quick action buttons**:
     - "Refresh Inventory" — triggers rebuild
     - "Refresh Matching" — triggers recipe matching rebuild
     - "Run Full Ingestion" — runs the complete pipeline
   - Status messages showing the result of each action

8. **Test the application**:
   - First, start the API server: `uv run uvicorn src.api.simple.main:app --reload --port 8000`
   - Then, start Streamlit: `uv run streamlit run src/app/main.py`
   - Verify each page loads and displays data
   - Test the Add Recipe form with valid and invalid data
   - Test the shopping list generation
   - Test the refresh/ingestion buttons

9. **Create usage documentation** at `docs/guides/using_the_app.md`:
   - Description of each page and what it shows
   - How to navigate between pages
   - How to add recipes (JSON and Markdown)
   - How to use the "What Can I Make?" features
   - How to switch between simple and authenticated APIs
   - Screenshots are not needed, but describe what each page looks like

## Things to Try After This Step

- Add a recipe through the UI and verify it appears in the Recipe Browser
- Use the "What Can I Make?" page to plan a meal based on your actual inventory
- Try switching the API URL to `http://localhost:8001` (the authenticated API) — what happens when you try to add a recipe?
- Look at the Dashboard and watch the metrics change after running an ingestion
- Modify the expiration color thresholds (e.g., change "soon" from 3-7 days to 5-10 days)
- Ask Claude Code: "Add a meal planning page that suggests a week of dinners from makeable recipes"
- Ask Claude Code: "Add a price comparison section that shows ingredient costs from receipt data"
- Try making the app responsive for mobile by adjusting the layout
- Think about: what other pages would be useful? A "frequently purchased" page? A "recipe similarity" page?
