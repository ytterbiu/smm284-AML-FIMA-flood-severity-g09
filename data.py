"""
src/data.py — Step 1 of the SMM284 Group 09 pipeline: data acquisition.

Source: FEMA OpenFEMA "FIMA NFIP Redacted Claims", dataset version 2
(~2.72M claim records, refreshed ~monthly).

Strategy
--------
* Use the OpenFEMA *metadata* API (v1) for the dataset descriptor and field
  schema only — never to page the 2.72M records (the data API caps at 1,000
  rows/request, so a full pull would be ~2,722 calls).
* Download the bulk *Parquet* file once (~50-500 MB vs 500 MB-10 GB for CSV),
  cache it under data/raw/, and read it with column pushdown so we only pull
  the ~30 columns the project needs into memory.

Column contract
---------------
The column groups below encode the leakage boundary agreed in the project
design. A pricing model may only use UNDERWRITING_FEATURES (known before any
flood). POST_FLOOD_FIELDS exist only after the water arrives and must never
enter a pricing model as features — importing this contract makes that
boundary enforceable in code, not just prose.

Requires: pandas, pyarrow, requests  (pin these in requirements.txt)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# --- Endpoints -------------------------------------------------------------
METADATA_BASE = "https://www.fema.gov/api/open/v1"
DATA_API = "https://www.fema.gov/api/open/v2/FimaNfipClaims"
DATASET_NAME = "FimaNfipClaims"
DATASET_VERSION = 2

RAW_DIR = Path("data/raw")
RAW_PARQUET = RAW_DIR / "FimaNfipClaimsV2.parquet"
PROVENANCE = RAW_DIR / "provenance.json"

# --- Column contract (the leakage boundary) --------------------------------
TARGET = "amountPaidOnBuildingClaim"

# Known at underwriting time -> legal features for a pricing model
UNDERWRITING_FEATURES = [
    "ratedFloodZone", "elevationDifference", "baseFloodElevation",
    "lowestFloorElevation", "lowestAdjacentGrade", "elevatedBuildingIndicator",
    "basementEnclosureCrawlspaceType", "obstructionType", "occupancyType",
    "numberOfFloorsInTheInsuredBuilding", "buildingDescriptionCode",
    "condominiumCoverageTypeCode", "postFIRMConstructionIndicator",
    "originalConstructionDate", "primaryResidenceIndicator",
    "rentalPropertyIndicator", "totalBuildingInsuranceCoverage",
    "totalContentsInsuranceCoverage", "buildingDeductibleCode",
    "crsClassificationCode", "elevationCertificateIndicator",
]

# Known only AFTER the flood -> leakage for a pricing model; never use as features
POST_FLOOD_FIELDS = [
    "waterDepth", "floodWaterDuration", "floodCharacteristicsIndicator",
    "causeOfDamage", "floodEvent", "eventDesignationNumber", "ficoNumber",
    "buildingDamageAmount", "contentsDamageAmount", "amountPaidOnContentsClaim",
    "netBuildingPaymentAmount", "netContentsPaymentAmount",
    "replacementCostBasis", "nonPaymentReasonBuilding", "nonPaymentReasonContents",
]

# Geography + time: for EDA, the zone/state baseline, and grouped CV splits
CONTEXT = ["state", "countyCode", "yearOfLoss", "dateOfLoss", "latitude", "longitude"]

# Diagnostic fields for the under-insurance rider (NOT pricing features)
RIDER = ["buildingReplacementCost", "buildingPropertyValue"]

# What we actually load from the parquet (target + legal features + context + rider)
LOAD_COLUMNS = [TARGET] + UNDERWRITING_FEATURES + CONTEXT + RIDER


# --- Metadata API ----------------------------------------------------------
def _get_json(path: str, params: dict) -> dict:
    """GET a small OpenFEMA metadata payload as JSON."""
    resp = requests.get(f"{METADATA_BASE}/{path}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_dataset_metadata() -> dict:
    """Dataset descriptor: bulk file URLs, record count, refresh stamp, hash."""
    payload = _get_json(
        "OpenFemaDataSets", {"$filter": f"name eq '{DATASET_NAME}'"}
    )
    ds = payload["OpenFemaDataSets"][0]
    dist = {d["format"]: d["accessURL"] for d in ds["distribution"]}
    return {
        "record_count": ds["recordCount"],
        "parquet_url": dist["parquet"],
        "csv_url": dist["csv"],
        "last_refresh": ds["lastDataSetRefresh"],
        "hash": ds["hash"],
        "version": ds["version"],
    }


def get_field_schema() -> pd.DataFrame:
    """Field dictionary as a DataFrame (name, type, description, key, nullable)."""
    payload = _get_json(
        "OpenFemaDataSetFields",
        {"$filter": f"openFemaDataSet eq '{DATASET_NAME}' "
                    f"and datasetVersion eq {DATASET_VERSION}"},
    )
    fields = pd.DataFrame(payload["OpenFemaDataSetFields"])
    return fields[["name", "type", "description", "primaryKey", "isNullable"]]


# --- Bulk download + load --------------------------------------------------
def download_raw(force: bool = False) -> Path:
    """Download the bulk Parquet once into data/raw/; skip if already cached.

    Writes a provenance.json sidecar (source URL, FEMA hash, expected row
    count, download time) so the run is reproducible and auditable.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_PARQUET.exists() and not force:
        return RAW_PARQUET

    meta = get_dataset_metadata()
    print(f"Downloading bulk parquet (~50-500 MB):\n  {meta['parquet_url']}")
    with requests.get(meta["parquet_url"], stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(RAW_PARQUET, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):  # 1 MB chunks
                fh.write(chunk)

    PROVENANCE.write_text(json.dumps({
        "parquet_url": meta["parquet_url"],
        "fema_hash": meta["hash"],
        "expected_record_count": meta["record_count"],
        "last_refresh": meta["last_refresh"],
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    print(f"Saved -> {RAW_PARQUET}")
    return RAW_PARQUET


def load_raw(columns: list[str] | None = LOAD_COLUMNS,
             validate: bool = True) -> pd.DataFrame:
    """Load the cached Parquet (default: the project's ~30 columns via pushdown).

    Pass columns=None to load all 73 fields. Row count is checked against the
    recorded provenance as a soft warning (FEMA refreshes monthly, so a drift
    is informative, not an error).
    """
    path = download_raw()
    df = pd.read_parquet(path, columns=columns, engine="pyarrow")

    if validate and PROVENANCE.exists():
        expected = json.loads(PROVENANCE.read_text())["expected_record_count"]
        if len(df) != expected:
            print(f"NOTE: loaded {len(df):,} rows; provenance expected "
                  f"{expected:,}. FEMA likely refreshed the file — "
                  f"re-run download_raw(force=True) to re-pin provenance.")
    return df


# --- Small API slice (for quick dev / building the shared fixture) ---------
def fetch_api_sample(n: int = 1000, where: str | None = None) -> pd.DataFrame:
    """Pull up to n rows via the v2 data API (paged in 1,000s).

    Use for fast iteration or to build the committed dev fixture, e.g.
    fetch_api_sample(2000, where="state eq 'TX' and yearOfLoss eq 2017").
    Do NOT use this to assemble the full dataset — use the bulk parquet.
    """
    rows, skip, page = [], 0, min(n, 1000)
    while len(rows) < n:
        params = {"$top": page, "$skip": skip, "$format": "json"}
        if where:
            params["$filter"] = where
        resp = requests.get(DATA_API, params=params, timeout=120)
        resp.raise_for_status()
        batch = resp.json().get(DATASET_NAME, [])
        if not batch:
            break
        rows.extend(batch)
        skip += page
    return pd.DataFrame(rows[:n])


if __name__ == "__main__":
    meta = get_dataset_metadata()
    print(f"FimaNfipClaims v{meta['version']}: {meta['record_count']:,} records "
          f"(refreshed {meta['last_refresh']})")
    df = load_raw()
    print(f"Loaded {df.shape[0]:,} rows x {df.shape[1]} columns for modelling.")
    print(df[[TARGET, "ratedFloodZone", "state", "yearOfLoss"]].head())