# Receipt Extraction Prompt

Use this prompt when sending a photo of a store receipt to an AI assistant (Claude, ChatGPT, etc.) to extract the purchase data.

## How to Use

1. Photograph your receipt — make sure ALL text is clearly readable
2. Open your preferred AI assistant
3. Upload the receipt photo
4. Copy the **Extraction Prompt** below (fill in the store name and date first)
5. Copy the CSV output
6. Save it as a `.csv` file in `data/receipts/` (e.g., `trader_joes_2024_03_15.csv`)

## Tips for Better Receipt Photos

- Lay the receipt flat on a dark, contrasting surface
- Ensure ALL text is in frame and sharp — blurry text leads to errors
- If the receipt is long, take multiple overlapping photos and tell the AI "this is part 1 of 2"
- Use good lighting without shadows across the text
- If the receipt is faded (thermal paper fades fast!), increase brightness/contrast before uploading
- Photograph it the same day if possible — thermal receipts can become unreadable within weeks

## Extraction Prompt

Copy everything between the `---` lines (fill in the bracketed values first):

---

Extract every FOOD item from this receipt into a CSV. The store is [STORE NAME] and the purchase date is [YYYY-MM-DD].

**Include TWO name columns:**
- `item_name`: The text EXACTLY as printed on the receipt (for traceability — we want to know what the receipt actually said)
- `normalized_name`: A simplified, lowercase version of the name, following these rules:
  - Remove ALL brand names and store brands: "TJ'S ORGANIC" → just the food name
  - Remove ALL size/weight info: "16OZ", "1GAL", "2LB" → these go in quantity/unit columns
  - Remove ALL marketing words: organic, natural, premium, artisan, etc.
  - Expand receipt abbreviations: "BNLS SKNLS CHKN BRST" → "chicken breast", "ORG WHL MLK" → "milk", "GRN PEPPERS" → "green pepper"
  - Use the simplest everyday name: "milk" not "whole milk", "chicken breast" not "boneless skinless chicken breast"
  - This normalized name MUST match how the same item would be listed in a pantry inventory

**Category assignment:**
Assign exactly ONE from: protein, vegetable, fruit, dairy, grain, spice, condiment, beverage, snack, other

**What to SKIP:**
- Non-food items (bags, cleaning supplies, toiletries, paper goods, pet food)
- Tax lines, subtotals, totals, payment lines
- Reward/loyalty point lines, coupon summary lines
- Bottle/CRV deposit lines

**Price rules:**
- If a line shows quantity x unit_price = total, capture all three
- If only a total is shown, put it in total_price and leave unit_price empty
- If a coupon/discount applies to an item, use the FINAL (discounted) price
- If quantity is unclear, assume 1

Output ONLY the CSV with headers, no explanation:

```
item_name,normalized_name,quantity,unit_price,total_price,category,store_name,purchase_date
```

---

## After Extraction

**Always review the output before saving.** Receipt OCR via AI is good but imperfect. Check:

- **All food items captured?** Long receipts or faded text can cause items to be missed
- **Prices correct?** Watch for items where quantity > 1 (the math should work: quantity x unit_price = total_price)
- **Non-food items excluded?** Remove any cleaning products, bags, or non-food items that slipped through
- **Normalized names reasonable?** The `normalized_name` should match pantry inventory names — "milk" not "2% Reduced Fat Milk"
- **Abbreviations decoded?** Receipt abbreviations can be tricky — verify the AI interpreted them correctly

Edit anything that needs fixing before saving to `data/receipts/`.

## About the normalized_name Column

This column is unique to receipt data. Receipts have the messiest item names of all our data sources because they reflect the store's inventory system ("TJ ORG BNLS CHKN BRST 1.5LB"), not how humans think about food ("chicken breast").

By asking the AI to provide a pre-normalized name at extraction time, we:
1. Get a human-verified normalization (you can check and fix it immediately)
2. Reduce the work the automated normalization pipeline needs to do
3. Improve matching accuracy between receipts, pantry items, and recipe ingredients

The original `item_name` is preserved so you can always trace back to exactly what the receipt said — this is called **data provenance** and it's important in any data pipeline.

## Handling Multiple Receipt Photos

If your receipt is too long for one photo:

1. Tell the AI: "This is photo 1 of 3 of the same receipt from [STORE] on [DATE]"
2. After each extraction, combine the CSVs (remove duplicate header rows)
3. Check for any items split across photos (an item at the bottom of photo 1 might appear again at the top of photo 2)
