# Data Format Guide

This guide describes the expected formats for each type of data file used in the WhatToEat application. You can create these files manually, or use AI tools (like Claude or ChatGPT) to extract data from photos of receipts and pantry shelves.

---

## Recipe JSON Format

Each recipe is a single JSON file in `data/recipes/json/`. Name the file after the recipe using underscores (e.g., `chicken_soup.json`).

### Example: `chicken_soup.json`

```json
{
  "name": "Chicken Noodle Soup",
  "description": "A classic comfort soup perfect for cold days",
  "prep_time_minutes": 15,
  "cook_time_minutes": 45,
  "servings": 6,
  "weather_temp": "cold",
  "weather_condition": "rainy",
  "ingredients": [
    {
      "name": "chicken breast",
      "quantity": 2,
      "unit": "pounds",
      "category": "protein"
    },
    {
      "name": "egg noodles",
      "quantity": 8,
      "unit": "ounces",
      "category": "grain"
    },
    {
      "name": "carrots",
      "quantity": 3,
      "unit": "whole",
      "category": "vegetable"
    },
    {
      "name": "celery",
      "quantity": 3,
      "unit": "stalks",
      "category": "vegetable"
    },
    {
      "name": "chicken broth",
      "quantity": 8,
      "unit": "cups",
      "category": "condiment"
    },
    {
      "name": "salt",
      "quantity": 1,
      "unit": "teaspoon",
      "category": "spice"
    },
    {
      "name": "black pepper",
      "quantity": 0.5,
      "unit": "teaspoon",
      "category": "spice"
    }
  ],
  "instructions": [
    "Bring chicken broth to a boil in a large pot",
    "Add chicken breasts and cook for 20 minutes",
    "Remove chicken, shred with forks, and return to pot",
    "Add carrots and celery, cook for 10 minutes",
    "Add egg noodles, cook for 8 minutes",
    "Season with salt and pepper to taste"
  ],
  "tags": ["soup", "comfort food", "easy"],
  "source": "family recipe"
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Recipe name |
| `ingredients` | array | List of ingredient objects (see below) |
| `instructions` | array | Ordered list of preparation steps |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Brief description of the dish |
| `prep_time_minutes` | integer | Preparation time in minutes |
| `cook_time_minutes` | integer | Cooking time in minutes |
| `servings` | integer | Number of servings the recipe makes |
| `weather_temp` | string | `"warm"` or `"cold"` — what temperature weather suits this food |
| `weather_condition` | string | `"rainy"`, `"sunny"`, or `"cloudy"` — what weather condition suits this food |
| `tags` | array | Category tags (e.g., "soup", "quick", "vegetarian") |
| `source` | string | Where the recipe came from |

### Ingredient Object Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Ingredient name (e.g., "chicken breast") |
| `quantity` | number | Yes | Amount needed (e.g., 2, 0.5) |
| `unit` | string | Yes | Unit of measurement (e.g., "pounds", "cups", "whole") |
| `category` | string | Recommended | Food category — see standard categories below |

---

## Recipe Markdown Format (Full Text)

Markdown files in `data/recipes/markdown/` store the **full human-readable text** of a recipe — the description, tips, story, and detailed instructions as you'd read them on a recipe website. Unlike the JSON files (which contain structured data for the database), Markdown files are stored as-is and not parsed for structured fields.

### How JSON and Markdown Are Linked

Each Markdown file is **paired with a JSON file by filename**:
- `data/recipes/json/chicken_soup.json` — structured data (parsed into database fields)
- `data/recipes/markdown/chicken_soup.md` — full recipe text (stored in the `full_text_markdown` field)

The JSON file is **required** (it's the primary data source). The Markdown file is **optional** (it enriches the record with the full text).

### Example: `chicken_soup.md`

This can be any format — it's stored as-is, not parsed for structure:

```markdown
# Chicken Noodle Soup

*A classic comfort soup that warms you up from the inside out. This is my grandmother's recipe, passed down through three generations. The secret is letting the chicken simmer low and slow to build flavor in the broth.*

## Ingredients

- **2 pounds chicken breast** — bone-in gives more flavor, but boneless works if that's what you have
- **8 ounces egg noodles** — wide egg noodles hold the broth best
- **3 carrots**, peeled and sliced into coins
- **3 stalks celery**, sliced
- **8 cups chicken broth** — homemade is best, but store-bought is fine
- **Salt and black pepper** to taste

## Instructions

1. Bring the chicken broth to a gentle boil in a large pot. Don't let it boil too vigorously.
2. Add the chicken breasts whole. Reduce heat to medium and cook for 20 minutes until the internal temperature reaches 165°F.
3. Remove the chicken to a cutting board. When cool enough to handle, shred it with two forks. Return the shredded chicken to the pot.
4. Add the carrots and celery. Cook for 10 minutes until tender but still with a bit of bite.
5. Add the egg noodles and cook for 8 minutes, stirring occasionally so they don't stick.
6. Season generously with salt and pepper. Taste and adjust.

## Tips

- Add a squeeze of lemon juice at the end for brightness
- This soup freezes well for up to 3 months (without noodles — add them fresh when reheating)
- Leftover rotisserie chicken works great if you're short on time

*Adapted from grandma's recipe box, circa 1965*
```

### How to Get Markdown Files

**Option A: Browser extension** — Install a Markdown extension like "MarkDownload" (Chrome/Firefox). When viewing a recipe page, click the extension to save the page as `.md`.

**Option B: AI extraction** — When using the `prompts/recipe_extraction.md` prompt, add: "Also provide the complete recipe as formatted Markdown." Save the output as a `.md` file.

**Option C: Streamlit app** — Paste the full recipe text directly into the "Add Recipe" page alongside the JSON.

**Option D: Skip it** — Markdown files are optional. The JSON alone provides all the structured data needed for the application to function.

---

## Receipt CSV Format

Receipt CSVs go in `data/receipts/`. Each file represents purchases from one shopping trip.

### Example: `trader_joes_2024_03_15.csv`

```csv
item_name,quantity,unit_price,total_price,category,store_name,purchase_date
Organic Whole Milk 1gal,1,5.99,5.99,Dairy,Trader Joe's,2024-03-15
Sourdough Bread,1,3.99,3.99,Bakery,Trader Joe's,2024-03-15
Chicken Breast 2lb,1,8.49,8.49,Meat,Trader Joe's,2024-03-15
Baby Spinach 5oz,2,2.99,5.98,Produce,Trader Joe's,2024-03-15
Eggs Large Dozen,1,3.49,3.49,Dairy,Trader Joe's,2024-03-15
Cheddar Cheese Block 8oz,1,4.29,4.29,Dairy,Trader Joe's,2024-03-15
Yellow Onion,3,0.79,2.37,Produce,Trader Joe's,2024-03-15
Garlic Bulb,2,0.50,1.00,Produce,Trader Joe's,2024-03-15
Olive Oil 16oz,1,6.99,6.99,Pantry,Trader Joe's,2024-03-15
Jasmine Rice 2lb,1,3.49,3.49,Pantry,Trader Joe's,2024-03-15
```

### Expected Columns

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `item_name` | string | Yes | Item name as printed on the receipt |
| `normalized_name` | string | Recommended | Pre-cleaned version of the name (see note below) |
| `quantity` | integer | Yes | Number of units purchased |
| `unit_price` | decimal | Recommended | Price per unit |
| `total_price` | decimal | Recommended | Total price for this line item |
| `category` | string | Recommended | Food category (protein, vegetable, dairy, etc.) |
| `store_name` | string | Yes | Name of the store |
| `purchase_date` | date | Yes | Date of purchase (YYYY-MM-DD format) |

> **Creating receipt CSVs:** Use the standardized extraction prompt in **`prompts/receipt_extraction.md`**. It instructs the AI to produce both the raw `item_name` (what the receipt says) and a `normalized_name` (a cleaned-up version that matches pantry/recipe naming). This pre-normalization at the point of extraction significantly improves data alignment later.

> **About `normalized_name`:** This column is optional but very valuable. Receipt item names are the messiest data source ("TJ ORG BNLS CHKN BRST 1.5LB"). Having a pre-normalized name ("chicken breast") from the AI extraction means the automated cleanup pipeline has a head start. If this column is missing, the normalization workstream (WS04) will clean `item_name` automatically using the rules in `config/normalization_mappings.json`.

---

## Pantry Inventory CSV Format

Pantry inventory CSVs go in `data/pantry/`. Each file represents a snapshot of what's currently in your kitchen.

### Example: `pantry_2024_03_15.csv`

```csv
item_name,quantity,unit,location,condition,category,date_inventoried,notes
milk,0.5,gallon,fridge,good,dairy,2024-03-15,about half left
bread,1,loaf,counter,good,grain,2024-03-15,sourdough
chicken breast,1.5,pounds,freezer,frozen,protein,2024-03-15,
spinach,1,bag,fridge,wilting,vegetable,2024-03-15,use soon
eggs,8,whole,fridge,good,dairy,2024-03-15,
cheddar cheese,0.5,block,fridge,good,dairy,2024-03-15,
onion,2,whole,pantry,good,vegetable,2024-03-15,yellow onion
garlic,1,bulb,pantry,good,vegetable,2024-03-15,
olive oil,0.75,bottle,pantry,good,condiment,2024-03-15,
rice,2,pounds,pantry,good,grain,2024-03-15,white rice
salt,1,container,pantry,good,spice,2024-03-15,
black pepper,1,container,pantry,good,spice,2024-03-15,
soy sauce,1,bottle,pantry,good,condiment,2024-03-15,
flour,3,pounds,pantry,good,grain,2024-03-15,all-purpose
butter,1,stick,fridge,good,dairy,2024-03-15,
```

### Expected Columns

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `item_name` | string | Yes | Item name (can be informal/short) |
| `quantity` | decimal | Yes | Amount currently on hand |
| `unit` | string | Yes | Unit of measurement |
| `location` | string | Recommended | Where it's stored: fridge, freezer, pantry, counter |
| `condition` | string | Recommended | Current state: good, wilting, frozen, opened, sealed |
| `category` | string | Recommended | Food category |
| `date_inventoried` | date | Yes | When this inventory was taken (YYYY-MM-DD) |
| `notes` | string | No | Any additional notes |

> **Creating pantry CSVs:** Use the standardized extraction prompt in **`prompts/pantry_extraction.md`**. It instructs the AI to normalize item names at the point of extraction (removing brands, sizes, and marketing words) and assign standard categories, which improves data alignment with recipes and receipts.

---

## Standard Food Categories

When assigning categories to food items (in recipes, receipts, or pantry data), try to use these standard values. Consistent categories enable the fuzzy matching feature that suggests ingredient substitutions.

| Category | Examples |
|----------|----------|
| `protein` | Chicken, beef, pork, fish, tofu, beans, lentils |
| `vegetable` | Carrots, onions, spinach, broccoli, peppers, garlic |
| `fruit` | Apples, bananas, lemons, berries, tomatoes |
| `dairy` | Milk, cheese, yogurt, butter, eggs, cream |
| `grain` | Bread, rice, pasta, flour, oats, noodles |
| `spice` | Salt, pepper, cumin, oregano, paprika, herbs |
| `condiment` | Oil, vinegar, soy sauce, broth, ketchup, mustard |
| `beverage` | Coffee, tea, juice, soda |
| `snack` | Chips, crackers, nuts, chocolate |
| `other` | Anything that doesn't fit above |

---

## Important Notes

### Why Receipt and Pantry Schemas Differ

Notice that receipt data uses names like "Organic Whole Milk 1gal" while pantry data uses "milk." This is **intentional and realistic** — it reflects how data from different real-world sources never perfectly aligns. The normalization workstream (WS04) will teach you how to handle these differences.

### Your Data Doesn't Need to Match Exactly

The ingestion scripts (WS02-03) are designed to read YOUR actual column names and adapt. Having columns close to the expected format helps, but the workstream prompts will analyze your actual data and build schemas to match.

### Date Format

Always use **YYYY-MM-DD** format for dates (e.g., `2024-03-15`). This is the ISO 8601 international standard and avoids ambiguity between US (MM/DD/YYYY) and European (DD/MM/YYYY) conventions.

### File Naming

- Use descriptive names: `trader_joes_2024_03_15.csv` is better than `receipt1.csv`
- Avoid spaces in filenames — use underscores instead
- Include the date in the filename when possible for easy reference
