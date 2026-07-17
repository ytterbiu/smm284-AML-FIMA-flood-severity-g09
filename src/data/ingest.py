"""src/data/ingest.py — Phase 1 step 1: data acquisition.

Pulls the FEMA claims data (sample or full) and the CPI series used for
inflation adjustment. Reuses the column contract and download machinery
from the repo-root data.py (BE's ingestion step) instead of redefining it,
so the leakage boundary (UNDERWRITING_FEATURES / POST_FLOOD_FIELDS) lives in
exactly one place. Does not import from or modify BE_notes.ipynb.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# data.py lives at the repo root, not inside a package -> put the repo root
# on sys.path so it can be imported directly rather than duplicated here.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import data as fema  # noqa: E402  (BE's root-level data.py)

SAMPLE_PARQUET = REPO_ROOT / "data" / "sample" / "nfip_sample.parquet"
CPI_CSV = REPO_ROOT / "data" / "raw" / "cpiaucsl.csv"
CPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"


def load_claims(mode: str = "sample") -> pd.DataFrame:
    """Load raw claims with the shared column pushdown (fema.LOAD_COLUMNS).

    mode="sample" reads the committed ~30k-row fixture (no download).
    mode="full" downloads (if not already cached) and reads the full
    ~2.72M-row FEMA parquet via fema.download_raw().
    """
    if mode == "sample":
        path = SAMPLE_PARQUET
    elif mode == "full":
        path = fema.download_raw()
    else:
        raise ValueError(f"mode must be 'sample' or 'full', got {mode!r}")
    return pd.read_parquet(path, columns=fema.LOAD_COLUMNS, engine="pyarrow")


def load_cpi_annual(cpi_csv: Path = CPI_CSV) -> pd.Series:
    """Annual-average CPI-U (BLS CPIAUCSL via FRED), cached locally.

    Shares the same cache path as BE_notes.ipynb §5, so a download from
    either the notebook or this script is reused by the other.
    """
    if not cpi_csv.exists():
        cpi_csv.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(CPI_URL, timeout=60)
        r.raise_for_status()
        cpi_csv.write_bytes(r.content)
        cpi_csv.with_suffix(".provenance.json").write_text(
            json.dumps(
                {
                    "source": CPI_URL,
                    "series": "CPIAUCSL (BLS via FRED)",
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
        )
    cpi = pd.read_csv(cpi_csv)
    date_col = cpi.columns[0]  # FRED has used both DATE and observation_date
    cpi[date_col] = pd.to_datetime(cpi[date_col])
    cpi["CPIAUCSL"] = pd.to_numeric(cpi["CPIAUCSL"], errors="coerce")
    annual = cpi.set_index(date_col)["CPIAUCSL"].resample("YE").mean()
    annual.index = annual.index.year
    return annual.dropna()


if __name__ == "__main__":
    df = load_claims("sample")
    print(f"loaded sample claims: {df.shape[0]:,} rows x {df.shape[1]} cols")
    cpi = load_cpi_annual()
    print(f"loaded CPI series: {cpi.index.min()}-{cpi.index.max()}")
