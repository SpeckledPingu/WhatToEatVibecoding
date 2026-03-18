# Recipe Extraction Prompt

Use this prompt with a browser-connected AI assistant (Claude with a browser plugin, ChatGPT, etc.) when you're viewing a recipe webpage and want to extract it into the structured JSON format used by this project.

## How to Use

1. Navigate to the recipe page in your browser
2. Activate your AI browser plugin
3. Copy the **Extraction Prompt** below and paste it into the AI
4. The AI will return a JSON object
5. Either:
   - Save the JSON as a `.json` file in `data/recipes/json/` (e.g., `chicken_soup.json`)
   - OR paste it into the "Add Recipe" section of the Streamlit app

## Extraction Prompt

Copy everything between the `---` lines:

---

Extract this recipe from the current page into the following JSON structure. Use ONLY information visible on the page.

**Ingredient normalization rules:**
- Simplify ingredient names to their common form: "2 large boneless skinless chicken breasts (about 1.5 lbs)" becomes name: "chicken breast", quantity: 2, unit: "pounds"
- Use lowercase for all ingredient names
- Remove brand names, marketing words (organic, premium, artisan), and size descriptions from the name
- Put the amount in `quantity` (as a number, not a fraction — use 0.5 not "1/2") and the measurement in `unit`
- Assign each ingredient a `category` from this list ONLY: protein, vegetable, fruit, dairy, grain, spice, condiment, beverage, snack, other

**Weather classification:**
- `weather_temp`: "cold" for hearty/warming dishes (soups, stews, baked, roasted, braised), "warm" for light/refreshing dishes (salads, grilled, smoothies, chilled)
- `weather_condition`: "rainy" for comfort food and rich dishes, "sunny" for fresh and light dishes, "cloudy" for versatile/moderate dishes

**Unit standardization:** Use these units: pounds, ounces, cups, tablespoons, teaspoons, whole, cloves, stalks, slices, pieces, cans, bunch, head, bulb

Output ONLY valid JSON, nothing else:

```json
{
  "name": "Recipe Name",
  "description": "One-sentence description of the dish",
  "prep_time_minutes": 0,
  "cook_time_minutes": 0,
  "servings": 0,
  "weather_temp": "warm or cold",
  "weather_condition": "sunny, rainy, or cloudy",
  "ingredients": [
    {
      "name": "simple lowercase ingredient name",
      "quantity": 1.0,
      "unit": "cups",
      "category": "one of the standard categories"
    }
  ],
  "instructions": [
    "Step 1 as a complete sentence",
    "Step 2 as a complete sentence"
  ],
  "tags": ["cuisine type", "meal type", "dietary info"],
  "source": "URL or website name"
}
```

---

## Getting the Full Recipe Text (Markdown)

The JSON above captures the **structured data** (what a computer needs). You may also want to save the **full text** of the recipe (what a human reads) — the narrative descriptions, tips, history, and flavor that make recipes enjoyable.

### Option A: Ask the AI to also output Markdown

Add this to the end of the extraction prompt above:

> Also output the complete recipe as human-readable Markdown below the JSON. Start with `# Recipe Name` and include ALL text from the page — the description, ingredient details, step-by-step instructions with tips, and any notes. This should read like the original recipe page, not just a structured list.

Save the Markdown output as a `.md` file in `data/recipes/markdown/` using the **same base name** as the JSON file (e.g., `chicken_soup.md` to pair with `chicken_soup.json`). The system will link them automatically.

### Option B: Use a browser Markdown extension

Install a browser extension that converts web pages to Markdown:
- **MarkDownload** (Chrome/Firefox) — right-click any page and save as `.md`
- **Copy as Markdown** (Chrome) — copies page content as Markdown to clipboard

Save the output to `data/recipes/markdown/` with the same base name as the JSON file.

### Option C: Paste into the Streamlit app

In the Streamlit "Add Recipe" page, there's a section where you can paste the JSON for the structured data AND separately paste or type the full recipe Markdown. This is useful when the AI extraction doesn't capture everything or you want to add personal notes.

## Tips for Better Extractions

- **Multi-part recipes**: If a page has sub-recipes (like a sauce within a main dish), ask the AI to combine them into one recipe or extract them separately
- **Missing weather fields**: The AI is guessing based on the dish — review and adjust if the classification doesn't feel right to you
- **Ingredient categories**: If the AI miscategorizes something (e.g., putting "eggs" in "protein" instead of "dairy"), edit it — consistency matters for the matching system
- **Source field**: Include the full URL when possible so you can find the original page again
