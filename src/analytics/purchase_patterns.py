"""
purchase_patterns.py — Analyze receipt data to find purchasing trends.

WHAT THIS SCRIPT DOES
This script examines your receipt data to answer questions like:
  - What items do you buy most often?
  - How much do you spend at each store?
  - What are the most expensive items you purchase?
  - Which food categories consume most of your budget?

It also generates matplotlib charts saved as PNG files in docs/charts/.

WHY PANDAS FOR THIS?
Pandas excels at exactly this kind of analysis:
  - groupby() to split data by store, category, or item
  - agg() to compute totals, averages, and counts in one operation
  - value_counts() for frequency analysis
  - sort_values() to rank results

MATPLOTLIB BASICS
Matplotlib is Python's foundational charting library. The key concepts:
  - Figure: the overall window/image containing one or more charts
  - Axes: a single chart within the figure (x-axis, y-axis, plot area)
  - plt.savefig(): saves the figure to a PNG file (for reports/docs)
  - plt.show(): opens an interactive window (for Jupyter/live exploration)
We use both: save to file AND show if running interactively (like in Jupyter).

RUN IT:
    uv run python -m src.analytics.purchase_patterns
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend (safe for scripts)
import matplotlib.pyplot as plt
import pandas as pd
from sqlmodel import Session, select

from src.database import create_db_and_tables, get_engine
from src.models.receipt import Receipt

# ---------------------------------------------------------------------------
# Output directory for saved charts
# ---------------------------------------------------------------------------
CHARTS_DIR = Path(__file__).parent.parent.parent / "docs" / "charts"


def load_receipts() -> pd.DataFrame:
    """
    Load all receipt records from the database into a pandas DataFrame.

    Returns:
        DataFrame with all receipt columns, or an empty DataFrame if no data.
    """
    engine = get_engine()
    create_db_and_tables(engine)

    with Session(engine) as session:
        rows = session.exec(select(Receipt)).all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in rows])


def analyze_purchase_frequency(df: pd.DataFrame):
    """
    Find the most frequently purchased items across all receipts.

    HOW value_counts() WORKS
    value_counts() counts how many times each unique value appears in a column.
    It returns a Series sorted by frequency (most common first). This is the
    simplest way to answer "what do I buy most often?"

    We use normalized_name when available because raw item_name values are
    messy receipt abbreviations (e.g., "Greenwise Hmstyle Meatbal Ft").
    """
    print("\n--- MOST FREQUENTLY PURCHASED ITEMS ---")

    # Use normalized_name if available, otherwise fall back to item_name
    name_col = "normalized_name" if "normalized_name" in df.columns else "item_name"

    # Drop NaN values before counting (some rows may not have a normalized name)
    names = df[name_col].dropna()

    # value_counts() counts occurrences of each unique value
    item_counts = names.value_counts()

    print(f"\nTop 15 most purchased items:")
    for rank, (item, count) in enumerate(item_counts.head(15).items(), 1):
        print(f"  {rank:2d}. {item} (purchased {count} time(s))")

    return item_counts


def analyze_spending_by_store(df: pd.DataFrame):
    """
    Calculate total and average spending per store.

    HOW groupby() + agg() WORKS
    groupby("store_name") splits the DataFrame into groups — one group per store.
    Then agg() applies MULTIPLE aggregation functions to each group at once:
      - "sum" adds up all values in the group
      - "mean" computes the average
      - "count" counts how many rows are in the group

    This is like creating a pivot table in Excel — you choose which column to
    group by and which calculations to perform.
    """
    print("\n--- SPENDING BY STORE ---")

    if "total_price" not in df.columns or df["total_price"].dropna().empty:
        print("  No price data available in receipts.")
        return pd.DataFrame()

    # groupby() splits by store, agg() computes multiple stats at once
    store_spending = df.groupby("store_name")["total_price"].agg(
        total_spent="sum",        # Sum all prices for each store
        avg_per_item="mean",      # Average price per line item
        items_purchased="count",  # How many line items per store
    ).sort_values("total_spent", ascending=False)

    for store, row in store_spending.iterrows():
        print(
            f"  {store}: ${row['total_spent']:.2f} total, "
            f"${row['avg_per_item']:.2f} avg/item, "
            f"{int(row['items_purchased'])} items"
        )

    return store_spending


def analyze_expensive_items(df: pd.DataFrame):
    """
    Find the most expensive individual items purchased.

    HOW sort_values() WORKS
    sort_values("column", ascending=False) sorts the DataFrame by a column,
    with the largest values first. Combined with .head(10), this gives us
    the top 10 most expensive items.
    """
    print("\n--- MOST EXPENSIVE ITEMS ---")

    if "total_price" not in df.columns or df["total_price"].dropna().empty:
        print("  No price data available in receipts.")
        return

    # Drop rows where total_price is NaN, then sort descending
    priced = df.dropna(subset=["total_price"])
    top_expensive = priced.sort_values("total_price", ascending=False).head(10)

    name_col = "normalized_name" if "normalized_name" in df.columns else "item_name"

    for rank, (_, row) in enumerate(top_expensive.iterrows(), 1):
        name = row[name_col] if pd.notna(row.get(name_col)) else row["item_name"]
        print(f"  {rank:2d}. {name} — ${row['total_price']:.2f}")


def analyze_category_spending(df: pd.DataFrame):
    """
    Break down spending by food category.

    HOW groupby() WITH MULTIPLE AGGREGATIONS WORKS
    Here we group by "category" and aggregate the "total_price" column:
      - sum: total spent in each category
      - count: number of items purchased in each category
    This reveals where your food budget actually goes.
    """
    print("\n--- SPENDING BY CATEGORY ---")

    if "category" not in df.columns or "total_price" not in df.columns:
        print("  No category or price data available.")
        return pd.DataFrame()

    has_data = df.dropna(subset=["category", "total_price"])
    if has_data.empty:
        print("  No items have both category and price data.")
        return pd.DataFrame()

    # groupby category, then aggregate total_price
    cat_spending = has_data.groupby("category")["total_price"].agg(
        total_spent="sum",
        item_count="count",
    ).sort_values("total_spent", ascending=False)

    # Calculate percentage of total spending
    grand_total = cat_spending["total_spent"].sum()
    cat_spending["pct_of_total"] = (
        cat_spending["total_spent"] / grand_total * 100
    )

    for cat, row in cat_spending.iterrows():
        print(
            f"  {cat}: ${row['total_spent']:.2f} "
            f"({row['pct_of_total']:.0f}%, {int(row['item_count'])} items)"
        )

    return cat_spending


def analyze_purchase_regularity(df: pd.DataFrame):
    """
    Identify items purchased on every trip vs. occasionally.

    HOW nunique() WORKS
    nunique() counts the number of UNIQUE values in a group. By grouping
    by item name and counting unique source_file values, we find out how
    many different receipt files (shopping trips) included each item.
    Items appearing on many trips are "regulars" — staples you always buy.
    """
    print("\n--- PURCHASE REGULARITY ---")

    name_col = "normalized_name" if "normalized_name" in df.columns else "item_name"
    names = df.dropna(subset=[name_col])

    if names.empty:
        print("  No item data available.")
        return

    # Count how many unique shopping trips each item appears on
    # nunique() = number of unique values
    trip_counts = (
        names.groupby(name_col)["source_file"]
        .nunique()
        .sort_values(ascending=False)
    )

    total_trips = df["source_file"].nunique()
    print(f"\n  Total shopping trips: {total_trips}")

    # Items bought on every (or most) trips
    regulars = trip_counts[trip_counts >= max(1, total_trips * 0.5)]
    if not regulars.empty:
        print(f"\n  Regulars (bought on 50%+ of trips):")
        for item, trips in regulars.items():
            print(f"    {item}: {trips}/{total_trips} trips")

    # Items bought only once
    one_timers = trip_counts[trip_counts == 1]
    if not one_timers.empty and total_trips > 1:
        print(f"\n  One-time purchases ({len(one_timers)} items):")
        for item in list(one_timers.index)[:10]:
            print(f"    {item}")
        if len(one_timers) > 10:
            print(f"    ... and {len(one_timers) - 10} more")


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

def plot_top_purchased(item_counts: pd.Series):
    """
    Create a bar chart of the top 15 most purchased items.

    MATPLOTLIB ANATOMY
    - plt.subplots() creates a Figure (the window) and Axes (the chart area)
    - ax.barh() draws horizontal bars (easier to read item names)
    - ax.set_xlabel/ylabel/title() label the chart
    - plt.tight_layout() adjusts spacing so labels don't get cut off
    - plt.savefig() writes the chart to a PNG file
    """
    if item_counts.empty:
        return

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    top = item_counts.head(15)

    # Create figure and axes — figsize=(width, height) in inches
    fig, ax = plt.subplots(figsize=(10, 6))

    # barh() draws horizontal bars — reversed so the most common is at the top
    ax.barh(
        range(len(top)),            # y-positions for each bar
        top.values[::-1],           # bar lengths (reversed for top-to-bottom)
        color="#3498db",            # bar color (a nice blue)
        edgecolor="white",          # thin white border between bars
    )

    # Set y-axis tick labels to item names (reversed to match bars)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(top.index[::-1])

    # Label axes and title
    ax.set_xlabel("Number of Purchases")
    ax.set_title("Top 15 Most Purchased Items")

    # tight_layout() prevents labels from being cut off at the edges
    plt.tight_layout()

    # Save to file — dpi=150 gives good resolution for viewing
    output_path = CHARTS_DIR / "top_purchased_items.png"
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close()  # Close to free memory (important in scripts)
    print(f"\n  Chart saved: {output_path}")


def plot_spending_by_category(cat_spending: pd.DataFrame):
    """
    Create a pie chart of spending by category.

    PIE CHART TIPS
    - Use autopct to show percentages on each slice
    - startangle=90 rotates so the first slice starts at 12 o'clock
    - Pie charts work best with 3-8 slices; more than that gets hard to read
    """
    if cat_spending.empty:
        return

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 8))

    # Create the pie chart
    wedges, texts, autotexts = ax.pie(
        cat_spending["total_spent"],      # Slice sizes
        labels=cat_spending.index,        # Slice labels (category names)
        autopct="%1.0f%%",               # Show percentages on slices
        startangle=90,                    # Start at 12 o'clock
        colors=plt.cm.Set3.colors[:len(cat_spending)],  # Color palette
    )

    # Make percentage text easier to read
    for autotext in autotexts:
        autotext.set_fontsize(9)

    ax.set_title("Spending by Category")

    plt.tight_layout()
    output_path = CHARTS_DIR / "spending_by_category.png"
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {output_path}")


def plot_spending_by_store(store_spending: pd.DataFrame):
    """
    Create a bar chart of spending by store.

    BAR CHART vs. PIE CHART
    Bar charts are better than pie charts when:
      - You want to compare exact values (bars are easier to compare than angles)
      - You have many categories (pie charts get cluttered past 6-8 slices)
      - You want to show both totals and averages
    """
    if store_spending.empty or len(store_spending) < 1:
        return

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))

    # Vertical bars for stores
    bars = ax.bar(
        store_spending.index,
        store_spending["total_spent"],
        color="#2ecc71",            # Green for money
        edgecolor="white",
    )

    # Add dollar amount labels on top of each bar
    for bar, amount in zip(bars, store_spending["total_spent"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,  # Center horizontally
            bar.get_height() + 0.5,              # Just above the bar
            f"${amount:.2f}",                    # Dollar format
            ha="center",                         # Horizontal alignment
            fontsize=10,
        )

    ax.set_ylabel("Total Spent ($)")
    ax.set_title("Spending by Store")

    plt.tight_layout()
    output_path = CHARTS_DIR / "spending_by_store.png"
    plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {output_path}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("PURCHASE PATTERNS ANALYSIS")
    print("=" * 70)

    df = load_receipts()

    if df.empty:
        print("\nNo receipt data found. Run ingestion first:")
        print("  uv run python -m src.ingestion.receipts")
    else:
        print(f"\nLoaded {len(df)} receipt line items.")

        # Run analyses and collect results for charting
        item_counts = analyze_purchase_frequency(df)
        store_spending = analyze_spending_by_store(df)
        analyze_expensive_items(df)
        cat_spending = analyze_category_spending(df)
        analyze_purchase_regularity(df)

        # Generate charts
        print("\n--- GENERATING CHARTS ---")
        plot_top_purchased(item_counts)

        if isinstance(cat_spending, pd.DataFrame) and not cat_spending.empty:
            plot_spending_by_category(cat_spending)

        if isinstance(store_spending, pd.DataFrame) and not store_spending.empty:
            plot_spending_by_store(store_spending)

    print(f"\n{'=' * 70}")
    print("Analysis complete.")
