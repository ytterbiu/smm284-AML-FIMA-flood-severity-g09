# Dashboard & Prediction UI — Plan

Tracks the work to build a data-visualisation dashboard and a model
prediction UI on top of Ben's analysis in `BE_notes.ipynb`. See
[../ANALYSIS_SUMMARY.md](../ANALYSIS_SUMMARY.md) for the modelling findings
this builds on, and [../CLAUDE.md](../CLAUDE.md) for repo conventions.

**Ground rule: `BE_notes.ipynb` is not modified by this work.** It stays
Ben's notebook, the reference implementation of every cleaning/modelling
decision. Everything here is a from-scratch re-implementation of the parts
we need, kept in sync with it by hand.

## Phase 1 — Data pipeline scripts (`src/data/`)

Extract the notebook's §2 (acquisition), §4 (cleaning & claim selection) and
§5 (inflation adjustment) into standalone, rerunnable scripts. Run on both
the sample and full data (matching the existing `USE_SAMPLE` toggle
pattern), writing outputs to `data/processed/` (already gitignored).

- [x] `src/data/ingest.py` — full parquet + CPI series download/cache.
      Reuses `data.py`'s column contract (`LOAD_COLUMNS`,
      `UNDERWRITING_FEATURES`, `POST_FLOOD_FIELDS`, `download_raw`) rather
      than redefining it, so the leakage boundary lives in one place.
- [x] `src/data/clean.py` — reproduces notebook §4 cell: as-of cutoff filter,
      string→numeric coercion, elevation sentinel nulling
      (`±9990`/`elevationDifference >= 90`), `building_age`,
      `deductible_amount` (code→$ map), `occupancy_class` (legacy + Risk
      Rating 2.0 merge), `zone_family` (6-bucket), `floors_cat`/
      `basement_cat`, boolean indicator columns, and the positive-payout
      selection filter (+ selection log). `ASOF`/`REF_YEAR` are parameters
      (`clean_claims(df, asof=...)`), defaulting to the notebook's own
      values (`2026-07-04`, `2024`).
- [x] `src/data/inflation_adjust.py` — reproduces notebook §5 cell: annual
      CPI-U (FRED `CPIAUCSL`) deflator to constant `REF_YEAR` USD, applied
      idempotently via `*_nominal` columns.
- [x] `src/data/pipeline.py` — CLI entry point (`--mode {sample,full}
      [--asof] [--ref-year]`) wiring ingest → clean → inflation_adjust,
      writing `data/processed/claims_{mode}.parquet`.
- [x] Ran for `mode=sample`: 22,533 modelling rows, median real severity
      $21,061 — close to Ben's full-data $21,229, good sanity check given
      it's a stratified subset. `mode=full` not yet run (needs the ~2.72M
      row FEMA download — hold until we're ready to build against it).

**Resolved:**
- `ASOF`/`REF_YEAR` parameterised, defaulting to Ben's notebook values (per
  discussion — not hardcoded as originally proposed).
- Gotcha hit and documented in `../CLAUDE.md`: the shell's default `python`
  resolves to a conda env without `pyarrow`; must use `./.venv/Scripts/python.exe`.

## Phase 2 — EDA notebook (`notebooks/`)

- [x] `notebooks/EDA.ipynb` created — separate from `BE_notes.ipynb`, reads
      `data/processed/claims_sample.parquet` (not the notebook's in-memory
      `df`/`model_df`). Connected via the Jupyter MCP server (see
      `../CLAUDE.md` → "Working with Jupyter Notebooks").
- [x] First chart built and verified: choropleth of median real severity by
      state (see cells 0–4). Caught two real data issues in the process:
      territory/unknown state codes (`PR`/`VI`/`GU`/`AS`/`MP`/`UN`, ~1.3% of
      rows) that don't render on a `USA-states` map, and several states
      with very small sample claim counts (e.g. `NV`=13, `AK`=10) whose
      medians are noisy.
- [x] Verified actual zone_family ascending-median order on sample data
      (cell 5) — see Phase 3 below, corrects an omission in the dashboard
      spec.
- [ ] Broader profiling pass (missingness, under-insurance, distributions
      per ANALYSIS_SUMMARY.md §2–3, §9) — not done yet; the notebook has
      mostly been used so far to prototype the dashboard's first chart and
      validate the Jupyter MCP workflow itself (including a mid-session fix:
      Jupyter Lab had been launched under the wrong Python env and needed
      restarting under `.venv` — see `../CLAUDE.md`).
- [ ] Treat this as scratch/draft space — the dashboard is the deliverable,
      this notebook is where chart choices get tried out first.

## Phase 3 — Dashboard (Dash)

Two sections; **Page 1 (EDA) built first**, Page 2 (model UI) blocked on
Ben's saved model (see below).

Reference implementation for conventions: `C:\Users\ardih\Data\CMS_Health_Insurance_Exchange\dashboard`
(see its `PLAN.md`/`AGENTS.md`) — same `dcc.Store`-as-single-source-of-truth
filter pattern, same dark-theme/Bootstrap conventions, adapted to this
app's chart set.

### Page 1 — "How much does flood insurance pay out in the USA?"

**Data**: `data/processed/claims_{mode}.parquet` (Phase 1 output). Dev
default `mode="sample"`; switch to `full` once that's been run. One row =
one claim (the cleaning step's positive-payout selection already applies),
so record count and claim count are the same number — answers the "does
this correspond to number of claims?" question in the spec: yes.

**Column pushdown at load time.** The processed file has 46 columns (full
feature set, kept for the future model-input page), but Page 1 only needs
5: `state`, `zone_family`, `yearOfLoss`, `amountPaidOnBuildingClaim`
(real), `amountPaidOnBuildingClaim_nominal`. `dashboard/data.py` reads with
`pl.read_parquet(path, columns=DASHBOARD_COLUMNS)` rather than loading all
46 into memory — same column-pushdown pattern `src/data/ingest.py` already
uses on the raw FEMA parquet. This meaningfully lowers the full-data memory
footprint below the earlier "few hundred MB to ~1GB" estimate (that number
assumed all 46 columns); re-check actual usage once `mode=full` exists.
Page 2 will need its own, wider column set (the `NUMERIC`/`CATEG` feature
list from `BE_notes.ipynb` §7) — not a reason to widen Page 1's load.

**Layout (top → bottom)**
```
Title: "How much does flood insurance pay out in the USA?"
----------------------------------------------------------------
Control row: F_Year (range slider, default = full extent) | F_Stat (Median/Mean toggle)
             | I_Payout (KPI card) | I_Freq (KPI card)
             | active-filter chips | Reset button
----------------------------------------------------------------
C1 (choropleth)                | C2 (nominal vs. real severity histogram,
                                |     raw/log toggle)
----------------------------------------------------------------
C3: row of 6 zone_family boxplots, shared y-axis, reference stat line
```

**Filter state** — one `dcc.Store(id="filter-state")`, mirroring the
reference app's pattern:
```json
{"year_range": [1978, 2026], "stat": "median", "state": null, "zone_family": null}
```
`year_range` was originally a single nullable year (`int | None`); changed
to an always-present `[lo, hi]` pair after teammate feedback asked for a
range (e.g. 2000–2020 inclusive), with a single year expressed as `[2000,
2000]`. This is a genuine simplification, not just an added feature: a
full-extent range (`[YEAR_MIN, YEAR_MAX]`, from `data.get_year_bounds()`)
is *functionally* a no-op filter, so "no year filter" no longer needs a
separate `None` case the way `state`/`zone_family` still do — `year_range`
is always applied via `pl.col("yearOfLoss").is_between(lo, hi)` (inclusive
both ends, Polars' default). UI: `dcc.RangeSlider` (sparse marks every 5
years — every-year marks would be unreadable across the ~49-year span —
plus an always-visible tooltip so exact dragged values are legible).
`stat` defaults to `"median"` (not null) since C1/C3/KPIs always need an
aggregation choice; `state`/`zone_family` still default to `null`
("no filter").

**Active-filter chips** (added after initial user testing — it wasn't
otherwise obvious which data subset the charts reflected): a read-only-by-
default badge row rendered from `filter-state` showing `year_range` (only
when it's narrower than the full extent — labelled `"Year: 2000"` when
`lo == hi`, `"Year: 2000–2020"` otherwise), `state`, and `zone_family` (not
`stat` — already visible via the highlighted toggle button, would be
redundant here). Each chip is *also* independently clickable to clear just
that one filter — implemented as a second callback writing to
`filter-state` via Dash's pattern-matching `Input({"type": "filter-chip",
"key": ALL}, "n_clicks")`, using `allow_duplicate=True` on both callbacks
that write to `filter-state`. Clicking the year chip resets it to the full
`[YEAR_MIN, YEAR_MAX]` extent, not `None` (year_range is never null,
unlike `state`/`zone_family`, which do reset to `None`). This is in
addition to, not a replacement for, each filter's existing removal path
(dragging the slider back out, clicking the same map state/zone box again)
and Reset (clears all four fields at once).

**The "never filter yourself" rule** (same principle the reference app uses
for state/metal): each chart is filtered by every *other* active filter,
never by the one it produces — it only highlights/dims its own selection.

| Chart | Filtered by | Not filtered by (dim/highlight only) |
|---|---|---|
| C1 choropleth | `year_range`, `zone_family` | `state` — map always shows all states; the selected one gets a highlight overlay (like the reference app's orange-border trace) |
| C2 histogram | `year_range`, `state`, `zone_family` | — (C2 has no filter of its own) |
| C3 boxplots | `year_range`, `state` | `zone_family` — all 6 boxes always shown; selected one full-opacity, others dimmed |
| I_Payout / I_Freq | `year_range`, `state`, `zone_family` | — |

Clicking an already-selected state/zone again clears that filter (toggle
behaviour, per spec). **Reset clears all four fields back to defaults,
including `stat` → `"median"`** (confirmed).

**Callback topology**
```
year-range-slider ──┐
stat-btn          ──┤
map-click         ──┼──► filter-state (Store) ──► C1 choropleth
zone-click*       ──┤                        ──► C2 histogram
reset-btn         ──┘                        ──► C3 boxplots
filter-chip-click*┘                          ──► KPI row (I_Payout, I_Freq)

c2-scale-toggle (raw/log) ──► C2 histogram directly
  (view-only, not a data filter — kept out of filter-state so toggling it
  doesn't re-trigger C1/C3/KPIs)
```
`*` validated (decision #4 below) — native `go.Box` `clickData` works
reliably, no button-row fallback needed.

**Chart specs**
- **C1 — choropleth**: `go.Choropleth` (not `px` — same reason as the
  reference app: need a second highlight-overlay trace for the selected
  state, which `px.choropleth` can't easily do). Colors by `stat`
  (median/mean) of `amountPaidOnBuildingClaim` per state, using a **fixed
  `zmin`/`zmax`** from `data.get_stat_range(stat)` — computed once from the
  full unfiltered dataset (padded ±10%, `RANGE_PAD_FRAC`, each bound scaled
  by itself not by range width — padding by range width barely moves a
  large max but nearly erases a small min), so a given color means the same
  dollar amount regardless of the active year/zone filter. Values outside
  the range still render (Plotly clamps to the boundary color, no error);
  the exact number is always available on hover regardless. Caught during
  manual testing: without this, the colorbar silently rescaled per filter,
  making colors incomparable across different year selections. Supersedes
  the `px.choropleth` used in `EDA.ipynb` cell 4, which was a quick workflow
  test, not the final chart implementation.
- **C2 — histogram**: two overlaid `go.Bar` traces styled as a histogram
  (nominal vs. real), reproducing `BE_notes.ipynb` §6 cell 21's binning
  approach — **bin counts/edges computed server-side with `numpy`/Polars
  (`np.histogram`), not by handing raw per-row arrays to `go.Histogram`**.
  See "Scalability at full data" below for why. The raw/log toggle
  recomputes bins on `log10(value)` rather than just setting a log-scaled
  axis on linear bins — matches the notebook's own approach and keeps bin
  widths meaningful either way.
- **C3 — zone boxplots**: one `go.Box` trace per `zone_family`, **using
  Plotly's precomputed-statistics mode** (`q1`, `median`, `q3`,
  `lowerfence`, `upperfence` passed directly, computed server-side with
  Polars `.quantile()`) **rather than passing raw `y` arrays** — see
  "Scalability at full data" below. All boxes share one y-axis natively
  (no `make_subplots` grid needed — unlike the reference app's C2+C3, we
  have no per-column KPI cards forcing a grid) + one `add_hline` per box at
  the current `stat` of the year+state-filtered (not zone-filtered) data.
  Selected zone at full opacity, others dimmed — same visual language as
  the reference app's metal-tier dimming.

**Scalability at full data (2.5M rows) — addressed now, not deferred:**
Polars filtering/aggregation (state groupby, zone groupby, year filter)
stays fast regardless of row count — that layer is not a concern. The real
risk is **C2 and C3 as naively spec'd would each embed raw per-row arrays
into the Plotly figure JSON sent to the browser** — fine at sample scale
(22K rows) but at 2.5M rows that means serializing millions of floats per
trace, and for C3 specifically, `go.Box`'s default outlier-point rendering
would try to draw a marker for every point beyond 1.5×IQR — on this
heavy-right-skewed severity data, plausibly tens of thousands of markers
per zone. Both charts are designed above to aggregate server-side with
Polars/numpy first (histogram bin counts, box quantiles) so the browser
only ever receives a few dozen numbers per chart, independent of whether
the underlying data is 22K or 2.5M rows. **Build this way from the start**
(even against `claims_sample.parquet` now) rather than doing it the naive
way first and rewriting later. One tradeoff: this means no individual
outlier points are plotted on C3 — acceptable for v1; can revisit with a
capped/sampled outlier overlay later if wanted.

Separately, in-memory footprint of `claims_full.parquet` (~2M rows ×
~46 cols) loaded once at import time (per the module-level cache pattern
in `AGENTS.md`) is expected to be a few hundred MB to ~1GB — fine for local
dev on a normal machine, single gunicorn worker. Worth re-checking actual
RAM usage once `mode=full` is run, and revisiting if/when a deployment
target with a fixed memory limit is chosen (see "Deployment Target" in
`AGENTS.md` — still not decided).

**Confirmed design decisions:**
1. **Zone order has 6 buckets, not 5** — confirmed, include
   `X/B/C (moderate-min)` at position 4. Ascending-median order (verified
   on sample data in `EDA.ipynb` cell 5): `Unknown ($7,174) →
   D (undetermined) ($11,372) → A (SFHA no BFE) ($14,303) →
   X/B/C (moderate-min) ($18,685) → V (velocity) ($19,898) →
   A (SFHA w/ BFE) ($25,610)`.
2. **Territory/unknown state codes excluded page-wide** — `PR`, `VI`,
   `GU`, `AS`, `MP`, `UN` (~1.3% of sample rows) are dropped for this page
   entirely, not just from C1, so I_Freq/I_Payout stay consistent with what
   the map shows.
3. **`D (undetermined)`'s small n (40 claims in sample) is an accepted
   caveat for now** — keep as-is; expected to look better once run against
   `claims_full.parquet`.
4. **Boxplot click reliability — validated, resolved.** Tested with a
   throwaway precomputed-statistics `go.Box` figure
   (`dashboard/_test_box_click.py`, since deleted): clicking the box body
   fires `clickData` reliably (`hoverOnBox: True`), and
   `clickData['points'][0]['x']` gives the clicked zone name directly —
   same identification pattern as the reference app's
   `map_click['points'][0]['location']`. **No button-row fallback needed**;
   C3 can use native chart clicks for the zone filter.
5. **Reset defaults `stat` to `"median"`** — confirmed (see Filter state
   above).

**Project structure** (new folder, mirrors the reference app):
```
dashboard/
├── PLAN_UI.md              ← this file
├── AGENTS.md               # AI coding-assistant guidance for this codebase
├── Notes_Dashboard.md      # your own prompt log — not for AI context
├── app.py                  # Dash init (use_pages=True); exposes server
├── data.py                 # loads data/processed/claims_{mode}.parquet, caches, apply_filters()
├── charts/
│   ├── choropleth.py       # build_choropleth(df, stat, selected_state) -> go.Figure   (C1)
│   ├── histogram.py        # build_histogram(df, log=False) -> go.Figure               (C2)
│   └── boxplots.py         # build_zone_boxplots(df, stat, selected_zone) -> go.Figure  (C3)
├── pages/
│   └── overview.py         # Page 1 layout + callbacks
└── assets/
    └── theme.css
```
`ZONE_ORDER` (the corrected 6-bucket list, ascending by median) and a
shared `US_STATES` constant should live in `src/data/clean.py` next to
`zone_family()`, where the buckets are already defined — so the dashboard
and any future notebook work import one shared list instead of each
redefining it (the `US_STATES` set currently only exists ad hoc in
`EDA.ipynb` cell 2).

**Build order**
1. [x] `dashboard/data.py` — load + cache `claims_sample.parquet` with the
   5-column pushdown above, `apply_filters()` helper (year/state/
   zone_family), territory/`UN` exclusion applied at load time.
   `ZONE_ORDER`/`US_STATES` added to `src/data/clean.py` as planned.
   Verified: 22,232 rows (301 territory/unknown rows correctly excluded),
   51 states, filters compose correctly (e.g. `state="TX"` → 3,424 rows,
   matching the count from `EDA.ipynb`'s earlier state-medians check).
2. [x] `app.py` + static layout in `pages/overview.py` with placeholder
   figures — title / control row (year dropdown populated from real data,
   stat toggle, KPI cards, reset) / C1+C2 / C3, no callbacks wired yet.
   Confirmed serving (HTTP 200) in a one-off background smoke test. Going
   forward the user runs the dev server themselves and views it in-browser
   — see `AGENTS.md` "Deployment Target" for why (a backgrounded test
   process couldn't be cleanly stopped afterward).
3. [x] **Validated the C3 click-to-filter risk** (decision #4 above) with a
   throwaway precomputed-statistics `go.Box` figure — native chart click
   works reliably, no button-row fallback needed (see decision #4 above).
4. [x] `charts/choropleth.py`, then wired `filter-state` + the C1 callback
   (year dropdown, stat toggle, map click-to-select-state, reset).
   Verified `build_choropleth()` standalone against real data (51 states,
   `state="TX"` highlight → $35,185, matching earlier checks) and verified
   the page's imports/callback registration are error-free. Not yet
   manually clicked through in-browser — over to the user.
5. [x] `charts/histogram.py` (server-side `np.histogram` binning) +
   `charts/boxplots.py` (precomputed-statistics `go.Box`), then the
   remaining callbacks: zone-click added to `filter-state`, C2 scale
   toggle (separate `c2-scale-state` store, kept out of `filter-state` as
   planned), C2/C3 render callbacks, KPI row (label now updates with the
   stat toggle too). Verified against real data: e.g. year=2020 + TX +
   V(velocity) correctly narrows to 1 claim across KPI/C1/C2/C3; empty
   filters return graceful "no claims" placeholders, not errors.
6. Rerun against `claims_full.parquet` once Phase 1 has been run in `full`
   mode — this is also the real test of the scalability approach above,
   since sample data (22K rows) wouldn't expose a raw-array performance
   problem even if we'd built it the naive way.

### Page 2 — Model UI *(blocked — see below)*

Feature-input form → prediction → explanation (SHAP feature importance,
lift vs. flat-zone baseline). Needs a serialized model artifact.

**Blocker:** nothing downstream of raw ingestion is currently saved by the
notebook — the fitted `best_model` (untuned GBM, refit on the OOT training
set) only ever exists in-memory during a notebook run. Need Ben to export
it (e.g. `joblib.dump(best_model, "models/best_model.joblib")`) before Page
2 can start. Revisit once that's available — don't build against a
placeholder/re-trained-by-us model, since the whole point is to serve
*his* selected, validated model.

## Status

- [x] Repo orientation, `ANALYSIS_SUMMARY.md` + `CLAUDE.md` written.
- [x] Confirmed only the sample data is committed; full/CPI data not yet
      downloaded on this machine.
- [x] Confirmed no processed dataset or fitted model is currently persisted
      anywhere in the pipeline.
- [x] Phase 1 (data pipeline scripts) — done for `mode=sample`; `mode=full`
      not yet run.
- [~] Phase 2 (EDA notebook) — notebook created, Jupyter MCP workflow
      verified end-to-end (including a mid-session Jupyter Lab
      wrong-Python-env fix), first chart (C1 choropleth prototype) built;
      broader profiling pass not done.
- [~] Phase 3 (dashboard) — Page 1 built and functionally verified:
      `data.py`, `app.py`, `pages/overview.py`, all three `charts/*.py`
      modules, and every callback in Build Order steps 1–5 are done. Fixed
      the choropleth's colorbar scaling bug caught during manual testing
      (see "Chart specs" → C1). Not yet done: a full in-browser click-through
      of every interaction together (year, stat, state click, zone click,
      C2 scale toggle, reset, in combination), and Build Order step 6
      (rerun against `claims_full.parquet`). Page 2 blocked on Ben.
