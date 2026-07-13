# Dashboard & Prediction UI — Plan

Tracks the work to build a data-visualisation dashboard and a model
prediction UI on top of Ben's analysis in `BE_notes.ipynb`. See
[ANALYSIS_SUMMARY.md](ANALYSIS_SUMMARY.md) for the modelling findings this
builds on, and [CLAUDE.md](CLAUDE.md) for repo conventions.

**Ground rule: `BE_notes.ipynb` is not modified by this work.** It stays
Ben's notebook, the reference implementation of every cleaning/modelling
decision. Everything here is a from-scratch re-implementation of the parts
we need, kept in sync with it by hand.

## Phase 1 — Data pipeline scripts (`src/data/`)

Extract the notebook's §2 (acquisition), §4 (cleaning & claim selection) and
§5 (inflation adjustment) into standalone, rerunnable scripts. Run on both
the sample and full data (matching the existing `USE_SAMPLE` toggle
pattern), writing outputs to `data/processed/` (already gitignored).

- [ ] `src/data/ingest.py` — full parquet + CPI series download/cache.
      Reuse `data.py`'s column contract (`LOAD_COLUMNS`,
      `UNDERWRITING_FEATURES`, `POST_FLOOD_FIELDS`, `download_raw`) rather
      than redefining it, so the leakage boundary lives in one place.
- [ ] `src/data/clean.py` — reproduces notebook §4 cell: as-of cutoff filter,
      string→numeric coercion, elevation sentinel nulling
      (`±9990`/`elevationDifference >= 90`), `building_age`,
      `deductible_amount` (code→$ map), `occupancy_class` (legacy + Risk
      Rating 2.0 merge), `zone_family` (6-bucket), `floors_cat`/
      `basement_cat`, boolean indicator columns, and the positive-payout
      selection filter (+ selection log).
- [ ] `src/data/inflation_adjust.py` — reproduces notebook §5 cell: annual
      CPI-U (FRED `CPIAUCSL`) deflator to constant `REF_YEAR` USD, applied
      idempotently via `*_nominal` columns.
- [ ] Wire the three into a single entry point (e.g. `src/data/pipeline.py`
      or a `make`-style script) that takes a sample/full flag and writes:
      - `data/processed/claims_{mode}.parquet` — cleaned + inflated,
        feature-engineered dataset (the thing that's currently *not* saved
        anywhere, per our earlier check of the notebook).
- [ ] Run once for `sample`, once for `full`; sanity-check output row counts
      against Ben's printed selection log (2,004,995 modelling rows on full
      data) and median real severity ($21,229).

**Open questions:**
- Hardcode `ASOF = 2026-07-04` and `REF_YEAR = 2024` to match Ben's numbers
  exactly, or parameterise? (default: hardcode, matching his notebook, for
  now)
- Confirm full-data CPI/FEMA download works from this machine before
  running Phase 1 for real (network access to `fema.gov` /
  `fred.stlouisfed.org`).

## Phase 2 — EDA notebook (`notebooks/`)

- [ ] `notebooks/eda.ipynb` (or similar) — separate from `BE_notes.ipynb`,
      reads `data/processed/claims_*.parquet` (not the notebook's in-memory
      `df`/`model_df`).
- [ ] Profile the processed dataset; draft the specific charts/tables
      intended for the dashboard's EDA section (severity distribution,
      zone/occupancy breakdowns, missingness, under-insurance view, etc. —
      see ANALYSIS_SUMMARY.md §2–3, §9 for what Ben already found).
- [ ] Treat this as scratch/draft space — the dashboard is the deliverable,
      this notebook is where chart choices get tried out first.

## Phase 3 — Dashboard (Dash)

Two sections, built in this order:

- [ ] **Section A — Interactive EDA.** Visualise the processed dataset and
      Ben's key findings (severity by zone/occupancy, missingness, OOT vs
      random-split gap, under-insurance by zone, pricing-implication
      deciles). Consumes `data/processed/claims_*.parquet` from Phase 1.
- [ ] **Section B — Model UI** *(blocked — see below)*. Feature-input form →
      prediction → explanation (SHAP feature importance, lift vs flat-zone
      baseline). Needs a serialized model artifact.

**Blocker for Section B:** nothing downstream of raw ingestion is currently
saved by the notebook — the fitted `best_model` (untuned GBM, refit on the
OOT training set) only ever exists in-memory during a notebook run. Need
Ben to export it (e.g. `joblib.dump(best_model, "models/best_model.joblib")`)
before Section B can start. Revisit once that's available — don't build
against a placeholder/re-trained-by-us model, since the whole point is to
serve *his* selected, validated model.

## Status

- [x] Repo orientation, `ANALYSIS_SUMMARY.md` + `CLAUDE.md` written.
- [x] Confirmed only the sample data is committed; full/CPI data not yet
      downloaded on this machine.
- [x] Confirmed no processed dataset or fitted model is currently persisted
      anywhere in the pipeline.
- [ ] Phase 1 (data pipeline scripts) — not started.
- [ ] Phase 2 (EDA notebook) — not started.
- [ ] Phase 3 (dashboard) — not started; Section B blocked on Ben.
