# Pantry Inventory Extraction Prompt

Use this prompt when sending photos of your pantry, fridge, or freezer to an AI assistant (Claude, ChatGPT, etc.) to extract a structured inventory.

## How to Use

1. Take clear photos of your pantry shelves, fridge interior, and/or freezer
2. Open your preferred AI assistant
3. Upload the photo(s)
4. Copy the **Extraction Prompt** below (fill in the date and location first)
5. Copy the CSV output
6. Save it as a `.csv` file in `data/pantry/` (e.g., `pantry_2024_03_15.csv`)

## Tips for Better Photos

- Open doors and drawers fully so items are visible
- Use good lighting — turn on nearby lights or use flash
- Take multiple photos if shelves are deep (front items can hide back items)
- Include close-ups of anything hard to identify
- Photograph one area at a time: top shelf, bottom shelf, door, crisper drawer, etc.
- For freezer items, briefly pull items out if labels are covered in frost

## Extraction Prompt

Copy everything between the `---` lines (fill in the bracketed values first):

---

Look at this photo of my [fridge / freezer / pantry / kitchen counter] and list every food item you can identify as a CSV.

**CRITICAL — Item name normalization rules:**
These normalized names must match recipe ingredients and receipt items in a database. Follow these rules strictly:
- Use simple, common, lowercase names: "milk" not "Organic Valley 2% Reduced Fat Milk 1 Gallon"
- Remove ALL brand names: "Kikkoman" → just "soy sauce", "Trader Joe's" → just the food name
- Remove ALL marketing qualifiers: organic, natural, fresh, premium, artisan, farm-fresh, cage-free, grass-fed, non-gmo, gluten-free
- Remove ALL size/weight descriptors from the name (put amounts in the quantity and unit columns)
- Use the simplest everyday word: "chicken breast" not "boneless skinless chicken breast fillets"
- For spices: "cumin" not "McCormick Ground Cumin", "oregano" not "Simply Organic Mediterranean Oregano"
- For condiments: "soy sauce" not "Less Sodium Soy Sauce", "olive oil" not "Extra Virgin Cold-Pressed Olive Oil"
- For dairy: "milk" not "2% reduced fat milk" (if fat content matters, put it in notes)

**Category assignment:**
Assign exactly ONE category from this list: protein, vegetable, fruit, dairy, grain, spice, condiment, beverage, snack, other
- protein: meat, fish, tofu, beans, lentils
- vegetable: any vegetable including garlic, onion, potato
- fruit: any fruit including tomatoes, lemons, avocado
- dairy: milk, cheese, yogurt, butter, eggs, cream
- grain: bread, rice, pasta, flour, oats, noodles, tortillas, cereal
- spice: salt, pepper, dried herbs, seasoning blends, spice powders
- condiment: oils, vinegars, sauces, broth, ketchup, mustard, honey, maple syrup
- beverage: coffee, tea, juice, soda, water
- snack: chips, crackers, nuts, chocolate, granola bars, popcorn
- other: anything else

**Condition assessment:**
- good: looks normal and fresh
- opened: package is open but item looks fine
- wilting: produce that's starting to look tired
- frozen: in the freezer
- expired: visibly bad or you can see a past-due date

Output ONLY the CSV with headers, no explanation:

```
item_name,quantity,unit,location,condition,category,date_inventoried,notes
```

Use [TODAY'S DATE AS YYYY-MM-DD] for date_inventoried.
Location is: [fridge / freezer / pantry / counter]

Estimate quantities as best you can — 0.5 for "about half left", 0.25 for "almost empty". Use these units: gallon, pounds, ounces, whole, bag, bottle, container, box, can, bunch, loaf, dozen, stick, jar, head, bulb, stalks, cups.

---

## After Extraction

**Always review the output before saving.** AI extraction from photos is imperfect. Check:

- **Quantities**: Are they reasonable? The AI often guesses incorrectly on amounts
- **Categories**: Are they correct? (Remember: eggs = dairy, tomatoes = fruit in our system, garlic = vegetable)
- **Names**: Are they fully normalized? Remove any remaining brand names or qualifiers
- **Missed items**: Did the AI miss anything visible in the photo? Add those rows manually
- **Condition**: The AI can only guess from appearance — correct if you know better

Edit anything that needs fixing in your text editor before saving to `data/pantry/`.

## Why Normalization at Extraction Matters

By normalizing names at the point of extraction (here, when the AI looks at photos), we get cleaner data BEFORE it ever enters the database. This means:
- The automated normalization pipeline (WS04) has less work to do
- Matching between pantry items and recipe ingredients is more accurate
- The same item photographed at different times will get the same normalized name

This is a real-world data engineering principle: **clean data at the source whenever possible**. Automated cleanup later is a safety net, not the primary strategy.
