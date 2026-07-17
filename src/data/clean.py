"""src/data/clean.py — Phase 1 step 2: cleaning & claim selection.

Reproduces BE_notes.ipynb section 4 ("Cleaning and claim selection") as a
standalone, rerunnable function. Does not import from or modify the
notebook — kept in sync with it by hand.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_ASOF = pd.Timestamp("2026-07-04", tz="UTC")

# buildingDeductibleCode -> $ amount
DEDUCTIBLE_MAP = {
    "0": 500, "1": 1000, "2": 2000, "3": 3000, "4": 4000, "5": 5000, "9": 750,
    "A": 10000, "B": 15000, "C": 20000, "D": 25000, "E": 50000, "F": 1250,
    "G": 1500, "H": 200,
}

# occupancyType: legacy (1-6) + Risk Rating 2.0 (11-19) -> one set of classes
OCCUPANCY_MAP = {
    1: "single_family", 11: "single_family",
    2: "2to4_family", 12: "2to4_family",
    3: "multi_family", 13: "multi_family",
    4: "non_residential", 6: "non_residential", 18: "non_residential", 19: "non_residential",
    14: "mobile_home", 17: "mobile_home",
    15: "condo", 16: "condo",
}

NUM_COERCE_COLS = [
    "amountPaidOnBuildingClaim",
    "totalBuildingInsuranceCoverage",
    "totalContentsInsuranceCoverage",
    "elevationDifference",
    "baseFloodElevation",
    "lowestFloorElevation",
    "lowestAdjacentGrade",
    "buildingReplacementCost",
    "crsClassificationCode",
    "numberOfFloorsInTheInsuredBuilding",
]

# "not reported" sentinel codes (9999 / -9999 family) -> NaN
ELEVATION_SENTINEL_COLS = [
    "elevationDifference",
    "baseFloodElevation",
    "lowestFloorElevation",
    "lowestAdjacentGrade",
]

BOOL_INDICATOR_COLS = [
    "postFIRMConstructionIndicator",
    "elevatedBuildingIndicator",
    "primaryResidenceIndicator",
]

# zone_family()'s 6 buckets, ascending by median amountPaidOnBuildingClaim
# (verified on sample data in notebooks/EDA.ipynb cell 5) — the order the
# dashboard's C3 boxplots and any other zone-ordered chart should use.
ZONE_ORDER = [
    "Unknown",
    "D (undetermined)",
    "A (SFHA no BFE)",
    "X/B/C (moderate-min)",
    "V (velocity)",
    "A (SFHA w/ BFE)",
]

# The 50 states + DC. `state` also contains territory/unknown codes (PR,
# VI, GU, AS, MP, UN) that don't map onto a "USA-states" choropleth and are
# excluded dataset-wide on the dashboard's Page 1 (see dashboard/PLAN_UI.md).
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}


def _as_utc_timestamp(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def zone_family(z) -> str:
    """FEMA rated-flood-zone string -> one of 6 risk-family buckets."""
    if not isinstance(z, str) or z.strip() == "":
        return "Unknown"
    z = z.upper()
    if z.startswith("V"):
        return "V (velocity)"
    if z.startswith("A"):
        return "A (SFHA no BFE)" if z == "A" else "A (SFHA w/ BFE)"
    if z[0] in {"X", "B", "C"}:
        return "X/B/C (moderate-min)"
    if z == "D":
        return "D (undetermined)"
    return "Unknown"


def clean_claims(
    df: pd.DataFrame, asof: pd.Timestamp | str = DEFAULT_ASOF
) -> tuple[pd.DataFrame, dict]:
    """Clean + feature-engineer raw claims, then filter to positive-payout rows.

    Mirrors BE_notes.ipynb §4: as-of cutoff, sentinel nulling, building_age,
    deductible_amount, occupancy_class, zone_family, floors_cat/basement_cat,
    boolean indicators, and the positive-payout selection.

    Returns (model_df, selection_log) — model_df is the cleaned frame
    filtered to positive building payouts; selection_log records the counts
    dropped at each stage (for parity checks against BE's printed numbers).
    """
    asof = _as_utc_timestamp(asof)
    df = df.copy()

    date_of_loss = pd.to_datetime(df["dateOfLoss"], errors="coerce", utc=True)
    beyond = date_of_loss >= asof
    df = df[~beyond].copy()

    for c in NUM_COERCE_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in ELEVATION_SENTINEL_COLS:
        df.loc[df[c].abs() >= 9990, c] = np.nan

    # elevationDifference is a difference in feet; values beyond physical
    # bound are sentinel arithmetic / code families, not real measurements
    df.loc[df["elevationDifference"].abs() >= 90, "elevationDifference"] = np.nan

    build_year = pd.to_datetime(df["originalConstructionDate"], errors="coerce").dt.year
    df["building_age"] = (df["yearOfLoss"] - build_year).where(
        lambda s: (s >= 0) & (s <= 200)
    )

    df["deductible_amount"] = df["buildingDeductibleCode"].map(DEDUCTIBLE_MAP)
    df["occupancy_class"] = df["occupancyType"].map(OCCUPANCY_MAP).fillna("other")
    df["zone_family"] = df["ratedFloodZone"].map(zone_family)

    df["floors_cat"] = (
        df["numberOfFloorsInTheInsuredBuilding"]
        .astype("Int64")
        .astype("string")
        .fillna("missing")
    )
    df["basement_cat"] = (
        df["basementEnclosureCrawlspaceType"]
        .astype("Int64")
        .astype("string")
        .fillna("missing")
    )
    for b in BOOL_INDICATOR_COLS:
        df[b + "_i"] = df[b].astype("int8")

    t = df["amountPaidOnBuildingClaim"]
    selection_log = {
        "total_rows": int(len(df)),
        "positive_payout": int((t > 0).sum()),
        "zero_or_denied": int((t == 0).sum()),
        "negative": int((t < 0).sum()),
        "missing": int(t.isna().sum()),
    }
    model_df = df[t > 0].copy()
    selection_log["modelling_rows"] = int(len(model_df))
    return model_df, selection_log


if __name__ == "__main__":
    from ingest import load_claims

    raw = load_claims("sample")
    cleaned, log = clean_claims(raw)
    print("SELECTION LOG")
    for k, v in log.items():
        print(f"  {k}: {v:,}")
