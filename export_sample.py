"""export_sample.py - cut a small, representative parquet slice for testing."""

import pandas as pd
import numpy as np
from pathlib import Path

RAW = Path("data/raw/FimaNfipClaimsV2.parquet")
OUT = Path("data/sample/nfip_sample.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(RAW, engine="pyarrow")
print(f"full: {len(df):,} rows x {df.shape[1]} cols")

# Strata key as a standalone Series — never added to df, so nothing to drop later
decade = pd.to_numeric(df["yearOfLoss"], errors="coerce") // 10 * 10
strata_key = (
    df["state"].astype("string").fillna("NA")
    + "_"
    + decade.astype("string").fillna("NA")
)

TARGET_ROWS = 30_000
frac = min(1.0, TARGET_ROWS / len(df))

# Proportional sample per stratum, min 1 per group; group_keys=False keeps it flat
sample = (
    df.groupby(strata_key, group_keys=False)
    .apply(lambda g: g.sample(max(1, int(round(len(g) * frac))), random_state=284))
    .reset_index(drop=True)
)


# Guarantee the known edge cases are present (don't rely on luck)
def force_in(sample, mask, n, label):
    extra = df.loc[mask]
    if len(extra):
        add = extra.sample(min(n, len(extra)), random_state=284)
        sample = pd.concat([sample, add]).drop_duplicates(subset="id")
        print(f"  +{min(n, len(extra))} {label}")
    return sample


bld = pd.to_numeric(df["amountPaidOnBuildingClaim"], errors="coerce")
sample = force_in(sample, bld < 0, 50, "negative payouts")
sample = force_in(sample, bld == 0, 200, "zero/denied payouts")
sample = force_in(
    sample,
    pd.to_numeric(df["elevationDifference"], errors="coerce") == 9999,
    200,
    "elev 9999 sentinels",
)
sample = force_in(
    sample,
    pd.to_numeric(df["occupancyType"], errors="coerce") >= 11,
    200,
    "Risk Rating 2.0 codes",
)
sample = force_in(
    sample,
    pd.to_numeric(df["yearOfLoss"], errors="coerce") < 1996,
    200,
    "pre-1996 records",
)

sample = sample.sample(frac=1, random_state=284).reset_index(drop=True)  # shuffle
sample.to_parquet(OUT, engine="pyarrow", compression="zstd")

mb = OUT.stat().st_size / 1e6
print(f"\nwrote {OUT}: {len(sample):,} rows x {sample.shape[1]} cols, {mb:.2f} MB")
if mb > 2.0:
    print("Above ~2 MB — re-run with TARGET_ROWS = 15_000 (zstd already on).")
