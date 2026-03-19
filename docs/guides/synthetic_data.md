# Synthetic Data Generation Guide

## Why Synthetic Data?

Real data takes time to accumulate. If you want to analyze purchase patterns over 3 months, you need 3 months of real receipts. Synthetic data solves this by generating realistic-looking data programmatically.

Synthetic data is used extensively in the real world for:

- **Testing**: Verify your app works with large datasets before real data exists
- **Privacy**: Share realistic data without exposing real purchase history
- **Simulation**: Model scenarios ("what if I shopped differently?")
- **Education**: Learn analytics techniques with rich datasets

## How Generation Works

### Patterns, Not Random Noise

Real shopping follows patterns. The synthetic generator models these:

1. **Weekly staples**: Milk, eggs, bread appear on almost every trip (~85% probability)
2. **Biweekly items**: Pasta, cheese are bought every other trip (~50%)
3. **Monthly items**: Olive oil, spices are replenished monthly (~20%)
4. **Store preferences**: Most people have a primary store they visit more often
5. **Day-of-week habits**: Most shopping happens on weekends
6. **Seasonal variation**: Berries in summer, squash in fall
7. **Price variation**: Slight fluctuations make data look natural

### Randomness and Seeds

The generator uses Python's `random` module with a configurable **seed**:

- **Same seed = same data**: `--seed 42` always produces identical output
- **Different seed = different data**: `--seed 99` produces different but equally realistic data
- This is called **reproducible randomness** — essential for debugging and sharing

### Two Data Types

| Type | What It Models | Example |
|------|---------------|---------|
| **Receipt** (transaction) | A shopping event | "Bought chicken at Publix on March 5th" |
| **Pantry** (snapshot) | Current kitchen state | "Right now there's chicken in the fridge" |

Receipts accumulate over time. Pantry snapshots replace each other.

## How to Configure

All generation parameters live in `config/synthetic_data.json`. Edit this file to customize what gets generated — no Python code changes needed.

### Food Items

Each item has:
```json
{
  "name": "chicken breast",
  "price_range": [5.99, 9.99],
  "unit": "pounds",
  "typical_qty": [1, 3],
  "frequency": "weekly"
}
```

- **price_range**: Prices are randomly selected within this range
- **typical_qty**: Purchase quantity varies within this range
- **frequency**: How often this item appears (weekly/biweekly/monthly/occasional)

### Store Profiles

Each store has its own pricing and product personality:
```json
{
  "Publix": {
    "price_factor": 1.0,
    "visit_weight": 0.45,
    "category_weights": {"protein": 1.2, "dairy": 1.1, ...}
  }
}
```

- **price_factor**: Multiplier on base prices (0.80 = 20% cheaper for Costco)
- **visit_weight**: How often this store is visited relative to others
- **category_weights**: Which categories are more/less likely at this store
- **qty_multiplier**: Bulk stores buy more per item (Costco = 2.0x)

### Shopping Patterns

```json
{
  "items_per_trip_range": [10, 25],
  "day_of_week_weights": {"5": 0.25, "6": 0.25, ...},
  "weekly_staple_probability": 0.85
}
```

### Seasonal Adjustments

```json
{
  "strawberry": {"peak_months": [4, 5, 6], "boost_factor": 2.0}
}
```

Items get a probability boost during their peak months.

## How to Run

### Generate Everything (Recommended)

```bash
# Default: 4 weeks, 2 trips/week, 70% pantry fullness
uv run python -m src.synthetic.generate_all

# Custom parameters
uv run python -m src.synthetic.generate_all --weeks 8 --trips 3 --fullness 0.9

# Generate data without running the pipeline
uv run python -m src.synthetic.generate_all --no-pipeline
```

### Generate Individual Components

```bash
# Just receipts
uv run python -m src.synthetic.generate_receipts --weeks 8 --seed 99

# Just pantry snapshot
uv run python -m src.synthetic.generate_pantry --fullness 0.5

# Compare synthetic vs real
uv run python -m src.analytics.synthetic_vs_real
```

### Command-Line Options

| Flag | Default | Description |
|------|---------|-------------|
| `--weeks` | 4 | Number of weeks of shopping to simulate |
| `--trips` | 2 | Average shopping trips per week |
| `--fullness` | 0.7 | Pantry stocking level (0.0 to 1.0) |
| `--seed` | 42 | Random seed for reproducibility |
| `--no-pipeline` | (off) | Skip running ingestion/normalization |

## How Synthetic Data Is Stored

```
data/
├── receipts/              ← Real receipt CSVs
│   └── synthetic_*.csv    ← Synthetic receipts (copied here for pipeline)
├── pantry/                ← Real pantry CSVs
│   └── synthetic_*.csv    ← Synthetic pantry (copied here for pipeline)
└── synthetic/             ← Original synthetic data (master copies)
    ├── receipts/          ← Generated receipt CSVs
    └── pantry/            ← Generated pantry CSVs
```

- Synthetic files are generated into `data/synthetic/` (organized, separate from real data)
- Copies are placed in `data/receipts/` and `data/pantry/` so the existing pipeline processes them
- The `synthetic_` prefix in filenames makes synthetic files easy to identify

## Distinguishing Synthetic from Real Data

In the database, synthetic records can be identified by their `source_file` column:

- **Real data**: `source_file` = `"publix_2026_03_17.csv"`
- **Synthetic data**: `source_file` = `"synthetic_publix_2026-02-22.csv"`

The analytics script `src/analytics/synthetic_vs_real.py` uses this to split and compare the datasets.

## Things to Try

1. **Change the seed**: Run with `--seed 99` and compare the output to `--seed 42`
2. **Simulate a year**: Use `--weeks 52` to generate a full year of shopping data
3. **Empty kitchen**: Try `--fullness 0.2` to see what recipe matching looks like with few ingredients
4. **Add a store**: Add a new store profile in the config and regenerate
5. **Add seasonal items**: Add your own seasonal adjustments and see them appear in the right months
6. **Compare distributions**: Run `synthetic_vs_real.py` to see how synthetic data compares to your real data
