"""Shared under-insurance status-band logic for Page 2 (C4 + C5).

Reproduces BE_notes.ipynb section 14 ("Behavioural rider: under-insurance"):
coverage_ratio = totalBuildingInsuranceCoverage / buildingReplacementCost,
clipped at 2. Coverage/replacement-cost values are the inflation-adjusted
(real) columns already in DASHBOARD_COLUMNS — the ratio is scale-invariant
to inflation adjustment (same CPI factor cancels in the division), so real
vs. nominal doesn't matter here, unlike C2's histogram.

Defined once here and imported by both chart builders (and the Page 2 KPI
cards) so the three bands/colors/thresholds can never drift apart between
C4, C5, and the KPI numbers — see dashboard/AGENTS.md "Status-band colors".
"""
from __future__ import annotations

import polars as pl

COVERAGE_COL = "totalBuildingInsuranceCoverage"
REPLACEMENT_COL = "buildingReplacementCost"
RATIO_CLIP = 2.0

STATUS_ORDER = ["Severely under-insured", "Under-insured", "Adequately insured"]

STATUS_COLORS = {
    "Adequately insured": "#4C78A8",  # neutral steel blue
    "Under-insured": "#F0A83E",  # amber
    "Severely under-insured": "#D64541",  # red
}

# severely-under < 0.5 <= under-insured < 0.8 <= adequately insured
SEVERE_THRESHOLD = 0.5
UNDER_THRESHOLD = 0.8


def compute_ratio_status(df: pl.DataFrame) -> pl.DataFrame:
    """Filter to valid rows (both fields present, replacement cost > 0),
    compute the clipped coverage ratio, and classify into a status band.

    Mirrors the notebook's `ok = rc.notna() & cov.notna() & (rc > 0)` mask.
    """
    valid = df.filter(
        pl.col(COVERAGE_COL).is_not_null()
        & pl.col(REPLACEMENT_COL).is_not_null()
        & (pl.col(REPLACEMENT_COL) > 0)
    )
    ratio = (pl.col(COVERAGE_COL) / pl.col(REPLACEMENT_COL)).clip(upper_bound=RATIO_CLIP)
    return valid.with_columns(
        ratio.alias("coverage_ratio"),
        pl.when(ratio < SEVERE_THRESHOLD)
        .then(pl.lit("Severely under-insured"))
        .when(ratio < UNDER_THRESHOLD)
        .then(pl.lit("Under-insured"))
        .otherwise(pl.lit("Adequately insured"))
        .alias("status"),
    )
