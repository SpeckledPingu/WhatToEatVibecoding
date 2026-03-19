"""
generate_all.py — Master script: generate synthetic data and optionally run the pipeline.

WHAT THIS SCRIPT DOES
This is the orchestration script that ties everything together:
  1. Generates synthetic receipt CSVs (simulated shopping trips)
  2. Generates a synthetic pantry snapshot CSV
  3. Copies the generated files into the ingestion directories (data/receipts/ and data/pantry/)
  4. Optionally runs the full ingestion → normalization → matching pipeline

WHAT IS AN ORCHESTRATION SCRIPT?
In data engineering, you often have many scripts that must run in a specific
order: generate data → ingest data → clean data → build derived tables. An
orchestration script automates this sequence so you don't have to run each
step manually. Professional systems use tools like Airflow or Prefect for this,
but a simple Python script works well for small projects.

WHY WE COPY FILES INTO THE INGESTION DIRECTORIES
The ingestion scripts (src/ingestion/receipts.py, src/ingestion/pantry.py)
scan specific directories (data/receipts/, data/pantry/) for CSV files.
Synthetic data is generated into data/synthetic/ to keep it organized, then
copied into the ingestion directories so the existing pipeline can process it
without any modifications. This is cleaner than modifying the ingestion scripts
to look in multiple directories.

RUN IT:
    uv run python -m src.synthetic.generate_all
    uv run python -m src.synthetic.generate_all --weeks 8 --trips 2 --fullness 0.7
    uv run python -m src.synthetic.generate_all --weeks 4 --no-pipeline
"""

import argparse
import shutil
from datetime import date
from pathlib import Path

from src.synthetic.generate_receipts import generate_receipts
from src.synthetic.generate_pantry import generate_pantry_snapshot


# Directories where the ingestion pipeline looks for data
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RECEIPTS_INGEST_DIR = PROJECT_ROOT / "data" / "receipts"
PANTRY_INGEST_DIR = PROJECT_ROOT / "data" / "pantry"


def _copy_to_ingestion_dirs(
    receipt_files: list[Path],
    pantry_file: Path,
) -> None:
    """
    Copy generated synthetic files into the ingestion directories.

    The existing pipeline scans data/receipts/ and data/pantry/ for CSV files.
    By copying our synthetic files there, the pipeline processes them alongside
    any real data — no pipeline modifications needed.

    Files are prefixed with "synthetic_" so they're easy to identify and
    distinguish from real data.
    """
    print("\nCopying synthetic files to ingestion directories...")

    for receipt_path in receipt_files:
        dest = RECEIPTS_INGEST_DIR / receipt_path.name
        shutil.copy2(receipt_path, dest)
    print(f"  Copied {len(receipt_files)} receipt files to {RECEIPTS_INGEST_DIR}/")

    dest = PANTRY_INGEST_DIR / pantry_file.name
    shutil.copy2(pantry_file, dest)
    print(f"  Copied 1 pantry file to {PANTRY_INGEST_DIR}/")


def _run_pipeline() -> None:
    """
    Run the full ingestion → normalization → matching pipeline.

    This calls the same functions that the individual workstream scripts use,
    in the correct order:
      1. Ingest recipes (in case new ones were added)
      2. Ingest receipts (including our synthetic receipts)
      3. Ingest pantry data (including our synthetic pantry)
      4. Build the unified active inventory (normalization)
      5. Build recipe matching tables (recommendation engine)

    The pipeline is idempotent — running it multiple times on the same data
    produces the same result (duplicates are detected and skipped).
    """
    print("\n" + "=" * 70)
    print("RUNNING FULL PIPELINE (ingest → normalize → match)")
    print("=" * 70)

    # Step 1: Ingest all data sources
    from src.ingestion.recipes import ingest_recipes
    from src.ingestion.receipts import ingest_receipts
    from src.ingestion.pantry import ingest_pantry

    print("\n[1/5] Ingesting recipes...")
    ingest_recipes()

    print("\n[2/5] Ingesting receipts...")
    ingest_receipts()

    print("\n[3/5] Ingesting pantry data...")
    ingest_pantry()

    # Step 2: Normalize and build derived tables
    from src.normalization.build_inventory import build_active_inventory
    from src.normalization.build_recipe_matching import build_recipe_matching

    print("\n[4/5] Building active inventory (normalization)...")
    build_active_inventory()

    print("\n[5/5] Building recipe matching tables...")
    build_recipe_matching()

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)


def generate_all(
    num_weeks: int = 4,
    trips_per_week: int = 2,
    pantry_fullness: float = 0.7,
    seed: int = 42,
    run_pipeline: bool = True,
) -> None:
    """
    Generate all synthetic data and optionally run the full pipeline.

    Parameters:
        num_weeks: Number of weeks of receipt data to generate.
        trips_per_week: Average shopping trips per week.
        pantry_fullness: How stocked the pantry is (0.0 to 1.0).
        seed: Random seed for reproducible data generation.
        run_pipeline: If True, run the ingestion/normalization/matching pipeline.

    This function coordinates all synthetic data generation in one call.
    It generates receipts, a pantry snapshot, copies them to the ingestion
    directories, and optionally processes everything through the pipeline.
    """
    print("=" * 70)
    print("SYNTHETIC DATA GENERATION")
    print("=" * 70)
    print(f"\nSettings:")
    print(f"  Weeks: {num_weeks}")
    print(f"  Trips/week: {trips_per_week}")
    print(f"  Pantry fullness: {pantry_fullness:.0%}")
    print(f"  Seed: {seed}")
    print(f"  Run pipeline: {run_pipeline}")

    # --- Step 1: Generate receipt data ---
    print("\n" + "-" * 40)
    print("STEP 1: Generate Receipts")
    print("-" * 40)
    receipt_files = generate_receipts(
        num_weeks=num_weeks,
        trips_per_week=trips_per_week,
        seed=seed,
    )

    # --- Step 2: Generate pantry snapshot ---
    print("\n" + "-" * 40)
    print("STEP 2: Generate Pantry Snapshot")
    print("-" * 40)
    pantry_file = generate_pantry_snapshot(
        fullness=pantry_fullness,
        seed=seed,
    )

    # --- Step 3: Copy to ingestion directories ---
    print("\n" + "-" * 40)
    print("STEP 3: Copy to Ingestion Directories")
    print("-" * 40)
    _copy_to_ingestion_dirs(receipt_files, pantry_file)

    # --- Step 4: Optionally run the full pipeline ---
    if run_pipeline:
        _run_pipeline()
    else:
        print("\nSkipping pipeline (--no-pipeline flag set)")
        print("Run the pipeline manually with:")
        print("  uv run python -m src.ingestion.receipts")
        print("  uv run python -m src.ingestion.pantry")
        print("  uv run python -m src.normalization.build_inventory")
        print("  uv run python -m src.normalization.build_recipe_matching")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("SYNTHETIC DATA GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nGenerated files:")
    print(f"  Receipt CSVs: {len(receipt_files)} files in data/synthetic/receipts/")
    print(f"  Pantry CSV:   1 file in data/synthetic/pantry/")
    print(f"  Copies:       Also in data/receipts/ and data/pantry/ for pipeline")
    if run_pipeline:
        print(f"\nPipeline: Complete — database updated with synthetic + real data")
    print(f"\nTo analyze the results:")
    print(f"  uv run python -m src.analytics.overview")
    print(f"  uv run python -m src.analytics.synthetic_vs_real")


# ---------------------------------------------------------------------------
# Run directly: python -m src.synthetic.generate_all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic grocery data and run the pipeline",
    )
    parser.add_argument(
        "--weeks", type=int, default=4,
        help="Number of weeks of receipt data to generate (default: 4)",
    )
    parser.add_argument(
        "--trips", type=int, default=2,
        help="Average shopping trips per week (default: 2)",
    )
    parser.add_argument(
        "--fullness", type=float, default=0.7,
        help="Pantry fullness 0.0-1.0 (default: 0.7)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--no-pipeline", action="store_true",
        help="Skip running the ingestion/normalization pipeline",
    )

    args = parser.parse_args()

    generate_all(
        num_weeks=args.weeks,
        trips_per_week=args.trips,
        pantry_fullness=args.fullness,
        seed=args.seed,
        run_pipeline=not args.no_pipeline,
    )
