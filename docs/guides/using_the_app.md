# Using the WhatToEat Streamlit App

The WhatToEat web application provides a visual interface for browsing recipes, managing your food inventory, and finding out what you can cook. It communicates with the REST API — never touching the database directly.

## Starting the App

You need **two terminal windows**: one for the API server, one for Streamlit.

**Terminal 1 — Start the API server:**
```bash
uv run uvicorn src.api.simple.main:app --reload --port 8000
```

**Terminal 2 — Start Streamlit:**
```bash
uv run streamlit run src/app/main.py
```

Streamlit will open automatically in your browser (usually at `http://localhost:8501`).

## Sidebar Navigation

The left sidebar has two sections:

**Page navigation** — click any page name to switch:
- Recipe Browser
- Add Recipe
- Inventory
- What Can I Make?
- Dashboard

**API Connection** (bottom of sidebar):
- **API URL** — defaults to `http://localhost:8000` (the simple API). Change to `http://localhost:8001` to use the authenticated API.
- **Test Connection** — click to verify the API server is running. A green dot means connected, red means disconnected.

## Pages

### Recipe Browser

A searchable, filterable list of all your recipes.

**Filters across the top:**
- **Search** — type part of a recipe name to filter
- **Temperature** — filter by warm or cold weather tag
- **Condition** — filter by sunny, rainy, or cloudy

**Recipe cards** show the recipe name, timing info, and an availability indicator:
- 🟢 **Can Make** — all ingredients are in your inventory
- 🟡 **Almost** — missing 1-2 ingredients
- 🔴 **Can't Make** — missing more than 2 ingredients
- ⚪ **No match data** — run "Refresh Matching" from the Dashboard

Click any recipe to expand it and see:
- **Ingredients tab** — each ingredient marked with ✅ (available), ❌ (missing), or 🔄 (substitute available)
- **Instructions tab** — step-by-step cooking instructions
- **Full Recipe tab** — if the recipe has Markdown text (the full human-readable version with tips and stories), it appears here

### Add Recipe

Add new recipes by pasting structured JSON (and optionally, full Markdown text).

**Section 1: Structured JSON (required)**
1. Use the extraction prompt in `prompts/recipe_extraction.md` with a browser-connected AI to generate the JSON from a recipe webpage
2. Paste the JSON into the text area
3. The validator checks in real-time:
   - ✅ Valid JSON syntax
   - ✅ Required fields (name, ingredients, instructions)
   - ✅ Ingredient structure (name, quantity, unit, category)
   - ✅ Categories match the normalization config
   - ⚠️ Warnings for missing optional fields (weather tags)
4. Click "Preview" in the expandable section to see how the recipe looks

**Section 2: Full Recipe Markdown (optional)**
- Paste the complete recipe text here — the tips, stories, and detailed descriptions
- A preview shows how the Markdown will render
- This gets stored as the `full_text_markdown` field

**Submit** sends both parts to the API. Fix any ❌ errors before the button becomes active.

### Inventory

A sortable table of everything in your active food inventory.

**Summary cards at the top** show total items, categories, expiring soon count, and expired count.

**Filters:**
- **Category** — filter by food category (protein, dairy, etc.)
- **Source** — show items from receipts, pantry, or all
- **Expiration Status** — show all, expiring soon, expired, or good items

**The table** is color-coded by status:
- **Green**: Good (>7 days until expiration)
- **Yellow**: Expiring soon (3-7 days)
- **Red**: Expiring very soon (<3 days)
- **Gray**: Expired

Click any column header to sort. The **Refresh Inventory** button rebuilds the active inventory from source data (receipts + pantry).

### What Can I Make?

Three tabs help you decide what to cook:

**Ready to Make** — recipes where every ingredient is in stock. Recipes using expiring ingredients get a "Use it up!" badge so you can prioritize them.

**Almost Ready** — use the slider (1-5) to set how many missing ingredients you'll tolerate. Recipes are sorted by fewest missing first. Check the boxes next to recipes, then click "Generate Shopping List" to get a consolidated list of what to buy, grouped by category.

**With Substitutions** — recipes where missing ingredients have a same-category substitute in your inventory (e.g., use mozzarella instead of cheddar). Note: category substitutions are approximate — always use your judgment.

### Dashboard

An overview with summary metrics and charts:

**Metrics row:** total recipes, inventory items, makeable recipe ratio, items expiring this week.

**Charts:**
- **Inventory by Category** — horizontal bar chart showing item counts per food category
- **Recipe Coverage** — pie chart showing the split between makeable, almost makeable, and can't-make recipes
- **Expiration Timeline** — bar chart of items expiring over the next 14 days

**Quick Actions:**
- **Refresh Inventory** — rebuilds the active inventory table
- **Refresh Matching** — rebuilds the recipe-ingredient matching tables
- **Run Full Ingestion** — runs the complete pipeline: ingest recipes, receipts, pantry, rebuild inventory, rebuild matching

## Switching Between APIs

The sidebar API URL field lets you point the app at different API servers:

- **Simple API** (`http://localhost:8000`): No authentication, great for development
- **Authenticated API** (`http://localhost:8001`): Requires login — you'll need to add auth headers (covered in future workstreams)

Change the URL and click "Test Connection" to verify.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot connect to API" | Make sure the API server is running in another terminal |
| No recipes or inventory | Click "Run Full Ingestion" on the Dashboard |
| Match data shows ⚪ | Click "Refresh Matching" on the Dashboard |
| Streamlit won't start | Check that streamlit is installed: `uv add streamlit` |
| Port conflict | Streamlit defaults to 8501. Use `uv run streamlit run src/app/main.py --server.port 8502` for a different port |
