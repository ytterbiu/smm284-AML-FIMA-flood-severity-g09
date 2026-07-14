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

Three pages: **Page 1 (severity overview) built first**, **Page 2
(under-insurance)** next, **Page 3 (model UI)** blocked on Ben's saved
model (see below).

Reference implementation for conventions: `C:\Users\ardih\Data\CMS_Health_Insurance_Exchange\dashboard`
(see its `PLAN.md`/`AGENTS.md`) — same `dcc.Store`-as-single-source-of-truth
filter pattern, same dark-theme/Bootstrap conventions, adapted to this
app's chart set.

### Architecture change for multi-page: global filter-state + shared control row

Page 1 was originally built as if it were the only page — `filter-state`
and the whole control row (year slider, stat toggle, KPI cards, active-filter
chips, reset) lived inside `pages/overview.py`. Adding Page 2 means
promoting these to app-shell level so they're shared rather than
per-page-duplicated:

- **`dcc.Store(id="filter-state")` moves to `app.py`'s top-level layout**,
  outside `dash.page_container`, so it persists across page navigation —
  confirmed intentional (not per-page-independent): selecting a state or
  zone on one page stays selected when you switch pages, letting you
  explore the same claim subset through both the severity and
  under-insurance lens. `zone_family` in particular is shared literally
  identically — clicking a zone on Page 2's by-zone chart sets the exact
  same field Page 1's C3 boxplot clicks do.
- **The control row's year slider / stat toggle / active-filter chips /
  reset button also move to `app.py`**, built by a shared function (e.g.
  `dashboard/components.py: build_control_row()`), so there's exactly one
  copy in the DOM regardless of route, instead of duplicating the same
  markup+IDs per page.
- **The KPI cards are the one part that stays page-aware — in both
  content *and count*** (2 cards on Page 1, up to 4 on Page 2). These live
  in their own `html.Div(id="kpi-row")` in the app shell, populated by one
  callback keyed off `dcc.Location(id="url").pathname` + `filter-state`.
  Each page module exposes its own `build_kpi_cards(filter_state) -> list`
  function (co-located with that page's other logic); the shared callback
  just dispatches to the right one based on the current path.
- The callbacks that currently live in `pages/overview.py` but operate on
  the now-shared control row (`update_filter_state`, `update_stat_buttons`,
  `sync_year_range_slider`, `update_active_filters_display`,
  `remove_filter_via_chip`) move to a shared module too (e.g.
  `dashboard/shared_controls.py`), imported once from `app.py` — so they're
  registered exactly once rather than per-page.
- **`suppress_callback_exceptions=True`** needs adding to the `Dash()`
  constructor: each page's own chart callbacks (`choropleth-map`,
  future under-insurance chart IDs) reference component IDs that only
  exist while *that* page is mounted, which Dash's default startup
  validation would otherwise flag as missing.
- **A simple nav** needs adding — there currently isn't one, since this was
  single-page until now. A `dbc.Nav`/`dbc.NavLink` pair driven by
  `dash.page_registry` in the app shell is enough.

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
This 5-column set was widened by 2 for Page 2's under-insurance charts (see
below); Page 3 (model UI) will need a much wider set (the `NUMERIC`/`CATEG`
feature list from `BE_notes.ipynb` §7) and should get its own load path
rather than growing this shared one further.

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

### Page 2 — Under-Insurance

Ports `BE_notes.ipynb` §14 ("Behavioural rider: under-insurance") — compares
`totalBuildingInsuranceCoverage` to `buildingReplacementCost` — into two
interactive charts, sharing the global filter-state and control row from
Page 1 (see "Architecture change" above).

**Data**: same cached `get_df()` DataFrame as Page 1, widened by 2 columns
— `totalBuildingInsuranceCoverage` and `buildingReplacementCost` — added to
`DASHBOARD_COLUMNS`. A second, *local* validity gate applies on top of the
usual year/state/zone filters: only rows where both columns are present
and `buildingReplacementCost > 0` count toward this page's charts/KPIs
(mirrors the notebook's `ok = rc.notna() & cov.notna() & (rc > 0)` mask).
Coverage ratio (`coverage / replacement_cost`) is clipped at 2, matching
the notebook.

**Status bands** (shared across both charts, same 3 colors and thresholds
everywhere on this page):
| Band | Threshold | Color |
|---|---|---|
| Adequately insured | ratio ≥ 0.8 | neutral (e.g. steel blue) |
| Under-insured | 0.5 ≤ ratio < 0.8 | amber |
| Severely under-insured | ratio < 0.5 | red |

**Layout (top → bottom)**, same control-row-then-charts shape as Page 1:
```
(shared control row + page-aware KPI row — see below)
----------------------------------------------------------------
C4 (coverage-ratio histogram, colored by band)  |  C5 (100%-stacked
                                                 |  bar: status share by zone)
```

**Chart specs**:
- **C4 — coverage-ratio histogram**: same server-side `np.histogram`
  binning discipline as C2 (payload size independent of row count), but
  bin edges are constructed as **three concatenated `linspace` ranges**
  (0→0.5, 0.5→0.8, 0.8→2.0) rather than one uniform range, so 0.5 and 0.8
  always land exactly on a bin boundary — no single bar straddles two
  status bands. Each bar colored by whichever band its bin falls in.
- **C5 — by-zone stacked bar**: one 100%-stacked bar per `zone_family` (in
  the existing `ZONE_ORDER`), three segments (adequately insured /
  under-insured / severely under-insured) summing to 100%, same 3 colors
  as C4 — an upgrade from the notebook's single-metric version (which only
  plotted share-under-80%). **Clickable**, same as Page 1's C3: clicking a
  zone's bar sets the shared `zone_family` filter (highlight/dim, not a
  self-filter — same "never filter yourself" rule as C3).

**Page-aware KPI row** (Page 2's 4 cards, replacing Page 1's 2 in the same
`html.Div(id="kpi-row")` slot):
1. Coverage Ratio (Median/Mean, per the shared `stat` toggle — confirmed
   still meaningful here as the reference stat, even though the notebook
   itself only ever printed a median)
2. Properties Assessed (count passing the local validity gate, on top of
   the global filters — this page's equivalent of Page 1's "Claims" count)
3. % Under-insured (< 80%)
4. % Severely under-insured (< 50%)

**Build order**
1. Do the multi-page architecture change first (Store + control row →
   `app.py`, `suppress_callback_exceptions=True`, nav, page-aware
   `kpi-row` callback) — Page 1 needs to keep working identically
   afterward before Page 2 is added on top.
2. Widen `DASHBOARD_COLUMNS`; add the coverage-ratio + validity-gate logic
   (co-located with Page 2's chart code, not promoted into `data.py`,
   since it's specific to this page).
3. `charts/coverage_histogram.py` (C4) — validate the three-band bin
   construction against real data before wiring it to filters.
4. `charts/under_insurance_by_zone.py` (C5) — validate the stacked-bar
   click-to-filter behaviour the same way C3's was validated (Build Order
   step 3 on Page 1) — expected to work the same way, but worth a quick
   sanity check given it's a new chart type (`go.Bar` with `barmode="stack"`
   rather than `go.Box`).
5. Wire `pages/under_insurance.py`'s layout + callbacks; confirm Page 1
   still works unchanged after the shared-architecture refactor.

### Model section (Pages 3+) — multiple pages, not one

Originally scoped as a single "Page 3 — Model UI." Expanded on request into
four sub-pages, since the model story has four genuinely different
outputs to show:

- **Model performance** — CV/OOT comparison across models (MAE, RMSE, R²,
  D²)
- **Feature importance / SHAP**
- **Lorenz curve / double lift charts**
- **Feature input UI + prediction**, across multiple models

**None of these participate in the shared `filter-state`/control row from
Pages 1–2.** They're all properties of a *fitted model* evaluated once on a
fixed OOT split (or, for the predict page, a hypothetical single property),
not the currently-filtered claims subset — there's no meaningful "state"/
"zone"/"year" filter to apply to a SHAP summary or a Lorenz curve. The
shared control row is hidden across this entire section (a pathname check
in the app shell, e.g. `pathname.startswith("/model")`), same underlying
mechanism as the page-aware `kpi-row`, just hiding rather than swapping
content.

**Data contract — RESOLVED.** A teammate exported a full artifact bundle to
`exports/dashboard/` (`model_glm.joblib`/`model_gbm.joblib` committed;
`model_rf.joblib` gitignored — too large, shared manually, integrity
verified via `checksums.txt`'s SHA-256, matches exactly). Checked every
file directly and test-loaded/predicted all three models on real sample
rows before marking anything unblocked:

| Sub-page | Needed | Delivered as | Status |
|---|---|---|---|
| Model performance | OOT scoreboard (MAE/RMSE/R²/D²) | `oot_scoreboard.csv` — 5 models: 3 baselines + GLM + RF + GBM | ✅ **Unblocked** |
| Feature importance / SHAP | SHAP values + feature names | `shap_mean_abs_by_feature.csv` (bar chart) **+** `shap_sample_raw_features.parquet` (2000×15) **+** `shap_values_oot_sample.npz` (`shap_values`, `X_transformed`, `feature_names`, `base_value`, `row_index`) — enough for a full beeswarm plot, not just a bar chart | ✅ **Unblocked**, richer than originally scoped |
| Lorenz curve / double lift | Fitted model artifact | `model_{glm,gbm,rf}.joblib`, all three loaded + test-predicted successfully | ✅ **Unblocked** — compute ourselves against our own OOT-filtered `claims_{mode}.parquet` (verified: all 14 `NUMERIC`+`CATEG` columns already present there, no re-run of Phase 1 needed). Bonus: `oot_scoreboard_insurance.csv` already has a per-model **Gini** column as a sanity-check reference point. |
| Feature input + prediction | Fitted model artifact(s) | Same three `.joblib` files + `baseline_zone_means.csv` (trivial baseline lookup, no artifact needed) | ✅ **Unblocked** |

**Artifacts and how to use them** (`exports/dashboard/`):
- `metadata.json` — the full contract: exact `input_schema` (matches our
  known `NUMERIC`/`CATEG` below byte-for-byte), model descriptions,
  `primary_model: "gbm"`, `prediction_business_rule`, `baseline_rule`,
  `random_state: 9`. Versions (`sklearn`/`numpy`/`pandas`/`shap` all pinned
  identically to our own `.venv` — only the Python patch version differs,
  which doesn't affect pickle compatibility) — checked, no environment risk.
- `dashboard_support.py` — **always load models via its `load_model(path)`**,
  never bare `joblib.load()`. The RF model is wrapped in a custom
  `SmearedLogTargetRegressor` (Duan's smearing correction) pickled from
  inside the notebook — `load_model()` registers the notebook-defined
  classes under `__main__` before unpickling, which RF specifically
  requires; harmless no-op for GLM/GBM, so use it uniformly for all three
  rather than branching per model. Also exposes `clip_at_coverage(pred, X)`
  — the coverage-cap business rule is applied *manually after* `.predict()`,
  not baked into the pipelines themselves; always call it.
- `oot_scoreboard.csv` / `oot_scoreboard_insurance.csv` / `shap_*` /
  `baseline_zone_means.csv` — plain CSV/parquet/npz, load directly with
  Polars/numpy.

```python
NUMERIC = ["totalBuildingInsuranceCoverage", "totalContentsInsuranceCoverage",
           "deductible_amount", "building_age", "crsClassificationCode",
           "elevationDifference"]
CATEG = ["zone_family", "occupancy_class", "state", "floors_cat",
         "basement_cat", "postFIRMConstructionIndicator_i",
         "elevatedBuildingIndicator_i", "primaryResidenceIndicator_i"]
```

**Data loading**: this section needs a much wider column set than Pages
1–2's 7-column `DASHBOARD_COLUMNS` (all of `NUMERIC`/`CATEG` above, plus
`TARGET` for the Lorenz/lift charts' actuals). Gets its **own load path**
(`dashboard/model_data.py`) rather than growing the shared
`get_df()`/`DASHBOARD_COLUMNS` further — confirmed all 14 columns already
exist in `claims_sample.parquet`, so this is just a new pushdown column
list, not a pipeline change.

**Logistics note**: `model_rf.joblib` is gitignored and was shared
manually (same situation as `data/raw/`) — needs a documented manual-
placement step for teammates who don't have it (README/`AGENTS.md`), same
pattern as the raw FEMA download.

**Build order**
1. [x] Nav/routing: added the 4 `/model/*` pages (`pages/model_{performance,
   importance,lift,predict}.py`, placeholder layouts, explicit `order=2..5`
   — also added `order=0/1` to the existing two pages for deterministic
   nav ordering), and hid the shared control row across the section via a
   `control-row-wrapper` div + pathname-keyed callback in `app.py`.
   Verified: all 6 pages register in the right order, control row/KPI row
   correctly hide on `/model/*` and stay visible/unaffected on `/` and
   `/under-insurance`.
2. [x] `dashboard/model_data.py` — `get_model_df()`/`get_oot_df()` (wide
   feature set + `TARGET`, `NUMERIC`/`CATEG`/`TARGET` derived from
   `metadata.json` rather than duplicated), `get_model(name)` (cached,
   via `dashboard_support.load_model()`), `predict(name, X)` (clipped at
   coverage), `predict_baseline(zone_family)`. Verified: 22,533 rows
   loaded, 2,445 in the OOT window, all 3 models load, and — the real
   compatibility test — predictions run correctly against rows from *our
   own* processed parquet (not just the teammate's isolated SHAP sample),
   with GBM/RF visibly more differentiated than GLM against actuals,
   matching the existing narrative.
3. **Model performance page**:
   - [x] `charts/oot_scoreboard.py` (C6) — small multiples, one horizontal-
     bar panel per metric (MAE/RMSE/D²/R², in that reading order), same
     model order fixed across all four panels (ascending MAE) so a
     model's position is trackable across metrics. Fixed identity colors
     per model (`MODEL_COLORS`, GBM anchored to palette slot 1 as
     `metadata.json`'s `primary_model` — reused across future Model-section
     pages, same convention as Page 2's `STATUS_COLORS`). Deliberately no
     on-chart text ranking the metrics (e.g. no "D² is the fair one"
     annotation) — panel order/position only, data shown for all four.
     Genuinely useful finding this surfaced: RF's D² (−0.469) is far worse
     than its MAE/R² rank would suggest — worth keeping visible now that
     it's built rather than only in a table.
   - [ ] Tuning-diagnostics chart from `cv_results_*`/`tuned_params.json`
     (the one thing buildable pre-export) as a secondary panel — not done
     yet, same page.
4. [x] **Feature importance / SHAP page** — GBM-only throughout (confirmed
   directly from the notebook: cell 85 computes SHAP against `best_model`
   exclusively, and `shap.TreeExplainer` is tree-model-only anyway; no
   GLM/RF equivalent exists to show). Three charts:
   - `charts/shap_importance.py` — C8 (bar chart, `shap_mean_abs_by_
     feature.csv`) + C9 (beeswarm, reimplemented in Plotly from
     `shap_values_oot_sample.npz`'s `shap_values`/`X_transformed`/
     `feature_names` — the `shap` library was only needed to *compute*
     these, already done by the teammate; no `shap`-library plotting code
     runs at dashboard runtime). Feature names cleaned of the
     `money__`/`cat__`/`num__` ColumnTransformer prefix for readability.
   - `charts/permutation_importance.py` — C10, genuinely new: not exported
     by the teammate (checked `exports/dashboard/` — no such file), but
     fully replicable ourselves, since `sklearn.inspection.
     permutation_importance` is model-agnostic (no custom-class dependency
     like RF's smearing wrapper) and works directly against
     `model_gbm.joblib` + our own OOT data. Dual-scored (MAE + gamma
     deviance, matching the notebook's own framing), on the raw 14
     features (not the ~99 one-hot-expanded ones SHAP uses), deliberately
     unclipped to match the notebook's choice. Computed once, cached
     (~7s one-time cost, not per page view) — verified numbers, including
     a real finding: `state` shows *negative* importance on our
     ~2,445-row OOT sample (shuffling it slightly improves MAE) — read as
     sampling noise given the small sample, not evidence `state` is
     harmful; also a useful cross-check against SHAP's per-state findings
     (which look at individual one-hot state columns, a finer-grained
     notion of importance than shuffling the whole feature at once).
   - Startup cost note: this page's layout builds the permutation
     importance chart eagerly (not behind a callback), adding ~7s to app
     import time (~11s total vs. near-instant before) — one-time per app
     run, cached after.
   - Post-build fixes from user review: (1) beeswarm colorscale switched
     from the palette's sequential blue ramp to `shap` library's own
     `#008bfb`→`#ff0051` (blue→red) — a deliberate, scoped exception to
     the usual sequential-hue convention, since matching this specific
     well-known external convention was requested. (2) Permutation
     importance chart had a real ordering bug: copied `oot_scoreboard.py`'s
     "sort ascending + `autorange=reversed`" recipe verbatim, but that
     recipe's correctness there relied on ascending-MAE-happens-to-mean-
     best-first — the opposite semantic holds for `mae_increase` (higher =
     more important), so it needed a descending sort instead. Fixed and
     verified the array order directly. (4) SHAP bar chart recolored to
     match `shap` library's own high-value color (`#ff0051`) and given
     value labels, per a reference screenshot; both charts' "outside" text
     labels were getting clipped/overlapping error-bar whiskers —
     fixed via explicit axis-range padding (bar chart) and manually-placed
     annotations positioned past the whisker tip, not `textposition=
     "outside"` (permutation importance panels).
   - **Full-data scalability, addressed proactively before it was hit**:
     `permutation_importance`'s cost is ~linear in row count (one
     `model.predict()` per feature × repeat). Sample-mode OOT data
     (~2,445 rows) never approached a problem, but full-mode OOT data
     (~213,746 rows, per the notebook's own figures) would take an
     estimated **~10 minutes** uncapped — computed eagerly at page load,
     that's not acceptable. Fix: capped at `MAX_ROWS = 50_000`, directly
     mirroring `BE_notes.ipynb` cell 60's own `SUB = min(50_000,
     len(X_test))` — Ben hit the identical cost concern and already solved
     it the same way; this was just an omission on our side since
     sample-mode data never got close to the cap. Verified the cap is a
     true no-op at current scale (identical result, ~7s, unchanged). Even
     capped, full mode would still cost ~1-2 minutes at first access
     (50K rows vs. today's 2,445) — worth revisiting whether to move this
     from eager (built into the page layout) to lazy (behind a callback,
     triggered on page visit with a loading spinner) once full mode is
     actually used, so it doesn't block the rest of the app's startup.
5. [x] **Predict page** (built ahead of pages 3's tuning chart and page 4,
   at the user's request) — `pages/model_predict.py`: 14-field input form
   (6 `NUMERIC` number inputs + 8 `CATEG` dropdowns), options/defaults
   derived dynamically from `model_data.get_model_df()` (not hardcoded —
   `state` restricted to the 50+DC via `US_STATES`, `zone_family` ordered
   via `ZONE_ORDER`, numeric-coded fields like `floors_cat` sorted
   numerically with "missing" last). Shows all 4 models side by side
   (Baseline/GLM/RF/GBM), per the original "multiple models" ask — result
   cards (reusing `kpi-card` styling) + `charts/predict_comparison.py`
   (C7, same `MODEL_COLORS` as the performance page's C6 — moved that
   constant into `model_data.py` as the true shared location once a second
   chart needed it). Verified: baseline prediction matches
   `baseline_zone_means.csv` exactly; a real finding surfaced during
   testing — at the default (median/mode-of-every-column) starting values,
   RF predicts noticeably higher ($142K) than GLM/Baseline/GBM (~$55-63K).
   Confirmed this isn't a bug (real historical rows tested earlier had
   RF/GBM tracking closely) — it's the log1p + Duan's-smearing
   back-transform amplifying a synthetic, independently-median/mode'd
   combination that may not resemble any real observed property.
6. **Lorenz / double lift page**: filter our own `claims_{mode}.parquet` to
   `yearOfLoss >= 2020` (the OOT window per `metadata.json`), score with
   all three models via `model_data`, compute Lorenz curves (cumulative %
   loss vs. cumulative % policies, ranked by predicted severity) and a
   double lift chart (GBM vs. RF, or vs. baseline) ourselves.

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
      (see "Chart specs" → C1). Also fixed post-launch: year filter changed
      from a single nullable year to an always-present `year_range` (range
      slider), and active-filter chips added (with click-to-remove). Not
      yet done: a full in-browser click-through of every interaction
      together, and Build Order step 6 (rerun against `claims_full.parquet`).
- [~] Page 2 (under-insurance) — built: multi-page architecture change done
      (`shared_controls.py` extracted; `filter-state`/control row/nav/
      kpi-row now live in `app.py`'s shell); `charts/status_bands.py`
      (shared 3-band logic), `charts/coverage_histogram.py` (C4),
      `charts/under_insurance_by_zone.py` (C5), and
      `pages/under_insurance.py` all done. Verified against real data:
      Page 1 KPIs/charts still work identically post-refactor; Page 2 KPIs
      (88% median coverage ratio, 15,805 properties assessed, 41%/20%
      under-insured/severely) and C4/C5 chart traces all check out.
      In-browser click-through done: nav between pages, C5's stacked-bar
      click-to-filter all confirmed working. Caught and fixed a real bug in
      the process — `shared_controls.update_filter_state` originally
      bundled `choropleth-map`/`zone-boxplots` (Page 1) and
      `zone-status-bars` (Page 2) `clickData` into one callback, which
      threw a runtime "nonexistent object" error the moment any one of them
      fired (`suppress_callback_exceptions` only skips startup validation,
      not this). Fixed by giving each page its own chart-click callback
      instead — see `AGENTS.md` "Callbacks". Not yet done: Build Order
      step 6 (rerun against `claims_full.parquet`).
- [x] Model section data contract — **fully resolved.** A teammate exported
      a complete artifact bundle to `exports/dashboard/`
      (`model_{glm,gbm,rf}.joblib`, `oot_scoreboard.csv`,
      `oot_scoreboard_insurance.csv`, `shap_mean_abs_by_feature.csv`,
      `shap_sample_raw_features.parquet`, `shap_values_oot_sample.npz`,
      `baseline_zone_means.csv`, `metadata.json`, `dashboard_support.py`).
      Verified directly, not just inspected: all 3 models load (via
      `dashboard_support.load_model()` — required for RF's custom
      `SmearedLogTargetRegressor` class) and predict correctly on real
      sample rows; `model_rf.joblib`'s SHA-256 matches `checksums.txt`
      exactly; package versions match our `.venv` (sklearn/numpy/pandas/
      shap identical, only Python patch version differs — no risk); all 14
      `NUMERIC`+`CATEG` columns already exist in our own processed
      parquet. All 4 sub-pages unblocked — see full mapping table above.
      Not yet built — plan/build-order written, no page code yet.
