"""
generate_pantry.py — Generate a realistic synthetic pantry snapshot CSV.

WHAT THIS SCRIPT DOES
Creates a fake but realistic-looking pantry inventory snapshot — a point-in-time
list of what's in your kitchen. The output CSV matches the exact format of real
pantry data in data/pantry/.

SNAPSHOT VS. TRANSACTION DATA
This is a key data modeling concept:
  - RECEIPTS are TRANSACTION data (events): "I bought chicken on March 5th"
  - PANTRY is SNAPSHOT data (state): "Right now I have chicken in the fridge"

Transactions accumulate over time — you never delete a receipt. Snapshots are
replaced — each new inventory replaces the old one. They answer different
questions:
  - Transactions: "How much did I spend last month?" (history)
  - Snapshots: "What can I cook tonight?" (current state)

This distinction matters for database design, API design, and analytics. The
synthetic data generation models both types.

HOW PANTRY GENERATION WORKS
1. Start with the full food item list from the config
2. Randomly select a fraction of items to be "in stock" (controlled by fullness)
3. Weight selection toward weekly staples (more likely to be present)
4. For each item: generate quantity, assign location, assign condition
5. Use informal/short names (like a real person scanning their kitchen)

RUN IT:
    uv run python -m src.synthetic.generate_pantry
    uv run python -m src.synthetic.generate_pantry --fullness 0.5 --seed 99
"""

import argparse
import csv
import random
from datetime import date
from pathlib import Path

from src.synthetic.config import (
    get_all_items_flat,
    get_pantry_settings,
    load_synthetic_config,
)


# Output directory for synthetic pantry CSVs
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic" / "pantry"

# Column names matching the real pantry CSV format exactly
PANTRY_COLUMNS = [
    "item_name",
    "quantity",
    "unit",
    "location",
    "condition",
    "category",
    "date_inventoried",
    "notes",
]


def _assign_location(category: str, pantry_settings: dict, rng: random.Random) -> str:
    """
    Assign a storage location based on the item's category.

    Most items go to their "natural" location (protein → fridge, grain → pantry),
    but there's a small chance items end up elsewhere. For example, you might
    have bread in the freezer or fruit in the fridge instead of the counter.
    """
    natural_location = pantry_settings["location_by_category"].get(category, "pantry")

    # 15% chance the item is in a non-default location (realistic variation)
    if rng.random() < 0.15:
        alternate_locations = ["fridge", "freezer", "pantry", "counter"]
        alternate_locations = [loc for loc in alternate_locations if loc != natural_location]
        return rng.choice(alternate_locations)

    return natural_location


def _assign_condition(location: str, pantry_settings: dict, rng: random.Random) -> str:
    """
    Assign a condition based on the storage location.

    Items in the fridge might be "good", "opened", or "wilting" (for produce).
    Frozen items are usually "frozen". Pantry items are often "opened" since
    packages get used over time. These probabilities are configured in JSON.
    """
    conditions = pantry_settings["condition_probabilities"].get(
        location, {"good": 1.0}
    )
    # Filter out metadata keys
    conditions = {k: v for k, v in conditions.items() if not k.startswith("_")}

    names = list(conditions.keys())
    weights = list(conditions.values())
    return rng.choices(names, weights=weights, k=1)[0]


def _generate_pantry_quantity(
    item: dict,
    pantry_settings: dict,
    rng: random.Random,
) -> float:
    """
    Generate a realistic quantity for a pantry item.

    Pantry items are often partially consumed — you don't always have a full
    bag of flour or a complete gallon of milk. The quantity_consumed_range
    setting controls how much might be used (0.1 = 10% consumed, 1.0 = full).

    Weekly staples tend to be more depleted since they're used frequently.
    Monthly items are more likely to be near-full since they last longer.
    """
    low, high = item.get("typical_qty", [1, 1])
    base_qty = rng.uniform(low, high)

    # Apply consumption — partially used items are realistic
    consumed_low, consumed_high = pantry_settings["quantity_consumed_range"]
    remaining_fraction = rng.uniform(consumed_low, consumed_high)

    # Weekly staples are more likely to be depleted
    if item.get("frequency") == "weekly":
        remaining_fraction *= rng.uniform(0.3, 0.9)

    quantity = round(base_qty * remaining_fraction, 2)
    return max(0.1, quantity)  # Always at least a little left


def _generate_note(item: dict, condition: str, rng: random.Random) -> str:
    """
    Generate a realistic note for a pantry item.

    Real pantry inventories have informal notes — "about half full",
    "expires soon", "behind the ketchup". These add realism and demonstrate
    free-text data handling.
    """
    # Most items don't have notes (only ~30% do)
    if rng.random() > 0.30:
        return ""

    # Pick a contextual note based on condition
    notes_by_condition = {
        "good": [
            "unopened",
            "just bought",
            "plenty left",
            "full package",
            "",
        ],
        "opened": [
            "about half full",
            "almost empty",
            "bag clipped shut",
            "resealable bag",
            "about 3/4 full",
            "use soon",
        ],
        "wilting": [
            "use today",
            "still okay to cook",
            "getting soft",
            "needs to be used up",
        ],
        "frozen": [
            "from last month",
            "double wrapped",
            "in freezer bag",
            "frozen from fresh",
        ],
        "sealed": [
            "brand new",
            "backup supply",
            "bought on sale",
        ],
    }

    options = notes_by_condition.get(condition, [""])
    return rng.choice(options)


def generate_pantry_snapshot(
    snapshot_date: date | None = None,
    fullness: float = 0.7,
    seed: int = 42,
) -> Path:
    """
    Generate a synthetic pantry inventory snapshot CSV.

    Parameters:
        snapshot_date: The date this inventory was taken (defaults to today).
        fullness: Fraction of possible items that are in stock (0.0 = empty
                  kitchen, 1.0 = fully stocked). A typical kitchen has ~70%
                  of common items in stock at any given time.
        seed: Random seed for reproducible generation.

    Returns:
        Path to the generated CSV file.

    The generated CSV matches the format in data/pantry/:
        item_name, quantity, unit, location, condition, category,
        date_inventoried, notes
    """
    rng = random.Random(seed)

    config = load_synthetic_config()
    all_items = get_all_items_flat(config)
    pantry_settings = get_pantry_settings(config)

    if snapshot_date is None:
        snapshot_date = date.today()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Select which items are "in stock" based on fullness
    # Weight toward weekly staples — they're more likely to be present
    num_items = max(1, round(len(all_items) * fullness))

    # Create selection weights — weekly items get higher weight
    frequency_weights = {
        "weekly": 3.0,
        "biweekly": 2.0,
        "monthly": 1.0,
        "occasional": 0.5,
    }
    weights = [
        frequency_weights.get(item.get("frequency", "occasional"), 0.5)
        for item in all_items
    ]

    # Weighted sampling without replacement (select unique items)
    # Since random.sample doesn't support weights, we simulate it
    selected_items = []
    available = list(range(len(all_items)))
    available_weights = list(weights)

    for _ in range(min(num_items, len(all_items))):
        if not available:
            break
        chosen_idx = rng.choices(range(len(available)), weights=available_weights, k=1)[0]
        selected_items.append(all_items[available[chosen_idx]])
        available.pop(chosen_idx)
        available_weights.pop(chosen_idx)

    # Generate rows for each selected item
    rows = []
    location_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}

    for item in selected_items:
        category = item["category"]
        location = _assign_location(category, pantry_settings, rng)
        condition = _assign_condition(location, pantry_settings, rng)
        quantity = _generate_pantry_quantity(item, pantry_settings, rng)
        note = _generate_note(item, condition, rng)

        rows.append({
            "item_name": item["name"],
            "quantity": quantity,
            "unit": item.get("unit", "whole"),
            "location": location,
            "condition": condition,
            "category": category,
            "date_inventoried": snapshot_date.isoformat(),
            "notes": note,
        })

        # Track statistics
        location_counts[location] = location_counts.get(location, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1

    # Write CSV file
    filename = f"synthetic_pantry_{snapshot_date.isoformat()}.csv"
    filepath = OUTPUT_DIR / filename

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PANTRY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    # Print summary
    print(f"\nGenerated synthetic pantry snapshot:")
    print(f"  Date: {snapshot_date}")
    print(f"  Fullness: {fullness:.0%} ({len(selected_items)} of {len(all_items)} possible items)")
    print(f"  Seed: {seed}")

    print(f"\n  Items by category:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")

    print(f"\n  Items by location:")
    for loc, count in sorted(location_counts.items(), key=lambda x: -x[1]):
        print(f"    {loc}: {count}")

    print(f"\n  File saved to {filepath}")

    return filepath


# ---------------------------------------------------------------------------
# Run directly: python -m src.synthetic.generate_pantry
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a synthetic pantry inventory snapshot",
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="Snapshot date (YYYY-MM-DD, defaults to today)",
    )
    parser.add_argument(
        "--fullness", type=float, default=0.7,
        help="Kitchen fullness 0.0-1.0 (default 0.7 = 70%% stocked)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()

    snap_date = date.fromisoformat(args.date) if args.date else None
    generate_pantry_snapshot(
        snapshot_date=snap_date,
        fullness=args.fullness,
        seed=args.seed,
    )
