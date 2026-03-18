# Workstream 09: Analytics, Jupyter Notebooks & Visualizations

Create analytics scripts and Jupyter notebooks that explore the food data, demonstrate data analysis techniques with pandas, and provide a starting point for students to build their own investigations.

## Context

Data analysis is about asking questions of your data and finding answers. This workstream creates analysis tools using two approaches:
1. **Python scripts** — automated analyses that print reports (good for repeatable checks)
2. **Jupyter notebooks** — interactive exploration where you can run code cell by cell, see results inline, and mix code with explanations (good for learning and experimenting)

Both use **pandas** (the most popular Python data analysis library) and **matplotlib** (the foundational visualization library).

## Instructions

1. **Create a comprehensive overview script** at `src/analytics/overview.py`:
   - Load all data from the database (recipes, inventory, matching) into pandas DataFrames
   - Print a formatted "State of the Kitchen" report:
     ```
     === WHAT TO EAT: Kitchen Overview ===

     📖 RECIPES
       Total: 15 recipes
       By format: 10 JSON, 5 Markdown
       By weather: 8 warm, 7 cold | 5 sunny, 6 rainy, 4 cloudy
       Average ingredients per recipe: 8.3

     📦 INVENTORY
       Total active items: 42
       By category: 12 vegetable, 8 dairy, 7 protein, ...
       Expiring this week: 5 items
       Already expired: 2 items

     🍳 RECIPE MATCHING
       Fully makeable: 4 recipes (27%)
       Missing 1-2 ingredients: 6 recipes (40%)
       Missing 3+: 5 recipes (33%)

     🔝 TOP 10 MOST COMMON RECIPE INGREDIENTS
       1. salt (appears in 14 recipes)
       2. olive oil (appears in 11 recipes)
       ...

     🛒 MOST COMMONLY MISSING INGREDIENTS
       1. heavy cream (missing for 5 recipes)
       ...

     ⚠️  INVENTORY NOT IN ANY RECIPE
       - ketchup, soda, crackers
       (these items aren't used by any of your recipes)

     🔍 RECIPE INGREDIENTS NOT IN INVENTORY
       - heavy cream, basil, thyme
       (consider buying these to unlock more recipes)
     ```
   - Use pandas throughout with **educational comments on every operation**:
     - Loading data from SQL into DataFrames
     - Filtering with boolean conditions
     - `value_counts()` for frequency analysis
     - `groupby()` for aggregation
     - `merge()` for combining DataFrames
     - Working with JSON fields stored in columns (using `json.loads` and `pd.json_normalize` or `.explode()`)
   - Make runnable directly

2. **Create a purchase patterns analysis** at `src/analytics/purchase_patterns.py`:
   - Analyze receipt data to find:
     - Most frequently purchased items (across all receipts)
     - Total and average spending per store (if price data exists)
     - Most expensive items purchased
     - Purchase frequency: items bought every trip vs occasionally
     - Category breakdown of spending
   - Create matplotlib visualizations:
     - Bar chart: Top 15 most purchased items
     - Pie chart: Spending by category
     - Bar chart: Spending by store (if multiple stores)
   - Save charts to `docs/` as PNG files AND display them if run in Jupyter
   - Educational comments explaining:
     - Each pandas `groupby` and `agg` operation
     - How to create and customize matplotlib charts
     - The difference between `plt.show()` (interactive) and `plt.savefig()` (save to file)
   - Make runnable directly

3. **Create a food waste estimation script** at `src/analytics/food_waste.py`:
   - Identify items that are expired or expiring before any makeable recipe uses them
   - Calculate a "waste risk" score for the overall inventory:
     ```
     WASTE RISK ANALYSIS
     Items expired: 2 (estimated value: $X.XX based on receipt prices)
     Items expiring in 3 days with no matching recipe: 3
     Items expiring in 7 days with a matching recipe: 2 (make these recipes!)
     Overall waste risk: MEDIUM
     ```
   - Suggest recipes that would use up at-risk items
   - Educational comments about how grocery stores and restaurants use similar analysis to reduce waste
   - Make runnable directly

4. **Create Jupyter Notebook: Data Exploration** at `notebooks/01_data_exploration.ipynb`:
   - **Markdown cells** introducing each section with plain-language explanations
   - Sections:
     - "Loading Data" — how to connect to the database and load tables into DataFrames
     - "First Look" — `.head()`, `.shape`, `.dtypes`, `.describe()`
     - "Asking Questions" — `.value_counts()`, `.groupby()`, filtering with conditions
     - "Working with JSON Fields" — extracting and analyzing the ingredients JSON column
     - "Summary Statistics" — `.agg()`, `.mean()`, `.sum()`
   - Every code cell should have a **markdown cell above it** explaining what the code does and why
   - End with **"Exercises to Try"**:
     - "Modify the groupby above to find the average number of ingredients per weather category"
     - "Filter to only recipes with more than 8 ingredients — what do they have in common?"
     - "Find which category of food appears in the most recipes"
   - Use the student's actual data throughout (query from the database)

5. **Create Jupyter Notebook: Join Operations** at `notebooks/02_join_operations.ipynb`:
   - Teach different join types using the food data:
   - **Markdown introduction** explaining joins with a simple analogy (like matching socks from two drawers)
   - **Section 1: Inner Join** — ingredients that appear in BOTH recipes and inventory
     - Show the pandas: `pd.merge(recipes_df, inventory_df, on='join_key', how='inner')`
     - Explain: "This shows only what matches in both — ingredients you have that recipes need"
   - **Section 2: Left Join** — all inventory items, matched to recipes where possible
     - "Start from what you HAVE, find recipes that use it. NaN means no recipe uses this item."
   - **Section 3: Right Join** — all recipe ingredients, matched to inventory where possible
     - "Start from what recipes NEED, find it in inventory. NaN means you DON'T have this."
     - **This is the key join** — it's how recipe matching works
   - **Section 4: Outer Join** — everything from both tables
     - "The complete picture — every item and every ingredient, matched where possible"
   - **Visualize** each join type: show which rows survive and which get NaN
   - **Exercises**:
     - "Modify the right join to only show rows where the inventory match is NaN (missing ingredients)"
     - "Use the inner join to find which of your inventory items are used by the most recipes"

6. **Create Jupyter Notebook: Visualization** at `notebooks/03_visualization.ipynb`:
   - **Bar charts**: Ingredient frequency, inventory by category, spending by store
   - **Pie charts**: Recipe weather distribution, inventory source breakdown
   - **Horizontal bar charts**: Missing ingredients ranked (shopping list visualization)
   - **Timeline charts**: Expiration dates over the next month, purchase dates over time
   - Each chart section:
     - Markdown explaining the chart type and when to use it
     - Code to create the chart with EVERY matplotlib call commented
     - A "Customization" cell showing how to change colors, labels, sizes
   - **Exercises**:
     - "Create a chart showing which recipes need the fewest additional ingredients"
     - "Make a stacked bar chart showing inventory by category AND source"
     - "Create a chart of your own choosing that answers a question about your data"

7. **Create Jupyter Notebook: Data Cleaning Deep Dive** at `notebooks/04_data_cleaning.ipynb`:
   - Walk through the normalization process step by step:
   - Load raw receipt and pantry data
   - Show the messy state: different names for the same food
   - Apply cleaning functions one at a time and show before/after
   - Demonstrate how match rates improve with each cleaning step:
     ```
     Before cleaning: 15% of recipe ingredients found in inventory
     After lowercase: 35%
     After removing brands: 52%
     After removing sizes: 68%
     After abbreviation expansion: 71%
     ```
   - **Interactive exploration**: let the student modify cleaning rules and see the impact
   - **Exercises**:
     - "Add a cleaning rule for a pattern specific to your data"
     - "Find two items that SHOULD match but don't — what cleaning rule would fix it?"
     - "What's the match rate if you only use category-level matching instead of exact name?"

8. **Verify all notebooks run** by executing them and checking for errors. Fix any issues.

9. **Create a Jupyter getting started guide** at `docs/guides/jupyter_getting_started.md`:
   - What Jupyter notebooks are (interactive documents mixing code, text, and output)
   - How to start: `uv run jupyter notebook`
   - Navigating the interface: file browser, cell types, toolbar
   - Running cells: Shift+Enter, Run All
   - Adding cells: code vs markdown
   - Saving and checkpoints
   - Tips for using Claude Code to help write notebook analysis cells
   - Common issues and solutions

## Things to Try After This Step

- Open `notebooks/01_data_exploration.ipynb` and run all cells to see your data explored
- Complete the exercises at the end of each notebook
- Modify the purchase patterns script to analyze your spending trends differently
- Ask Claude Code: "Create a notebook that calculates recipe similarity — which recipes share the most ingredients?"
- Ask Claude Code: "Add a visualization comparing real data vs synthetic data distributions"
- Try the food waste analysis — are you at risk of wasting any inventory items?
- Create your OWN notebook: ask Claude Code a question about your data and have it create a notebook to answer it
- Export a completed notebook to HTML (`File > Download as > HTML`) to share with someone
