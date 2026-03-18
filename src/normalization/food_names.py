"""
food_names.py — Normalize food names from receipts, pantry, and recipes.

THE NORMALIZATION PROBLEM
Food data from different sources uses wildly different names for the same thing:
  - Receipt: "Greenwise Hmstyle Meatbal Ft" (brand + abbreviation + suffix)
  - Pantry:  "all purpose flour" (clean, but not the canonical name "flour")
  - Recipe:  "butter" (already canonical)

To combine these into a unified inventory, we need to normalize all names to
a standard form. Normalization means: lowercase, expand abbreviations, strip
qualifiers and sizes, resolve aliases to canonical names.

CONFIGURATION OVER CODE
All normalization rules live in config/normalization_mappings.json, NOT in this
Python file. This means:
  - Students can customize rules by editing JSON (no Python changes needed)
  - Adding a new food alias or abbreviation is just a JSON edit
  - The Python code here is generic logic; the config file has the specific data
  - If you find a food that doesn't normalize correctly, add a rule to the config

HOW TO CUSTOMIZE
1. Open config/normalization_mappings.json
2. Find the relevant section:
   - name_aliases: to add a new variation of a food name
   - abbreviations: to expand a new receipt abbreviation
   - qualifiers_to_strip: to ignore a new marketing term
   - food_categories: to put a food in the right category
3. Save the file and re-run the normalization pipeline

RUN IT (demo mode):
    uv run python -m src.normalization.food_names
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.normalization import NormalizationMapping

# ---------------------------------------------------------------------------
# Config file path — resolved relative to the project root
# ---------------------------------------------------------------------------
# Path(__file__) is THIS file (food_names.py), .parent.parent.parent goes up
# from src/normalization/ to the project root
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "normalization_mappings.json"


@lru_cache(maxsize=1)
def load_normalization_config() -> dict:
    """
    Read and cache the normalization configuration file.

    WHY A SEPARATE CONFIG FILE?
    Keeping normalization rules in JSON rather than Python code follows the
    "configuration over code" principle:
      - Non-programmers can edit JSON to add new aliases
      - The same config can be loaded into a SQL table for data-driven joins
      - Changes don't require understanding the normalization code
      - Rules are visible in one central, auditable location

    WHY @lru_cache?
    lru_cache memoizes the result — the file is read once on first call, and
    subsequent calls return the cached dict instantly. This avoids re-reading
    the JSON file every time we normalize a food name (which could be hundreds
    of times during a pipeline run).

    Returns:
        A dict containing all normalization rules from the config file.
    """
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    return config


def _build_reverse_alias_map(config: dict) -> dict[str, str]:
    """
    Build a reverse lookup: {alias → canonical_name}.

    The config stores aliases as:
        "chicken breast": ["boneless chicken", "chkn breast", ...]

    We need the reverse: given "chkn breast", return "chicken breast".
    This function builds that mapping, including the canonical name itself.
    """
    reverse_map = {}
    for canonical, aliases in config.get("name_aliases", {}).items():
        if canonical.startswith("_"):
            continue
        # Include the canonical name as its own alias (for exact matches)
        reverse_map[canonical.lower()] = canonical.lower()
        if isinstance(aliases, list):
            for alias in aliases:
                reverse_map[alias.lower()] = canonical.lower()
    return reverse_map


def _flatten_strip_terms(section: dict) -> list[str]:
    """
    Flatten a config section with subcategories into a single list of terms.

    The config organizes strip terms into subcategories for readability:
        "qualifiers_to_strip": {
            "marketing": ["organic", "natural", ...],
            "diet_and_health": ["non-gmo", "gluten free", ...],
            ...
        }

    This function flattens them into one list: ["organic", "natural", "non-gmo", ...]
    and sorts longest-first so multi-word terms are matched before single words.
    """
    terms = []
    for key, values in section.items():
        if key.startswith("_"):
            continue
        if isinstance(values, list):
            terms.extend(values)
    # Sort longest first so "extra large" is stripped before "large"
    return sorted(terms, key=len, reverse=True)


def _flatten_size_patterns(section: dict) -> list[str]:
    """
    Flatten the size_patterns_to_strip config section into a list of regex patterns.
    """
    patterns = []
    for key, values in section.items():
        if key.startswith("_"):
            continue
        if isinstance(values, list):
            patterns.extend(values)
    return patterns


def normalize_food_name(raw_name: str, pre_normalized: str | None = None) -> str:
    """
    Transform a raw food name into a standardized canonical form.

    THE NORMALIZATION PIPELINE
    Each step addresses a specific type of messiness found in real food data:

    1. **Pre-normalized shortcut**: If the data source already provides a cleaned
       name (from an AI extraction prompt), use that as a head start instead of
       trying to decode receipt abbreviations from scratch.

    2. **Lowercase + strip**: Basic text normalization — "Organic MILK" → "organic milk"

    3. **Expand abbreviations**: Receipt systems use shorthand to fit POS displays.
       "chkn" → "chicken", "brst" → "breast", "bnls" → "boneless"
       Without this, "BNLS SKNLS CHKN BRST" would be unrecognizable.

    4. **Strip qualifiers**: Marketing terms add no value for matching.
       "organic", "natural", "fresh", "cage-free" — these don't change WHAT
       the food is, just how it was produced or marketed.

    5. **Strip packaging terms**: Container descriptors from store data.
       "bag", "box", "bunch" — these describe HOW the food is sold, not WHAT it is.

    6. **Strip size/weight patterns**: Embedded measurements from SKU data.
       "16oz", "2lb", "5ct" — store-specific sizing that varies by package.

    7. **Resolve aliases**: Map known variations to canonical names.
       "whole milk" → "milk", "baby spinach" → "spinach"
       This is the most powerful step — it handles naming differences between
       stores, recipes, and common usage.

    Parameters:
        raw_name: The food name as it appears in the source data.
        pre_normalized: Optional pre-cleaned name from AI extraction.
                        If provided and non-empty, used as the starting point
                        instead of raw_name (skips abbreviation expansion).

    Returns:
        The canonical, standardized food name (e.g., "butter", "chicken breast").

    Examples:
        >>> normalize_food_name("Organic Whole Milk 1gal")
        'milk'
        >>> normalize_food_name("BNLS SKNLS CHKN BRST")
        'chicken breast'
        >>> normalize_food_name("Greenwise Hmstyle Meatbal Ft", pre_normalized="meatball")
        'meatball'
    """
    config = load_normalization_config()

    # -----------------------------------------------------------------------
    # Step 1: Use pre-normalized name if available
    # -----------------------------------------------------------------------
    # Receipt data from AI extraction prompts often includes a normalized_name
    # column. This is already cleaned by the LLM, so it's a better starting
    # point than the raw receipt text. We still run the remaining steps to
    # ensure consistency with our canonical names.
    if pre_normalized and pre_normalized.strip():
        name = pre_normalized.strip().lower()
    else:
        name = raw_name.strip().lower()

        # -----------------------------------------------------------------------
        # Step 2: Expand abbreviations (only when no pre-normalized name)
        # -----------------------------------------------------------------------
        # Receipt abbreviations are specific to store POS systems. The AI extraction
        # prompt typically already expands these, so we only need this step for
        # raw receipt text. We sort by length (longest first) so multi-word
        # abbreviations like "sw pot" are matched before "sw".
        abbreviations = config.get("abbreviations", {})
        abbrevs = {
            k.lower(): v.lower()
            for k, v in abbreviations.items()
            if not k.startswith("_")
        }
        # Sort by length (longest first) to match multi-word abbreviations first
        for abbrev in sorted(abbrevs.keys(), key=len, reverse=True):
            # Use word boundary matching to avoid replacing inside other words
            pattern = r"\b" + re.escape(abbrev) + r"\b"
            name = re.sub(pattern, abbrevs[abbrev], name)

    # -----------------------------------------------------------------------
    # Step 2.5: Early alias check (before stripping)
    # -----------------------------------------------------------------------
    # Some food names contain words that are also packaging/qualifier terms.
    # For example, "bay leaves" contains "leaves" (a packaging term), but
    # "bay leaves" is a valid food name. By checking aliases BEFORE stripping,
    # we catch these cases. If an alias matches now, we use it and skip the
    # stripping steps entirely — the alias already gives us the canonical name.
    reverse_aliases = _build_reverse_alias_map(config)
    if name in reverse_aliases:
        return reverse_aliases[name]

    # -----------------------------------------------------------------------
    # Step 3: Strip qualifier terms (marketing, diet, sourcing, freshness)
    # -----------------------------------------------------------------------
    # These words describe how food is produced/marketed, not what it IS.
    # "Organic free-range eggs" and "eggs" are the same food for matching.
    qualifiers = _flatten_strip_terms(config.get("qualifiers_to_strip", {}))
    for term in qualifiers:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        name = re.sub(pattern, "", name)

    # -----------------------------------------------------------------------
    # Step 4: Strip packaging terms (containers, produce units, portions)
    # -----------------------------------------------------------------------
    # These describe how food is SOLD, not what it is. "1 bag of flour"
    # and "flour" are the same food.
    packaging = _flatten_strip_terms(config.get("packaging_terms_to_strip", {}))
    for term in packaging:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        name = re.sub(pattern, "", name)

    # -----------------------------------------------------------------------
    # Step 5: Strip size/weight patterns (embedded measurements)
    # -----------------------------------------------------------------------
    # Receipts include package sizes because that's how stores track SKUs.
    # "Milk 1gal" and "Milk" are the same food — the size is about the
    # package, not the product.
    size_patterns = _flatten_size_patterns(config.get("size_patterns_to_strip", {}))
    for pattern in size_patterns:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)

    # -----------------------------------------------------------------------
    # Step 6: Clean up whitespace left from stripping
    # -----------------------------------------------------------------------
    # After removing terms, we may have extra spaces: "  butter  " → "butter"
    name = re.sub(r"\s+", " ", name).strip()

    # -----------------------------------------------------------------------
    # Step 7: Resolve aliases to canonical names
    # -----------------------------------------------------------------------
    # This is the final and most important step. After cleaning, check if the
    # name matches any known alias and map it to the canonical form.
    # "whole milk" → "milk", "baby spinach" → "spinach"
    if name in reverse_aliases:
        name = reverse_aliases[name]

    # -----------------------------------------------------------------------
    # Step 8: Guard against empty results
    # -----------------------------------------------------------------------
    # If aggressive stripping removed ALL words (e.g., "roll" is both a food
    # name and a packaging term), fall back to the pre-normalized or raw name.
    # An empty normalized name would break join keys and matching.
    if not name:
        if pre_normalized and pre_normalized.strip():
            name = pre_normalized.strip().lower()
        else:
            name = raw_name.strip().lower()

    return name


def extract_food_category(name: str, existing_category: str | None = None) -> str:
    """
    Determine the food category for a normalized food name.

    CATEGORY ASSIGNMENT STRATEGY
    1. If the source data already provides a valid category, use it (after
       normalizing to lowercase). The data collector often knows best.
    2. If no category is provided, look up the food name in the config's
       food_categories section. Each category lists example foods that belong to it.
    3. If still no match, fall back to "other". Students can fix this by adding
       the food to the appropriate category in config/normalization_mappings.json.

    Parameters:
        name: The normalized food name (e.g., "chicken breast").
        existing_category: A category provided by the source data (e.g., "protein").
                           May be None if the source didn't include one.

    Returns:
        A standardized category string (e.g., "protein", "dairy", "grain", "other").
    """
    config = load_normalization_config()
    food_categories = config.get("food_categories", {})

    # Collect all valid category names (excluding the _description key)
    valid_categories = {
        k.lower() for k in food_categories.keys() if not k.startswith("_")
    }

    # -----------------------------------------------------------------------
    # Option 1: Use existing category if it's valid AND specific
    # -----------------------------------------------------------------------
    # We accept the source category only if it's a real category (not "other").
    # "other" is a catch-all fallback — if the source says "other", we should
    # try to find a better category from the config before accepting it.
    if (
        existing_category
        and existing_category.strip().lower() in valid_categories
        and existing_category.strip().lower() != "other"
    ):
        return existing_category.strip().lower()

    # -----------------------------------------------------------------------
    # Option 2: Look up the food name in config's food_categories
    # -----------------------------------------------------------------------
    # Each category maps to a list of example foods. We search all categories
    # to find which one contains this food name.
    name_lower = name.lower()
    for category, foods in food_categories.items():
        if category.startswith("_"):
            continue
        if isinstance(foods, list) and name_lower in [f.lower() for f in foods]:
            return category.lower()

    # -----------------------------------------------------------------------
    # Option 3: Check if it's a canonical name in the aliases (which have categories)
    # -----------------------------------------------------------------------
    # If the name is a canonical name from name_aliases, we can find its category
    # by checking which category list contains it
    # (Already covered by the loop above if the canonical name is in food_categories)

    # -----------------------------------------------------------------------
    # Fallback: "other"
    # -----------------------------------------------------------------------
    # If we can't determine the category, return "other". Students should add
    # this food to the appropriate category in config/normalization_mappings.json.
    return "other"


def load_config_to_sql():
    """
    Load normalization rules from config/normalization_mappings.json into the
    NormalizationMapping SQL table.

    THE "CONFIG FILE AS SOURCE OF TRUTH, SQL TABLE AS QUERYABLE CACHE" PATTERN
    This demonstrates a common data architecture pattern:
      - The JSON config file is the SINGLE SOURCE OF TRUTH for normalization rules.
        Students edit this file to add aliases, categories, etc.
      - The SQL table is a QUERYABLE CACHE of the same data. It enables SQL joins
        and lookups that would be awkward or slow to do in Python.
      - This function SYNCS from file to table — it drops and recreates all rows
        to ensure the table matches the file exactly.
      - If the table gets out of sync, just re-run this function.

    WHY BOTH FILE AND TABLE?
      - File: human-readable, version-controlled, easy to diff and review
      - Table: SQL-joinable, queryable, indexed for fast lookups
      - Together: best of both worlds for an educational project

    This is called by the build_inventory pipeline (build_inventory.py) to ensure
    the SQL table is always up to date before building the inventory.
    """
    config = load_normalization_config()
    food_categories = config.get("food_categories", {})
    name_aliases = config.get("name_aliases", {})

    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        # Clear existing mappings — full rebuild from config
        existing = session.exec(select(NormalizationMapping)).all()
        for record in existing:
            session.delete(record)
        session.commit()

        count = 0

        # Build a lookup: food_name → category
        food_to_category = {}
        for category, foods in food_categories.items():
            if category.startswith("_"):
                continue
            if isinstance(foods, list):
                for food in foods:
                    food_to_category[food.lower()] = category

        # Insert alias mappings
        for canonical, aliases in name_aliases.items():
            if canonical.startswith("_"):
                continue

            category = food_to_category.get(canonical.lower(), "other")

            # Add self-reference (canonical name maps to itself)
            session.add(
                NormalizationMapping(
                    canonical_name=canonical.lower(),
                    alias=canonical.lower(),
                    category=category,
                )
            )
            count += 1

            # Add each alias
            if isinstance(aliases, list):
                for alias in aliases:
                    session.add(
                        NormalizationMapping(
                            canonical_name=canonical.lower(),
                            alias=alias.lower(),
                            category=category,
                        )
                    )
                    count += 1

        session.commit()

    print(f"  Loaded {count} normalization mappings into SQL table")


# ---------------------------------------------------------------------------
# Demo / test section — run this file directly to see normalization in action
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("FOOD NAME NORMALIZATION — DEMO")
    print("=" * 70)
    print(f"\nConfig file: {CONFIG_PATH}")
    print()

    # -----------------------------------------------------------------------
    # Test with actual receipt data
    # -----------------------------------------------------------------------
    print("RECEIPT ITEMS (raw receipt text → normalized):")
    print("-" * 60)

    receipt_examples = [
        # (raw_name, pre_normalized_from_ai)
        ("Greenwise Hmstyle Meatbal Ft", "meatball"),
        ("Sar Slcd Provolone Ft", "cheese"),
        ("Ground Round (15% Fat) Ft", "ground beef"),
        ("Publix Frsh Spinach Ft", "spinach"),
        ("Pompeian EV Olive Oil Ft", "olive oil"),
        ("Gld Mdl AP Flour 5lb Ft", "flour"),
        ("Publix Unsltd Btr Ft", "butter"),
        ("Phila Crm Chs 8oz Ft", "cream cheese"),
        ("Hass Avocados Lrg Ft", "avocado"),
        ("Barilla Spaghetti Ft", "pasta"),
        ("Bushs Blk Beans 15oz Ft", "black beans"),
        ("Qkr Old Fash Oats Ft", "oats"),
        ("Publix Lrg Eggs 12ct Ft", "egg"),
    ]

    for raw, pre_norm in receipt_examples:
        result = normalize_food_name(raw, pre_normalized=pre_norm)
        category = extract_food_category(result)
        print(f'  "{raw}"')
        print(f'    pre-normalized: "{pre_norm}" → final: "{result}" [{category}]')

    # -----------------------------------------------------------------------
    # Test with pantry data (already fairly clean)
    # -----------------------------------------------------------------------
    print()
    print("PANTRY ITEMS (already clean names → canonical):")
    print("-" * 60)

    pantry_examples = [
        "all purpose flour",
        "bread flour",
        "brown sugar",
        "chocolate chips",
        "penne pasta",
        "red lentils",
        "diced tomatoes",
        "chicken broth",
        "panko breadcrumbs",
        "bay leaves",
        "Italian seasoning",
    ]

    for name in pantry_examples:
        result = normalize_food_name(name)
        category = extract_food_category(result)
        print(f'  "{name}" → "{result}" [{category}]')

    # -----------------------------------------------------------------------
    # Test abbreviation expansion (without pre-normalized name)
    # -----------------------------------------------------------------------
    print()
    print("ABBREVIATION EXPANSION (raw receipt text without AI help):")
    print("-" * 60)

    abbrev_examples = [
        "BNLS SKNLS CHKN BRST",
        "Org Whl Milk 1gal",
        "Grnd Beef 2lb",
        "Sm Broc Bunch",
    ]

    for name in abbrev_examples:
        result = normalize_food_name(name)
        category = extract_food_category(result)
        print(f'  "{name}" → "{result}" [{category}]')

    # -----------------------------------------------------------------------
    # Load config into SQL table (demo)
    # -----------------------------------------------------------------------
    print()
    print("LOADING CONFIG INTO SQL TABLE:")
    print("-" * 60)
    load_config_to_sql()
    print("  Done! NormalizationMapping table is now populated.")
    print()
    print("=" * 70)
    print("To customize normalization, edit config/normalization_mappings.json")
    print("and re-run this pipeline.")
