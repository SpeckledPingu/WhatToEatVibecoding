"""
config.py — Load and provide typed access to synthetic data configuration.

WHY CONFIGURATION IS IN JSON, NOT PYTHON
The synthetic data parameters (food items, prices, store profiles, etc.) live in
config/synthetic_data.json rather than being hardcoded here. This separation
means students can customize WHAT gets generated (items, prices, patterns) by
editing a JSON file, without needing to understand or modify Python code.

WHY CONFIGURATION IS SEPARATE FROM GENERATION LOGIC
This module is a thin loading layer. It reads the JSON file and provides a
clean Python interface to the data. The actual generation logic lives in
generate_receipts.py and generate_pantry.py. This modularity means:
  - You can swap out the entire config without touching generation code
  - You can test the config loader independently
  - Multiple scripts can share the same config without duplicating load logic

HOW PROBABILITY DISTRIBUTIONS CREATE REALISTIC VARIATION
Real data is never perfectly uniform. When you buy chicken, the price isn't
always exactly $7.99 — it varies between $5.99 and $9.99 depending on the day,
the cut, and the store. The config stores these ranges, and the generation
scripts use Python's `random` module to pick values within them. This creates
data that LOOKS real because it has the natural variation of real purchases.

THE CONCEPT OF A "RANDOM SEED"
A random seed is a starting number that determines the entire sequence of
"random" numbers generated. Same seed = same sequence = same synthetic data
every time. This is crucial for:
  - REPRODUCIBILITY: You can regenerate the exact same data later
  - DEBUGGING: If something looks wrong, re-run with the same seed to reproduce
  - SHARING: Two people with the same seed get identical datasets
Change the seed to get a completely different (but equally realistic) dataset.

RUN IT:
    # This module is imported by the generation scripts, not run directly.
    # But you can test it:
    uv run python -m src.synthetic.config
"""

import json
from pathlib import Path


# Path to the synthetic data configuration file
# Using Path for cross-platform compatibility (works on Windows, Mac, Linux)
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "synthetic_data.json"


def load_synthetic_config() -> dict:
    """
    Load the synthetic data configuration from JSON.

    Returns the full configuration dictionary with these top-level keys:
      - food_items: dict of category -> list of item definitions
      - store_profiles: dict of store name -> store settings
      - shopping_patterns: trip size, day preferences, frequency probabilities
      - seasonal_adjustments: month-based item availability boosts
      - pantry_settings: location assignments, condition probabilities

    Raises FileNotFoundError if the config file is missing — this is
    intentional so you get a clear error rather than silently using defaults.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Synthetic data config not found at {CONFIG_PATH}\n"
            f"Expected location: config/synthetic_data.json\n"
            f"Run WS10 to create this file, or create it manually."
        )

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    return config


def get_food_items(config: dict) -> dict[str, list[dict]]:
    """
    Extract the food items dictionary, skipping the _description metadata key.

    Returns a dict like:
        {
            "protein": [{"name": "chicken breast", "price_range": [...], ...}, ...],
            "dairy": [...],
            ...
        }
    """
    return {
        category: items
        for category, items in config["food_items"].items()
        if not category.startswith("_")
    }


def get_all_items_flat(config: dict) -> list[dict]:
    """
    Get all food items as a flat list, each annotated with its category.

    Useful when you need to iterate over ALL items regardless of category,
    for example when building a pantry snapshot from the full item pool.
    """
    items = []
    for category, category_items in get_food_items(config).items():
        for item in category_items:
            items.append({**item, "category": category})
    return items


def get_store_profiles(config: dict) -> dict[str, dict]:
    """
    Extract store profiles, skipping the _description metadata key.

    Returns a dict like:
        {
            "Publix": {"price_factor": 1.0, "visit_weight": 0.45, ...},
            "Trader Joes": {...},
            ...
        }
    """
    return {
        name: profile
        for name, profile in config["store_profiles"].items()
        if not name.startswith("_")
    }


def get_shopping_patterns(config: dict) -> dict:
    """Extract shopping pattern settings."""
    return config["shopping_patterns"]


def get_seasonal_adjustments(config: dict) -> dict[str, dict]:
    """
    Extract seasonal adjustment rules, skipping metadata keys.

    Returns a dict like:
        {"strawberry": {"peak_months": [4, 5, 6], "boost_factor": 2.0}, ...}
    """
    return {
        name: adj
        for name, adj in config["seasonal_adjustments"].items()
        if not name.startswith("_")
    }


def get_pantry_settings(config: dict) -> dict:
    """Extract pantry snapshot generation settings."""
    return config["pantry_settings"]


# ---------------------------------------------------------------------------
# Quick test — run this module directly to verify config loads correctly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    config = load_synthetic_config()

    food_items = get_food_items(config)
    all_items = get_all_items_flat(config)
    stores = get_store_profiles(config)
    patterns = get_shopping_patterns(config)
    seasonal = get_seasonal_adjustments(config)
    pantry = get_pantry_settings(config)

    print("Synthetic Data Configuration Loaded Successfully")
    print("=" * 50)
    print(f"\nFood items by category:")
    for category, items in food_items.items():
        print(f"  {category}: {len(items)} items")
    print(f"  Total: {len(all_items)} items")

    print(f"\nStore profiles: {len(stores)}")
    for name, profile in stores.items():
        print(f"  {name}: price factor {profile['price_factor']}, visit weight {profile['visit_weight']}")

    print(f"\nShopping patterns:")
    print(f"  Items per trip: {patterns['items_per_trip_range']}")
    print(f"  Weekly staple prob: {patterns['weekly_staple_probability']}")

    print(f"\nSeasonal adjustments: {len(seasonal)} items")
    print(f"Pantry locations: {len(pantry['location_by_category'])} categories mapped")
