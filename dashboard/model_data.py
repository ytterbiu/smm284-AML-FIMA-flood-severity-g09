"""dashboard/model_data.py — Model section (Pages 3+): wide feature-set data
loading + cached model artifacts.

Own load path, deliberately separate from data.py's DASHBOARD_COLUMNS
(Pages 1-2) — this section needs the full NUMERIC/CATEG feature list plus
TARGET, not the lean 7-column set those pages use. See PLAN_UI.md "Model
section (Pages 3+)" and AGENTS.md "Model artifacts" for the full data
contract this implements.

Reads exports/dashboard/ directly (the teammate's export bundle) rather
than copying those files into dashboard/ — metadata.json is the single
source of truth for the feature schema, so NUMERIC/CATEG/TARGET are derived
from it, not duplicated as literals.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = REPO_ROOT / "exports" / "dashboard"

# dashboard_support.py isn't a package importable from dashboard/ without
# this — same sys.path trick data.py/ingest.py use for src/data/clean.py.
if str(EXPORTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPORTS_DIR))

from dashboard_support import clip_at_coverage, load_model  # noqa: E402

METADATA = json.loads((EXPORTS_DIR / "metadata.json").read_text())

NUMERIC: list[str] = METADATA["input_schema"]["numeric"]
CATEG: list[str] = METADATA["input_schema"]["categorical"]
TARGET: str = METADATA["target"]
PRIMARY_MODEL: str = METADATA["primary_model"]  # "gbm"

OOT_CUTOFF_YEAR = 2020  # metadata["oot_test_window"] == "yearOfLoss >= 2020"

# From metadata.json's "baseline_rule": unseen zone_family -> this global mean.
BASELINE_GLOBAL_MEAN = 49811.57

# For replicating the notebook's permutation-importance gamma-deviance scorer
# (mean_gamma_deviance floors predictions at this value — matches
# BE_notes.ipynb's DEV_FLOOR exactly, not a separately-chosen constant).
GAMMA_DEV_FLOOR: float = METADATA["gamma_deviance_pred_floor"]

# Fixed identity color per model, not by rank (see dataviz skill: color
# follows the entity, never its rank). GBM anchored to the palette's first
# slot since it's PRIMARY_MODEL and recurs across the whole Model section
# (performance page, predict page) — established once here, reused
# everywhere, same convention as charts/status_bands.py's STATUS_COLORS.
MODEL_COLORS = {
    "GBM (gamma loss)": "#2a78d6",
    "GLM (Gamma, log-link)": "#1baf7a",
    "RF (bagging, smeared log target)": "#eda100",
    "Baseline (zone mean)": "#008300",
    "Baseline (global mean)": "#4a3aa7",
    "Baseline (global median)": "#e34948",
}

MODEL_COLUMNS = NUMERIC + CATEG + ["yearOfLoss", TARGET]

USE_SAMPLE = True  # matches data.py's USE_SAMPLE convention
_MODE = "sample" if USE_SAMPLE else "full"
_DATA_PATH = REPO_ROOT / "data" / "processed" / f"claims_{_MODE}.parquet"

_df: pl.DataFrame | None = None
_models: dict[str, object] = {}
_baseline_means: dict[str, float] | None = None


def get_model_df() -> pl.DataFrame:
    """Cached wide-feature-set DataFrame: NUMERIC + CATEG + yearOfLoss + TARGET."""
    global _df
    if _df is None:
        _df = pl.read_parquet(_DATA_PATH, columns=MODEL_COLUMNS)
    return _df


def get_oot_df() -> pl.DataFrame:
    """get_model_df(), filtered to the out-of-time test window (yearOfLoss >= 2020) —
    for the Lorenz/lift page, evaluating against data the models never trained on."""
    return get_model_df().filter(pl.col("yearOfLoss") >= OOT_CUTOFF_YEAR)


def get_model(name: str):
    """Cached load of 'glm'/'gbm'/'rf' via dashboard_support.load_model() —
    never a bare joblib.load() (required for RF's custom class, see AGENTS.md)."""
    if name not in _models:
        _models[name] = load_model(str(EXPORTS_DIR / f"model_{name}.joblib"))
    return _models[name]


def predict(name: str, X: pl.DataFrame):
    """Predict with model `name`, clipped at coverage — the standard path
    every page should use rather than calling .predict() directly."""
    model = get_model(name)
    X_pd = X.to_pandas() if isinstance(X, pl.DataFrame) else X
    pred = model.predict(X_pd)
    return clip_at_coverage(pred, X_pd)


def get_baseline_means() -> dict[str, float]:
    """zone_family -> mean_severity_train lookup, from baseline_zone_means.csv."""
    global _baseline_means
    if _baseline_means is None:
        df = pl.read_csv(EXPORTS_DIR / "baseline_zone_means.csv")
        _baseline_means = dict(zip(df["zone_family"].to_list(), df["mean_severity_train"].to_list()))
    return _baseline_means


def predict_baseline(zone_family: str) -> float:
    """The trivial baseline: zone mean, falling back to the global mean for
    an unseen zone (shouldn't happen in practice — all 6 known zone_family
    buckets are already in baseline_zone_means.csv)."""
    return get_baseline_means().get(zone_family, BASELINE_GLOBAL_MEAN)


if __name__ == "__main__":
    df = get_model_df()
    print(f"model_df: {df.shape[0]:,} rows x {df.shape[1]} cols")
    oot = get_oot_df()
    print(f"OOT (yearOfLoss >= {OOT_CUTOFF_YEAR}): {oot.shape[0]:,} rows")
    for name in ("glm", "gbm", "rf"):
        m = get_model(name)
        print(f"  loaded {name}: {type(m).__name__}")
    print("baseline means:", get_baseline_means())
