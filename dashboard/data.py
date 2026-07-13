"""dashboard/data.py — Page 1 data loading and caching.

Loads data/processed/claims_{mode}.parquet once at import time (module-level
cache) and exposes a filtering helper for callbacks. See dashboard/AGENTS.md
for the caching rationale and dashboard/PLAN_UI.md for the filter-state design
this supports.
"""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

# src/data/clean.py isn't a package importable from dashboard/ without this
# — same repo-root sys.path trick src/data/ingest.py uses to reuse data.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data.clean import US_STATES, ZONE_ORDER  # noqa: E402

USE_SAMPLE = True  # matches the USE_SAMPLE convention used elsewhere in this repo
_MODE = "sample" if USE_SAMPLE else "full"
_DATA_PATH = REPO_ROOT / "data" / "processed" / f"claims_{_MODE}.parquet"

TARGET = "amountPaidOnBuildingClaim"

# Page 1 only needs these 5 of the processed file's 46 columns — column
# pushdown at read time. Page 2 (model UI) will define its own column list.
DASHBOARD_COLUMNS = [
    "state",
    "zone_family",
    "yearOfLoss",
    TARGET,
    f"{TARGET}_nominal",
]

_df: pl.DataFrame | None = None
_stat_range_cache: dict[str, tuple[float, float]] = {}


def get_df() -> pl.DataFrame:
    """Return the cached, page-1-ready DataFrame. Loads from disk on first call.

    Excludes territory/unknown state codes (PR, VI, GU, AS, MP, UN) dataset-wide
    so I_Freq/I_Payout stay consistent with what the choropleth can render —
    see dashboard/PLAN_UI.md "Confirmed design decisions" #2.
    """
    global _df
    if _df is None:
        raw = pl.read_parquet(_DATA_PATH, columns=DASHBOARD_COLUMNS)
        _df = raw.filter(pl.col("state").is_in(US_STATES))
    return _df


RANGE_PAD_FRAC = 0.10  # +/-10% padding, see get_stat_range docstring


def get_stat_range(stat: str = "median") -> tuple[float, float]:
    """Global min/max of per-state {stat} severity across ALL years/zones,
    padded by RANGE_PAD_FRAC on each side.

    Used to fix the choropleth's colorbar range so a given color always
    means the same dollar amount, regardless of the currently active
    year/zone filter — otherwise go.Choropleth auto-scales to whatever
    subset is currently shown, making colors incomparable across filter
    changes (e.g. a single sparse year vs. "all years"). Cached per stat
    since it only depends on the full dataset, not on any filter.

    Padding gives a filtered subset (e.g. one zone_family in one state) some
    room to exceed the unfiltered global range before its color saturates
    at the scale's boundary — values beyond [zmin, zmax] still render (no
    error), just pinned to the nearest boundary color; the exact number is
    always still shown on hover regardless.
    """
    if stat not in _stat_range_cache:
        df = get_df()
        agg_expr = pl.col(TARGET).median() if stat == "median" else pl.col(TARGET).mean()
        per_state = df.group_by("state").agg(agg_expr.alias("value"))
        lo, hi = float(per_state["value"].min()), float(per_state["value"].max())
        # Pad each bound by a fraction of itself, not of (hi - lo) — padding
        # by range width would add the same absolute amount to both ends,
        # which barely moves a large hi but can nearly erase a small lo.
        _stat_range_cache[stat] = (
            max(0.0, lo * (1 - RANGE_PAD_FRAC)),
            hi * (1 + RANGE_PAD_FRAC),
        )
    return _stat_range_cache[stat]


def apply_filters(
    df: pl.DataFrame,
    year: int | None = None,
    state: str | None = None,
    zone_family: str | None = None,
) -> pl.DataFrame:
    """Apply zero or more filters to the DataFrame in-memory."""
    if year is not None:
        df = df.filter(pl.col("yearOfLoss") == year)
    if state is not None:
        df = df.filter(pl.col("state") == state)
    if zone_family is not None:
        df = df.filter(pl.col("zone_family") == zone_family)
    return df


if __name__ == "__main__":
    df = get_df()
    print(f"loaded: {df.shape[0]:,} rows x {df.shape[1]} cols from {_DATA_PATH}")
    print(f"zone_family order: {ZONE_ORDER}")
    print(f"years: {df['yearOfLoss'].min()}-{df['yearOfLoss'].max()}")
    print(f"n states: {df['state'].n_unique()}")
