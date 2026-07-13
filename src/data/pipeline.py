"""src/data/pipeline.py — Phase 1 entry point.

Runs ingest -> clean -> inflation_adjust and writes the processed dataset to
data/processed/claims_{mode}.parquet (gitignored). Run for both mode=sample
and mode=full.

Usage:
    python src/data/pipeline.py --mode sample
    python src/data/pipeline.py --mode full
    python src/data/pipeline.py --mode full --asof 2026-01-01 --ref-year 2023
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clean import DEFAULT_ASOF, clean_claims
from inflation_adjust import DEFAULT_REF_YEAR, apply_inflation_adjustment
from ingest import load_claims, load_cpi_annual

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def build_processed(
    mode: str = "sample",
    asof: pd.Timestamp | str = DEFAULT_ASOF,
    ref_year: int = DEFAULT_REF_YEAR,
) -> tuple[pd.DataFrame, dict, Path]:
    """Run the full ingest -> clean -> inflation_adjust pipeline and save it.

    Returns (model_df, selection_log, output_path).
    """
    raw = load_claims(mode)
    print(f"[{mode}] loaded raw claims: {raw.shape[0]:,} rows x {raw.shape[1]} cols")

    model_df, selection_log = clean_claims(raw, asof=asof)
    print(f"[{mode}] SELECTION LOG")
    for k, v in selection_log.items():
        print(f"  {k}: {v:,}")

    cpi_annual = load_cpi_annual()
    model_df = apply_inflation_adjustment(model_df, cpi_annual, ref_year=ref_year)
    print(
        f"[{mode}] median real severity ({ref_year} USD): "
        f"${model_df['amountPaidOnBuildingClaim'].median():,.0f}"
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / f"claims_{mode}.parquet"
    model_df.to_parquet(out_path, engine="pyarrow")
    print(f"[{mode}] saved -> {out_path}")
    return model_df, selection_log, out_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sample", "full"], default="sample")
    parser.add_argument(
        "--asof",
        default=str(DEFAULT_ASOF.date()),
        help="Drop claims dated on/after this date (default matches BE_notes.ipynb).",
    )
    parser.add_argument(
        "--ref-year",
        type=int,
        default=DEFAULT_REF_YEAR,
        help="CPI reference year for inflation adjustment (default matches BE_notes.ipynb).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    build_processed(mode=args.mode, asof=args.asof, ref_year=args.ref_year)
