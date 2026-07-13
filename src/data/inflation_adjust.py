"""src/data/inflation_adjust.py — Phase 1 step 3: inflation adjustment.

Reproduces BE_notes.ipynb section 5 ("Inflation adjustment — constant 2024
USD") as a standalone, rerunnable function. Does not import from or modify
the notebook — kept in sync with it by hand.
"""
from __future__ import annotations

import pandas as pd

DEFAULT_REF_YEAR = 2024

MONEY_COLS = [
    "amountPaidOnBuildingClaim",  # the target
    "totalBuildingInsuranceCoverage",
    "totalContentsInsuranceCoverage",
    "deductible_amount",
    "buildingReplacementCost",
]


def apply_inflation_adjustment(
    model_df: pd.DataFrame,
    cpi_annual: pd.Series,
    ref_year: int = DEFAULT_REF_YEAR,
) -> pd.DataFrame:
    """Deflate MONEY_COLS to constant ref_year USD.

    Idempotent: deflates from a preserved *_nominal copy, so re-running this
    (or changing ref_year) never compounds the adjustment. Years outside the
    CPI table fall back to the latest available factor.
    """
    model_df = model_df.copy()
    factor = (cpi_annual.loc[ref_year] / cpi_annual).rename("cpi_factor")

    f = model_df["yearOfLoss"].map(factor).fillna(factor.iloc[-1])
    model_df["cpi_factor"] = f

    for c in MONEY_COLS:
        if c in model_df.columns:
            nom = c + "_nominal"
            if nom not in model_df.columns:
                model_df[nom] = model_df[c]
            model_df[c] = model_df[nom] * f
    return model_df


if __name__ == "__main__":
    from clean import clean_claims
    from ingest import load_claims, load_cpi_annual

    raw = load_claims("sample")
    cleaned, _ = clean_claims(raw)
    cpi = load_cpi_annual()
    adjusted = apply_inflation_adjustment(cleaned, cpi)
    print(f"Median real severity: ${adjusted['amountPaidOnBuildingClaim'].median():,.0f}")
