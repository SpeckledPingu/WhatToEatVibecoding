"""
synthetic_vs_real.py — Compare synthetic and real data quality.

WHAT THIS SCRIPT DOES
Evaluates whether synthetic data looks realistic by comparing it against real
data (if both exist) or analyzing synthetic data patterns on its own.

WHY VALIDATE SYNTHETIC DATA?
Synthetic data is only useful if it behaves like real data. If every receipt has
exactly 15 items and prices are suspiciously round, analysis done on that data
won't transfer to real-world scenarios. This script checks for:
  - Realistic frequency distributions (some items bought more than others)
  - Realistic price distributions (not all the same, not wildly different)
  - Category mix that matches typical grocery shopping
  - Reasonable trip sizes and spending patterns

COMPARING REAL VS SYNTHETIC
When both datasets exist, side-by-side comparison reveals whether our synthetic
generation captured the patterns in real data. Perfect overlap isn't expected
(synthetic data models general patterns, not exact behavior), but the broad
shapes should be similar.

RUN IT:
    uv run python -m src.analytics.synthetic_vs_real
"""

from datetime import date

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for saving plots without a display
import matplotlib.pyplot as plt
import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.inventory import ActiveInventory
from src.models.receipt import Receipt
from src.models.pantry import PantryItem


# ---------------------------------------------------------------------------
# Output directory for charts
# ---------------------------------------------------------------------------
from pathlib import Path
CHARTS_DIR = Path(__file__).resolve().parent.parent.parent / "notebooks" / "charts"


def load_receipts_as_df() -> pd.DataFrame:
    """Load all Receipt records into a pandas DataFrame."""
    engine = get_engine()
    create_db_and_tables(engine)
    with Session(engine) as session:
        receipts = session.exec(select(Receipt)).all()
        if not receipts:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in receipts])


def load_inventory_as_df() -> pd.DataFrame:
    """Load all ActiveInventory records into a pandas DataFrame."""
    engine = get_engine()
    with Session(engine) as session:
        items = session.exec(select(ActiveInventory)).all()
        if not items:
            return pd.DataFrame()
        return pd.DataFrame([i.model_dump() for i in items])


def split_real_synthetic(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split a DataFrame into real and synthetic subsets.

    Synthetic files are prefixed with "synthetic_" in their source_file name.
    This is how we distinguish generated data from real data without needing
    a separate column — a simple naming convention.
    """
    if "source_file" not in df.columns or df.empty:
        return df, pd.DataFrame()

    synthetic_mask = df["source_file"].str.startswith("synthetic_", na=False)
    return df[~synthetic_mask].copy(), df[synthetic_mask].copy()


def analyze_receipt_data(df: pd.DataFrame, label: str) -> dict:
    """
    Analyze a receipt DataFrame and return summary statistics.

    Returns a dictionary of metrics useful for comparison.
    """
    if df.empty:
        print(f"\n  No {label} receipt data found.")
        return {}

    stats = {}

    # Basic counts
    stats["total_items"] = len(df)
    stats["unique_items"] = df["item_name"].nunique() if "item_name" in df.columns else 0

    # Price statistics
    if "total_price" in df.columns:
        prices = pd.to_numeric(df["total_price"], errors="coerce").dropna()
        stats["avg_price"] = round(prices.mean(), 2)
        stats["median_price"] = round(prices.median(), 2)
        stats["min_price"] = round(prices.min(), 2)
        stats["max_price"] = round(prices.max(), 2)
        stats["total_spent"] = round(prices.sum(), 2)

    # Category breakdown
    if "category" in df.columns:
        stats["category_counts"] = df["category"].value_counts().to_dict()

    # Store breakdown
    if "store_name" in df.columns:
        stats["store_counts"] = df["store_name"].value_counts().to_dict()

    # Trip statistics (group by store + date = one trip)
    if "store_name" in df.columns and "purchase_date" in df.columns:
        trips = df.groupby(["store_name", "purchase_date"]).size()
        stats["num_trips"] = len(trips)
        stats["avg_items_per_trip"] = round(trips.mean(), 1)

    # Print summary
    print(f"\n  {label} Receipt Data Summary:")
    print(f"    Total line items: {stats['total_items']}")
    print(f"    Unique items: {stats['unique_items']}")
    if "avg_price" in stats:
        print(f"    Price range: ${stats['min_price']} - ${stats['max_price']}")
        print(f"    Average price: ${stats['avg_price']}")
        print(f"    Total spent: ${stats['total_spent']}")
    if "num_trips" in stats:
        print(f"    Shopping trips: {stats['num_trips']}")
        print(f"    Avg items/trip: {stats['avg_items_per_trip']}")
    if "category_counts" in stats:
        print(f"    Category breakdown:")
        for cat, count in sorted(stats["category_counts"].items(), key=lambda x: -x[1]):
            pct = count / stats["total_items"] * 100
            print(f"      {cat}: {count} ({pct:.1f}%)")
    if "store_counts" in stats:
        print(f"    Store breakdown:")
        for store, count in sorted(stats["store_counts"].items(), key=lambda x: -x[1]):
            print(f"      {store}: {count} items")

    return stats


def create_comparison_charts(
    real_stats: dict,
    synthetic_stats: dict,
) -> None:
    """
    Create side-by-side matplotlib charts comparing real vs synthetic data.

    These visualizations make it easy to spot differences in the distributions.
    If synthetic data is well-calibrated, the bar heights should be roughly
    proportional (not identical, since datasets may differ in size).
    """
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    has_real = bool(real_stats)
    has_synthetic = bool(synthetic_stats)

    if not has_real and not has_synthetic:
        print("\n  No data available for charts.")
        return

    # Chart 1: Category distribution comparison
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Category Distribution: Real vs Synthetic", fontsize=14)

    for ax, stats, label in [
        (axes[0], real_stats, "Real"),
        (axes[1], synthetic_stats, "Synthetic"),
    ]:
        if not stats or "category_counts" not in stats:
            ax.text(0.5, 0.5, f"No {label} data", ha="center", va="center", fontsize=12)
            ax.set_title(label)
            continue

        cats = stats["category_counts"]
        total = sum(cats.values())
        categories = sorted(cats.keys())
        percentages = [cats.get(c, 0) / total * 100 for c in categories]

        ax.barh(categories, percentages, color="steelblue" if label == "Real" else "coral")
        ax.set_xlabel("Percentage of Items")
        ax.set_title(f"{label} Data ({total} items)")
        ax.set_xlim(0, max(percentages) * 1.2 if percentages else 10)

    plt.tight_layout()
    chart_path = CHARTS_DIR / "synthetic_vs_real_categories.png"
    plt.savefig(chart_path, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"\n  Saved category chart to {chart_path}")

    # Chart 2: Price distribution (if available)
    if (has_real and "avg_price" in real_stats) or (has_synthetic and "avg_price" in synthetic_stats):
        fig, ax = plt.subplots(figsize=(10, 6))

        metrics = ["avg_price", "median_price", "min_price", "max_price"]
        labels = ["Average", "Median", "Min", "Max"]
        x_pos = range(len(metrics))
        width = 0.35

        real_values = [real_stats.get(m, 0) for m in metrics] if has_real else [0] * len(metrics)
        synth_values = [synthetic_stats.get(m, 0) for m in metrics] if has_synthetic else [0] * len(metrics)

        if has_real:
            ax.bar([x - width / 2 for x in x_pos], real_values, width, label="Real", color="steelblue")
        if has_synthetic:
            ax.bar([x + width / 2 for x in x_pos], synth_values, width, label="Synthetic", color="coral")

        ax.set_ylabel("Price ($)")
        ax.set_title("Price Statistics: Real vs Synthetic")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels)
        ax.legend()

        plt.tight_layout()
        chart_path = CHARTS_DIR / "synthetic_vs_real_prices.png"
        plt.savefig(chart_path, dpi=100, bbox_inches="tight")
        plt.close()
        print(f"  Saved price chart to {chart_path}")


def analyze_synthetic_quality(synthetic_stats: dict) -> None:
    """
    Evaluate whether synthetic data has realistic properties.

    WHAT MAKES SYNTHETIC DATA LOOK REAL
    Good synthetic data has these properties:
      1. VARIED PRICES: Not all $5.00 — should have a range
      2. UNEVEN CATEGORIES: Not perfectly balanced — produce > spices in real life
      3. REASONABLE TRIP SIZES: 10-25 items, not 1 or 100
      4. PATTERN PRESENCE: Some items appear more than others (staples > luxuries)

    This function checks for obvious signs that data is too uniform or too random.
    """
    if not synthetic_stats:
        print("\n  No synthetic data to evaluate.")
        return

    print("\n  Synthetic Data Quality Assessment:")
    print("  " + "-" * 40)

    issues = []
    passed = []

    # Check 1: Price variation
    if "avg_price" in synthetic_stats and "min_price" in synthetic_stats:
        price_range = synthetic_stats["max_price"] - synthetic_stats["min_price"]
        if price_range < 1.0:
            issues.append("Prices have very little variation (range < $1.00)")
        elif price_range > 50:
            issues.append("Price range seems unrealistically wide (> $50)")
        else:
            passed.append(f"Price variation looks realistic (${synthetic_stats['min_price']} - ${synthetic_stats['max_price']})")

    # Check 2: Category distribution not too uniform
    if "category_counts" in synthetic_stats:
        counts = list(synthetic_stats["category_counts"].values())
        if counts:
            ratio = max(counts) / max(min(counts), 1)
            if ratio < 1.5:
                issues.append("Categories are suspiciously uniform (ratio < 1.5x)")
            else:
                passed.append(f"Category distribution is varied (max/min ratio: {ratio:.1f}x)")

    # Check 3: Trip size
    if "avg_items_per_trip" in synthetic_stats:
        avg = synthetic_stats["avg_items_per_trip"]
        if avg < 5:
            issues.append(f"Average trip size too small ({avg} items)")
        elif avg > 40:
            issues.append(f"Average trip size too large ({avg} items)")
        else:
            passed.append(f"Trip size realistic (avg {avg} items)")

    # Check 4: Multiple stores
    if "store_counts" in synthetic_stats:
        num_stores = len(synthetic_stats["store_counts"])
        if num_stores < 2:
            issues.append("Only 1 store — real shoppers usually visit multiple stores")
        else:
            passed.append(f"Multiple stores represented ({num_stores})")

    # Report
    for item in passed:
        print(f"    PASS: {item}")
    for item in issues:
        print(f"    WARN: {item}")

    if not issues:
        print("\n    Overall: Synthetic data looks realistic!")
    else:
        print(f"\n    Overall: {len(issues)} potential issue(s) to review")


def run_comparison() -> None:
    """Main function — run the full synthetic vs real comparison."""
    print("=" * 70)
    print("SYNTHETIC vs REAL DATA COMPARISON")
    print("=" * 70)

    # Load all receipt data and split by source
    all_receipts = load_receipts_as_df()

    if all_receipts.empty:
        print("\nNo receipt data found in the database.")
        print("Run the synthetic data generator first:")
        print("  uv run python -m src.synthetic.generate_all")
        return

    real_df, synthetic_df = split_real_synthetic(all_receipts)

    has_real = not real_df.empty
    has_synthetic = not synthetic_df.empty

    print(f"\nData sources found:")
    print(f"  Real data:      {'Yes' if has_real else 'No'} ({len(real_df)} records)")
    print(f"  Synthetic data: {'Yes' if has_synthetic else 'No'} ({len(synthetic_df)} records)")

    # Analyze each dataset
    real_stats = {}
    synthetic_stats = {}

    if has_real:
        real_stats = analyze_receipt_data(real_df, "Real")

    if has_synthetic:
        synthetic_stats = analyze_receipt_data(synthetic_df, "Synthetic")

    # Compare or assess quality
    if has_real and has_synthetic:
        print("\n" + "=" * 70)
        print("SIDE-BY-SIDE COMPARISON")
        print("=" * 70)

        # Compare key metrics
        print("\n  Metric                    Real          Synthetic")
        print("  " + "-" * 55)

        metrics = [
            ("Total items", "total_items", "d"),
            ("Unique items", "unique_items", "d"),
            ("Avg price", "avg_price", ".2f"),
            ("Median price", "median_price", ".2f"),
            ("Total spent", "total_spent", ".2f"),
            ("Shopping trips", "num_trips", "d"),
            ("Avg items/trip", "avg_items_per_trip", ".1f"),
        ]

        for label, key, fmt in metrics:
            real_val = real_stats.get(key, "—")
            synth_val = synthetic_stats.get(key, "—")
            real_str = f"{real_val:{fmt}}" if isinstance(real_val, (int, float)) else str(real_val)
            synth_str = f"{synth_val:{fmt}}" if isinstance(synth_val, (int, float)) else str(synth_val)
            if key in ("avg_price", "median_price", "total_spent"):
                real_str = f"${real_str}" if real_val != "—" else "—"
                synth_str = f"${synth_str}" if synth_val != "—" else "—"
            print(f"  {label:<24} {real_str:<14} {synth_str}")

        # Item overlap analysis
        if has_real and has_synthetic:
            real_items = set(real_df["item_name"].unique()) if "item_name" in real_df.columns else set()
            synth_items = set(synthetic_df["item_name"].unique()) if "item_name" in synthetic_df.columns else set()
            overlap = real_items & synth_items
            print(f"\n  Item overlap:")
            print(f"    Items in both: {len(overlap)}")
            print(f"    Real only: {len(real_items - synth_items)}")
            print(f"    Synthetic only: {len(synth_items - real_items)}")

    # Create visualizations
    print("\n" + "=" * 70)
    print("VISUALIZATIONS")
    print("=" * 70)
    create_comparison_charts(real_stats, synthetic_stats)

    # Quality assessment (always useful, even with real data)
    if has_synthetic:
        print("\n" + "=" * 70)
        print("QUALITY ASSESSMENT")
        print("=" * 70)
        analyze_synthetic_quality(synthetic_stats)

    print("\n" + "=" * 70)
    print("Comparison complete.")
    if CHARTS_DIR.exists():
        print(f"Charts saved to {CHARTS_DIR}/")


if __name__ == "__main__":
    run_comparison()
