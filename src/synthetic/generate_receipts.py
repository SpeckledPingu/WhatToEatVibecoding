"""
generate_receipts.py — Generate realistic synthetic receipt CSV files.

WHAT THIS SCRIPT DOES
Creates fake but realistic-looking grocery receipt data by simulating shopping
trips over a configurable number of weeks. Each trip produces a CSV file that
matches the exact format of real receipt data in data/receipts/.

HOW IT CREATES REALISTIC DATA
Real shopping isn't random — people have patterns:
  - Weekly staples (milk, eggs, bread) appear on almost every trip
  - Some items are bought biweekly (pasta, cheese) or monthly (olive oil, spices)
  - Prices fluctuate slightly from trip to trip
  - People prefer certain stores and shop on certain days
  - Seasonal items appear more often during their peak months

This script models all of these patterns using probability distributions
configured in config/synthetic_data.json. The result is data that LOOKS like
it came from real grocery shopping — not uniformly random noise.

USING random.seed() FOR REPRODUCIBILITY
Python's random module generates "pseudo-random" numbers — they look random
but follow a deterministic sequence from a starting "seed" value. By setting
the seed before generation:
  - Same seed → same data every time (useful for testing and debugging)
  - Different seed → different but equally realistic data
  - Omit the seed → truly unpredictable data each run

This is a fundamental concept in data science and simulation.

RUN IT:
    uv run python -m src.synthetic.generate_receipts
    uv run python -m src.synthetic.generate_receipts --weeks 8 --trips 3 --seed 123
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from src.synthetic.config import (
    get_all_items_flat,
    get_food_items,
    get_seasonal_adjustments,
    get_shopping_patterns,
    get_store_profiles,
    load_synthetic_config,
)


# Output directory for synthetic receipt CSVs
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "synthetic" / "receipts"

# Column names matching the real receipt CSV format exactly
RECEIPT_COLUMNS = [
    "item_name",
    "normalized_name",
    "quantity",
    "unit_price",
    "total_price",
    "category",
    "store_name",
    "purchase_date",
]


def _pick_store(stores: dict[str, dict], rng: random.Random) -> str:
    """
    Choose a store for this trip using weighted random selection.

    WEIGHTED RANDOM CHOICES
    Each store has a visit_weight (e.g., Publix=0.45, Trader Joes=0.30).
    random.choices() uses these weights to make higher-weight stores more
    likely to be picked. Over many trips, the distribution of store visits
    will approximately match the configured weights.

    This is more realistic than picking uniformly at random — most people
    have a "primary" grocery store they visit most often.
    """
    store_names = list(stores.keys())
    weights = [stores[name]["visit_weight"] for name in store_names]
    return rng.choices(store_names, weights=weights, k=1)[0]


def _pick_shopping_day(week_start: date, patterns: dict, rng: random.Random) -> date:
    """
    Pick a day of the week for this shopping trip.

    Uses day-of-week weights from the config. Most people shop on weekends
    (Saturday/Sunday weights are highest), so the generated data reflects
    this pattern. The weights don't need to sum to 1.0 — random.choices()
    normalizes them automatically.
    """
    day_weights = patterns["day_of_week_weights"]
    days = list(range(7))
    weights = [day_weights[str(d)] for d in days]
    chosen_day = rng.choices(days, weights=weights, k=1)[0]
    return week_start + timedelta(days=chosen_day)


def _should_include_item(
    item: dict,
    patterns: dict,
    seasonal: dict,
    month: int,
    rng: random.Random,
) -> bool:
    """
    Decide whether to include an item in this trip's basket.

    FREQUENCY-BASED PROBABILITY
    Each item has a frequency setting that maps to a base probability:
      - "weekly" items (milk, eggs) have ~85% chance of appearing each trip
      - "biweekly" items (pasta, cheese) have ~50% chance
      - "monthly" items (olive oil, spices) have ~20% chance
      - "occasional" items are rare at ~8%

    SEASONAL ADJUSTMENTS
    Items in the seasonal config get a probability BOOST during their peak
    months. Strawberries in June are 2x more likely than in December.
    This creates the realistic seasonal variation seen in real purchase data.
    """
    # Map frequency labels to base probabilities
    freq = item.get("frequency", "occasional")
    base_prob = {
        "weekly": patterns["weekly_staple_probability"],
        "biweekly": patterns["biweekly_probability"],
        "monthly": patterns["monthly_probability"],
        "occasional": patterns["occasional_probability"],
    }.get(freq, patterns["occasional_probability"])

    # Apply seasonal boost if applicable
    item_name = item["name"]
    if item_name in seasonal:
        adj = seasonal[item_name]
        if month in adj["peak_months"]:
            base_prob = min(1.0, base_prob * adj["boost_factor"])

    return rng.random() < base_prob


def _generate_price(item: dict, store: dict, rng: random.Random) -> float:
    """
    Generate a realistic price for an item at a specific store.

    WHY SMALL RANDOM VARIATION MAKES DATA FEEL REAL
    Real prices fluctuate slightly — the same chicken breast might be $7.49
    one week and $7.99 the next due to sales, stock rotation, or rounding.
    We model this by:
      1. Picking a base price uniformly within the item's price_range
      2. Multiplying by the store's price_factor (Costco is cheaper, etc.)
      3. Rounding to 2 decimal places (like real prices)

    The combination of range + store factor creates believable price variation
    without any single number looking suspiciously precise.
    """
    low, high = item["price_range"]
    base_price = rng.uniform(low, high)
    adjusted = base_price * store.get("price_factor", 1.0)
    return round(adjusted, 2)


def _generate_quantity(item: dict, store: dict, rng: random.Random) -> int:
    """
    Generate a purchase quantity for an item.

    Costco and other bulk stores have a qty_multiplier in their profile,
    which increases the typical quantity purchased. A normal trip might
    buy 1 carton of eggs, but a Costco trip buys 2-3.
    """
    low, high = item["typical_qty"]
    qty = rng.randint(low, high)
    # Apply bulk store multiplier (Costco buys more of each item)
    multiplier = store.get("qty_multiplier", 1.0)
    if multiplier > 1.0:
        qty = max(1, round(qty * multiplier))
    return qty


def _build_basket(
    food_items: dict[str, list[dict]],
    store_profile: dict,
    patterns: dict,
    seasonal: dict,
    month: int,
    rng: random.Random,
) -> list[dict]:
    """
    Build a shopping basket (list of items) for one trip.

    The basket is built by iterating through all possible items and using
    probability to decide which ones to include. Store category_weights
    adjust probabilities — a Farmers Market is more likely to include produce,
    while Costco skews toward proteins and bulk items.

    After selection, if the basket is too small or too large, items are
    randomly added or removed to stay within the configured range. This
    ensures every trip looks like a realistic shopping trip (10-25 items).
    """
    basket = []
    min_items, max_items = patterns["items_per_trip_range"]
    category_weights = store_profile.get("category_weights", {})

    for category, items in food_items.items():
        # Store's affinity for this category adjusts inclusion probability
        cat_weight = category_weights.get(category, 1.0)

        for item in items:
            # Temporarily boost the item's frequency probability by category weight
            if _should_include_item(item, patterns, seasonal, month, rng):
                # Apply category weight as an additional filter
                if rng.random() < cat_weight:
                    basket.append({**item, "category": category})

    # Ensure basket size is within realistic range
    if len(basket) > max_items:
        # Trim to max, but keep weekly staples (they're always purchased)
        staples = [i for i in basket if i.get("frequency") == "weekly"]
        non_staples = [i for i in basket if i.get("frequency") != "weekly"]
        rng.shuffle(non_staples)
        basket = staples + non_staples[: max_items - len(staples)]

    if len(basket) < min_items:
        # Add more items to reach minimum — pick from items not already in basket
        all_items = []
        for category, items in food_items.items():
            for item in items:
                all_items.append({**item, "category": category})
        basket_names = {i["name"] for i in basket}
        available = [i for i in all_items if i["name"] not in basket_names]
        rng.shuffle(available)
        basket.extend(available[: min_items - len(basket)])

    return basket


def generate_receipts(
    num_weeks: int = 4,
    trips_per_week: int = 2,
    start_date: date | None = None,
    seed: int = 42,
) -> list[Path]:
    """
    Generate synthetic receipt CSV files simulating grocery shopping.

    Parameters:
        num_weeks: Number of weeks to simulate (4 = ~1 month of shopping)
        trips_per_week: Average shopping trips per week (with slight random variation)
        start_date: First day of the simulation period (defaults to num_weeks ago)
        seed: Random seed for reproducible generation (same seed = same data)

    Returns:
        List of Path objects pointing to the generated CSV files.

    Each generated CSV matches the format in data/receipts/:
        item_name, normalized_name, quantity, unit_price, total_price,
        category, store_name, purchase_date
    """
    # Initialize random number generator with seed for reproducibility
    # Using a dedicated Random instance instead of the global random.seed()
    # prevents interference with other code that uses random numbers
    rng = random.Random(seed)

    # Load all configuration
    config = load_synthetic_config()
    food_items = get_food_items(config)
    stores = get_store_profiles(config)
    patterns = get_shopping_patterns(config)
    seasonal = get_seasonal_adjustments(config)

    # Default start date: num_weeks ago from today
    if start_date is None:
        start_date = date.today() - timedelta(weeks=num_weeks)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated_files = []
    # Track totals for the summary report
    store_stats: dict[str, dict] = {}

    print(f"\nGenerating synthetic receipts...")
    print(f"  Period: {start_date} to {start_date + timedelta(weeks=num_weeks)}")
    print(f"  Weeks: {num_weeks}, Target trips/week: {trips_per_week}, Seed: {seed}")

    for week_num in range(num_weeks):
        week_start = start_date + timedelta(weeks=week_num)

        # Slight variation in trips per week (±1) to avoid robotic regularity
        actual_trips = max(1, trips_per_week + rng.randint(-1, 1))

        for trip_num in range(actual_trips):
            # Pick a store and a day for this trip
            store_name = _pick_store(stores, rng)
            store_profile = stores[store_name]
            trip_date = _pick_shopping_day(week_start, patterns, rng)

            # Build the shopping basket
            basket = _build_basket(
                food_items, store_profile, patterns, seasonal, trip_date.month, rng
            )

            # Generate receipt rows
            rows = []
            trip_total = 0.0

            for item in basket:
                quantity = _generate_quantity(item, store_profile, rng)
                unit_price = _generate_price(item, store_profile, rng)
                total_price = round(unit_price * quantity, 2)
                trip_total += total_price

                rows.append({
                    "item_name": item["name"],
                    "normalized_name": item["name"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "category": item["category"],
                    "store_name": store_name,
                    "purchase_date": trip_date.isoformat(),
                })

            # Write CSV file — name format: synthetic_{store}_{date}.csv
            safe_store_name = store_name.lower().replace(" ", "_")
            filename = f"synthetic_{safe_store_name}_{trip_date.isoformat()}.csv"
            filepath = OUTPUT_DIR / filename

            # Handle duplicate filenames (multiple trips to same store on same day)
            counter = 2
            while filepath.exists():
                filename = f"synthetic_{safe_store_name}_{trip_date.isoformat()}_{counter}.csv"
                filepath = OUTPUT_DIR / filename
                counter += 1

            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=RECEIPT_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

            generated_files.append(filepath)

            # Update store statistics
            if store_name not in store_stats:
                store_stats[store_name] = {"trips": 0, "items": 0, "total": 0.0}
            store_stats[store_name]["trips"] += 1
            store_stats[store_name]["items"] += len(rows)
            store_stats[store_name]["total"] += trip_total

    # Print generation summary
    total_items = sum(s["items"] for s in store_stats.values())
    total_spent = sum(s["total"] for s in store_stats.values())

    print(f"\nGenerated {len(generated_files)} shopping trips over {num_weeks} weeks:")
    for store_name, stats in sorted(store_stats.items()):
        print(
            f"  - {store_name}: {stats['trips']} trips, "
            f"{stats['items']} items, ${stats['total']:.2f} total"
        )
    print(f"Total: {total_items} items across {len(generated_files)} trips (${total_spent:.2f})")
    print(f"Files saved to {OUTPUT_DIR}/")

    return generated_files


# ---------------------------------------------------------------------------
# Run directly: python -m src.synthetic.generate_receipts
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic grocery receipt data",
    )
    parser.add_argument("--weeks", type=int, default=4, help="Number of weeks to simulate")
    parser.add_argument("--trips", type=int, default=2, help="Average trips per week")
    parser.add_argument("--start-date", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()

    start = date.fromisoformat(args.start_date) if args.start_date else None
    generate_receipts(
        num_weeks=args.weeks,
        trips_per_week=args.trips,
        start_date=start,
        seed=args.seed,
    )
