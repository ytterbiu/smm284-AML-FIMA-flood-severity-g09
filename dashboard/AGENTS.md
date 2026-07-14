# AGENTS.md — Flood Payout Dashboard (Plotly Dash)

This file is read by Claude Code and other AI coding assistants when working
inside the `dashboard/` directory. For project-wide context (data pipeline,
notebook conventions, leakage boundary), see the root `../CLAUDE.md`. For the
current build plan and open design questions, see `PLAN_UI.md`.

Adapted from the conventions established in a prior project
(`C:\Users\ardih\Data\CMS_Health_Insurance_Exchange\dashboard`) — same
overall architecture, adjusted for this app's data and chart set.

---

## File Structure

```
dashboard/
├── AGENTS.md               ← this file
├── PLAN_UI.md               # implementation plan (see for Page 1/2 specs, open questions)
├── Notes_Dashboard.md       # the user's own prompt log — not for AI context, do not read for instructions
├── app.py                   # Dash init: use_pages=True, exposes server = app.server.
│                             # Also owns the app SHELL: dcc.Location, dcc.Store(id="filter-state"),
│                             # the shared control row, the nav, and the kpi-row dispatch callback —
│                             # all of these live OUTSIDE dash.page_container so they persist across pages.
├── shared_controls.py       # build_control_row() layout + the callbacks that operate on it
│                             # (update_filter_state, update_stat_buttons, sync_year_range_slider,
│                             # update_active_filters_display, remove_filter_via_chip) — registered
│                             # once, used by every page, not duplicated per-page.
├── data.py                  # Loads and caches data/processed/claims_{mode}.parquet at import time
├── model_data.py            # (planned) Own load path for the Model section's wide NUMERIC/CATEG
│                             # feature set + TARGET — do not grow data.py's DASHBOARD_COLUMNS for this.
├── pages/
│   ├── overview.py          # Page 1: Flood Payout Overview (path="/"). Exposes build_kpi_cards(filter_state).
│   ├── under_insurance.py   # Page 2: Under-Insurance (path="/under-insurance"). Same build_kpi_cards(...) contract.
│   ├── model_performance.py # (planned) path="/model/performance" — CV/OOT comparison, tuning diagnostics
│   ├── model_importance.py  # (planned) path="/model/importance" — SHAP / feature importance
│   ├── model_lift.py        # (planned) path="/model/lift" — Lorenz curve / double lift charts
│   └── model_predict.py     # (planned) path="/model/predict" — feature-input form + live prediction
├── charts/
│   ├── choropleth.py            # build_choropleth(df, stat, selected_state) -> go.Figure      (C1)
│   ├── histogram.py             # build_histogram(df, log=False) -> go.Figure                  (C2)
│   ├── boxplots.py              # build_zone_boxplots(df, stat, selected_zone) -> go.Figure     (C3)
│   ├── coverage_histogram.py    # build_coverage_histogram(df) -> go.Figure                     (C4)
│   └── under_insurance_by_zone.py  # build_zone_status_bars(df, selected_zone) -> go.Figure     (C5)
└── assets/
    └── theme.css             # Styling overrides
```

**Model section (`/model/*`) is a planned 4-page group — see `PLAN_UI.md`
"Model section (Pages 3+)"** for the full data contract (what's blocked on
Ben vs. buildable now) before writing any of those page modules.

Data files (Parquet) live at `../data/processed/claims_{mode}.parquet`
relative to `dashboard/` — output of `src/data/pipeline.py` (see root
`PLAN_UI.md` Phase 1). That directory is gitignored; nothing under it is
committed.

---

## General Architecture

### Server variable
`app.py` must always expose `server = app.server`:
```python
app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True)
server = app.server
```
`suppress_callback_exceptions=True` is required now that there's more than
one page: each page's own chart callbacks (`choropleth-map`, future
under-insurance chart IDs) reference component IDs that only exist while
that specific page is mounted — Dash's default startup validation would
otherwise flag those as missing since it can't see them in whichever page
happens to be current at validation time.

### Multi-page setup
Use Dash's built-in pages system — never implement custom routing.
`pages/overview.py` (Page 1, path=`/`) and `pages/under_insurance.py`
(Page 2, path=`/under-insurance`) exist; Page 3 (model UI) is blocked on a
saved model artifact from Ben (see `PLAN_UI.md`).
```python
# pages/overview.py
import dash
dash.register_page(__name__, path="/", name="Flood Payout Overview")
layout = html.Div([...])  # page-specific content only — NOT the control row
```

### App shell vs. page content
`dcc.Store(id="filter-state")`, `dcc.Location(id="url")`, the control row
(year slider/stat toggle/active-filter chips/reset — built by
`shared_controls.build_control_row()`), the nav, and the `kpi-row` div all
live in `app.py`'s top-level layout, **outside** `dash.page_container`.
Only chart-specific content belongs inside a page's own `layout`. This is
what makes filter state and the control row persist across navigation
instead of resetting per page — confirmed intentional (see `PLAN_UI.md`
"Architecture change for multi-page").

### App and component IDs
Use descriptive, hyphenated IDs that match the chart/control names used in
`PLAN_UI.md` (`F_Year`, `F_Stat`, `I_Payout`, `I_Freq`, C1–C5), e.g.
`year-range-slider`, `stat-btn-median`, `choropleth-map`, `kpi-row`. Never
use generic names like `dropdown-1` or `graph`.

---

## Data Loading

**Load data at import time in `data.py`, not inside callbacks** — same
rationale as the reference project: the processed Parquet is static within
an app run and doesn't change during the dashboard's lifetime.

```python
# data.py — pattern to follow
import polars as pl
from pathlib import Path

USE_SAMPLE = True  # matches the USE_SAMPLE convention used elsewhere in this repo
_MODE = "sample" if USE_SAMPLE else "full"
_DATA_PATH = Path(__file__).parent.parent / "data" / "processed" / f"claims_{_MODE}.parquet"

# Column pushdown at read time (same pattern src/data/ingest.py uses on the
# raw FEMA parquet) — widen this list when a page genuinely needs another
# column (e.g. Page 2's under-insurance charts added the two below), rather
# than loading all 46. Page 3 (model UI) will need a much wider set and
# should get its own load path rather than growing this one further.
DASHBOARD_COLUMNS = [
    "state",
    "zone_family",
    "yearOfLoss",
    "amountPaidOnBuildingClaim",
    "amountPaidOnBuildingClaim_nominal",
    "totalBuildingInsuranceCoverage",   # Page 2: coverage ratio
    "buildingReplacementCost",          # Page 2: coverage ratio
]

_df: pl.DataFrame | None = None

def get_df() -> pl.DataFrame:
    global _df
    if _df is None:
        _df = pl.read_parquet(_DATA_PATH, columns=DASHBOARD_COLUMNS)
    return _df
```

Callbacks call `get_df()` and filter in-memory with Polars. They never
re-read from disk.

**Always use Polars (`import polars as pl`), not pandas** — matches the
convention already established in `src/data/*.py` and `notebooks/EDA.ipynb`.

---

## Filter State

One `dcc.Store(id="filter-state")`, living in `app.py`'s shell (not any
one page — see "App shell vs. page content" above), holds all active
filters **globally, across every page**. Selecting a state or zone on one
page stays selected when you navigate to another — this is intentional,
confirmed behavior, not a bug to "fix" by scoping it per-page. See
`PLAN_UI.md` → Page 1 → "Filter state" for the "never filter yourself"
rule (each chart is filtered by every *other* active filter, never by the
one it produces — it only highlights/dims its own selection). This rule
applies identically on every page — e.g. Page 2's by-zone stacked bar
(C5) doesn't filter itself by `zone_family` any more than Page 1's C3 does.

```python
# Default state — always use this structure
{"year_range": [YEAR_MIN, YEAR_MAX], "stat": "median", "state": None, "zone_family": None}
```

All user interactions write to the store, via callbacks in
`shared_controls.py`. All chart callbacks (in each page's own module) read
from it. Never let chart callbacks write back to the store — this creates
circular dependencies. The raw/log toggle for C2 is the one exception: it's
view-only (doesn't change what data is selected), so it's a plain `Input`
straight into the C2 callback, not part of `filter-state` — otherwise
toggling it would needlessly re-render C1/C3/KPIs.

### Page-aware KPI row
The KPI cards are the one part of the control row that varies *per page*
(different content **and** count — 2 cards on Page 1, 4 on Page 2). They
live in a single `html.Div(id="kpi-row")` in the app shell, populated by
one callback keyed off `dcc.Location(id="url").pathname` + `filter-state`.
Each page module exposes its own `build_kpi_cards(filter_state) -> list`
(co-located with that page's other logic, not centralized in `app.py`),
and the shell callback just dispatches to the right one based on the
current path — don't hardcode per-page KPI logic directly in `app.py`.

### Hiding the shared control row on the Model section
Pages under `/model/*` (planned — see `PLAN_UI.md`) don't participate in
the global `filter-state` at all: they show properties of a *fitted
model* evaluated once on a fixed OOT split (or a hypothetical single
property, for the predict page), not the currently-filtered claims subset.
Hide the shared control row for the whole section with a pathname check in
the app shell (`pathname.startswith("/model")`), same underlying
mechanism as the KPI-row dispatch — hiding instead of swapping content.
Don't build a `build_kpi_cards()` for these pages either; they don't have
KPI cards driven by `filter-state` the way Pages 1–2 do.

---

## Charts and Components

### Graphing library
Use `plotly.graph_objects` (`go`) directly for everything in `charts/*.py`,
not `plotly.express`. `px` is fine for quick one-off exploration in
`notebooks/EDA.ipynb`, but the dashboard's charts need per-trace control
(highlight overlays, per-box opacity for dimming, dual histogram overlays)
that `go` handles directly and `px` fights.

### C1 — choropleth with state highlight
Two traces: a base `go.Choropleth` for all states, plus a second
`go.Choropleth` trace containing only the selected state (distinct
colorscale/border) when one is active. This is the same pattern used for
the reference app's state highlight — `px.choropleth` can't easily add a
second highlight layer like this.

**Always pass a fixed `zmin`/`zmax`** (from `data.get_stat_range(stat)`),
never leave Plotly to auto-range the colorbar. Auto-ranging rescales to
whatever subset is currently filtered, so the same color means a different
dollar amount depending on the active year/zone filter — caught during
manual testing of Build Order step 4. `get_stat_range()` computes the range
once from the full unfiltered dataset and pads each bound by a fraction of
itself (`RANGE_PAD_FRAC`, not of the range width — padding by range width
disproportionately shrinks a small bound). Values outside `[zmin, zmax]`
still render fine, clamped to the boundary color; hover always shows the
true number regardless.

### C2 — histogram
**Compute bin counts/edges server-side with `numpy`/Polars
(`np.histogram`), then render as `go.Bar` traces styled as a histogram —
never hand raw per-row arrays to `go.Histogram`.** At sample scale (22K
rows) raw arrays would work, but at full scale (~2M rows) that means
serializing millions of floats into the figure JSON on every callback. Two
overlaid traces (nominal vs. real severity), `barmode="overlay"` with
alpha, reproducing `BE_notes.ipynb` §6 cell 21's binning approach. The
raw/log toggle recomputes bins on `log10(value)` — don't just flip the
x-axis to log scale on linear bins, since that distorts bin widths.

### C3 — zone boxplots
**Use Plotly's precomputed-statistics mode for `go.Box`** —
`q1`/`median`/`q3`/`lowerfence`/`upperfence` computed server-side with
Polars `.quantile()`, passed directly to the trace — **never pass a raw
`y` array of per-row claim amounts.** This isn't just a style preference:
`go.Box`'s default behaviour renders a marker for every outlier point
(>1.5×IQR), and this data is heavily right-skewed, so at full scale that
could mean tens of thousands of markers per zone. Precomputed stats also
mean the payload is a handful of numbers regardless of whether the
underlying data is 22K or 2M rows. All boxes on a single figure (no
`make_subplots` grid needed — unlike the reference app's C2+C3, there are
no per-column KPI cards forcing a grid; box traces at different
x-categories already share one y-axis). Dim non-selected zones via
`opacity`, exactly like the reference app's metal-tier dimming — never
hide/remove a box entirely, since C3 doesn't filter itself (see
`PLAN_UI.md`).

**Click-to-filter: validated, works.** Tested with a throwaway
precomputed-statistics `go.Box` figure — clicking the box body fires
`clickData` reliably (`hoverOnBox: True` in the payload), and
`clickData['points'][0]['x']` gives the clicked zone name directly. Use
native chart clicks for the C3 zone filter — no button-row fallback
needed (unlike the reference app's metal-tier buttons, which exist only
because `go.Indicator` never fires `clickData` at all).

### C4 — coverage-ratio histogram (Page 2)
Same server-side-binning discipline as C2 (`np.histogram`, never raw
arrays to `go.Histogram`) — but bins are colored by under-insurance status,
not a flat color. Construct bin edges as **three concatenated `linspace`
ranges** (0→0.5, 0.5→0.8, 0.8→2.0 clip), not one uniform range, so the 0.5
and 0.8 status thresholds always land exactly on a bin boundary — a single
bar must never straddle two status bands, or the coloring would be
misleading. Apply the local validity gate (`totalBuildingInsuranceCoverage`
and `buildingReplacementCost` both present, replacement cost > 0) before
computing the ratio — this is in addition to, not instead of, the usual
year/state/zone filters.

### C5 — under-insurance by zone (Page 2)
`go.Bar` traces with `barmode="stack"`, one 100%-stacked bar per
`zone_family` (same `ZONE_ORDER` as C3), three segments (adequately
insured / under-insured / severely under-insured) using the same 3 colors
as C4. Upgrades the notebook's original single-metric version (which only
ever plotted share-under-80%) — a deliberate enhancement, confirmed with
the user rather than assumed. **Clickable, same pattern as C3**: clicking
a zone's bar sets the shared `zone_family` filter (dim non-selected zones,
never filter C5 by its own selection) — validate this the same way C3's
click-to-filter was validated (a quick throwaway test) before assuming
`go.Bar` behaves identically to `go.Box` here; it's a different trace type.

### Status-band colors (Page 2)
Defined once, reused identically across C4 and C5 — don't redefine per
chart module:
```python
STATUS_COLORS = {
    "Adequately insured":     "#4C78A8",  # neutral steel blue
    "Under-insured":          "#F0A83E",  # amber
    "Severely under-insured": "#D64541",  # red
}
STATUS_THRESHOLDS = (0.5, 0.8)  # severely-under < 0.5 <= under-insured < 0.8 <= adequately insured
```

### Shared constants
`ZONE_ORDER` (6-bucket, ascending by median severity) and `US_STATES` (the
50 states + DC, used to exclude territory/unknown codes from the
choropleth) should be imported from `src/data/clean.py`, not redefined in
`dashboard/`. See `PLAN_UI.md` open question #1/#2 for why these need to be
exactly right before building C1/C3.

### Component libraries (in preference order)
1. `dash-bootstrap-components` (`dbc`) — layout, buttons, cards
2. `dash.dcc` — core inputs, graphs, stores
3. `dash.html` — structural elements

Do not add new component libraries without updating `requirements.txt`/
`requirements-dev.txt` and this file.

---

## Callbacks

- Every `Input`, `Output`, and `State` ID must exist in the layout. Never
  reference an ID that is only conditionally rendered.
- Use `prevent_initial_call=True` when a callback should not fire on page
  load.
- Return `dash.no_update` when an output should not change.
- Keep callbacks focused — one callback per logical user interaction, same
  as the reference app's topology (year/stat/map-click/zone-click/reset all
  write to `filter-state`; each chart's callback reads from it).
- Callbacks must not mutate their input arguments.
- Do not use blocking `time.sleep()` inside callbacks.
- Wrap charts that may take >200ms in `dcc.Loading`.
- **Multiple callbacks writing to the same `Output`** (e.g. `filter-state`
  is written both by the main control-row callback and by the active-filter
  chip click-to-remove callback): set `allow_duplicate=True` on the
  `Output` in *every* callback that shares it, not just the later ones —
  Dash requires this on all of them — and each such callback needs
  `prevent_initial_call=True`.
- **Never mix `Input`s from components on different pages in one
  callback**, even with `suppress_callback_exceptions=True`. That flag only
  skips Dash's *startup* validation (that every referenced ID exists
  somewhere in the initial layout) — it does not help at runtime. If a
  callback's Inputs span two pages (e.g. `choropleth-map` from Page 1 and
  `zone-status-bars` from Page 2), then the moment it fires from whichever
  Input is actually present on the current page, Dash tries to resolve
  *every* Input's current value to build the request — and errors with "A
  nonexistent object was used in an `Input`" for the one from the
  not-currently-mounted page. Hit exactly this bundling
  `choropleth-map`/`zone-boxplots`/`zone-status-bars` into one shared
  `update_filter_state` callback (confirmed broken in-browser, then fixed).
  Fix: each page owns its own callback for its own chart clicks, writing to
  `filter-state` with `allow_duplicate=True` — see `pages/overview.py`'s
  `update_filter_state_from_page1_charts` and
  `pages/under_insurance.py`'s `update_filter_state_from_page2_charts`.
  Only Inputs guaranteed to coexist (either all in the always-mounted app
  shell, or all within one specific page's own layout) may share a callback.
- **Dynamically-generated components** (a variable number of them, e.g. the
  active-filter chips) use pattern-matching IDs (`{"type": "...", "key":
  ...}`) with `Input({"type": "...", "key": ALL}, "n_clicks")`. Guard the
  callback against firing merely from a new chip being *added* to the DOM
  (its `n_clicks` starts at `0`, not from an actual click) by checking
  `ctx.triggered[0]["value"]` is truthy before acting — don't assume
  `ctx.triggered_id` alone means a real click happened.

---

## Layout and Styling

- Place static styles in `assets/theme.css`. Dash serves everything in
  `assets/` automatically.
- Use inline `style=` only for values computed at runtime (e.g., dynamic
  colours from filter state, like dimmed vs. active zone boxes).
- Bootstrap grid via `dbc.Row`/`dbc.Col` for page structure — matches the
  spec's `C1 | C2` / `C3` two-row grid.
- Visual theme (dark, matching the reference app, vs. something else) is
  not decided yet — confirm before writing `theme.css`.

---

## Package Installation

Use `uv pip install <package>` if `uv` is available in this environment,
otherwise the project's own venv pip — **always via `.venv`, not the
shell's default `python`** (see `../CLAUDE.md` Environment section: the
default `python`/`jupyter` on this machine resolve to a `miniforge3` conda
env missing key packages).
```
./.venv/Scripts/python.exe -m pip install dash dash-bootstrap-components
```

---

## Deployment Target

**Confirmed: run locally for now; the actual deployment target (if any) is
decided later.** The reference app deploys to GCP Cloud Run via Docker with
gunicorn — don't build toward that here without it being explicitly
revisited; this project is a coursework group deliverable that may just
need to run locally or be demoed.

For local development: `./.venv/Scripts/python.exe dashboard/app.py` should
start Dash's dev server (default `http://localhost:8050`) with hot reload.

**The user runs the dev server themselves, not the AI assistant.** A
background-started `app.run(debug=True)` process couldn't be reliably
stopped afterward — `netstat`/`Get-NetTCPConnection` kept reporting a PID
still listening on the port, but `Stop-Process`/`Get-Process`/Task Manager
all reported that PID didn't exist (likely a stale kernel-level socket
entry, possibly related to Werkzeug's debug-mode reloader spawning a
subprocess). Don't start `dashboard/app.py` in the background to
smoke-test it — write/edit the code, then ask the user to run it and view
it in their browser. If a quick non-visual sanity check is needed, prefer
importing the layout module directly (e.g. checking `pages.overview.layout`
constructs without raising) over binding to a port.

---

## Avoid These Mistakes

| Never do this | Do this instead |
|---|---|
| `app.run_server(...)` | `app.run(...)` |
| `from dash.dependencies import Input, Output` | `from dash import Input, Output, callback` |
| `import pandas as pd` in `dashboard/` code | `import polars as pl` |
| `px.choropleth` / `px.box` in `charts/*.py` | `plotly.graph_objects` (`go`) directly |
| Redefining `ZONE_ORDER`/`US_STATES` locally | Import from `src/data/clean.py` |
| A chart's own filter applied to itself (e.g. C3 hiding non-selected zones) | Dim via opacity; only highlight, never filter out, the chart's own selection |
| Putting the C2 raw/log toggle into `filter-state` | Keep it a plain `Input` local to the C2 callback |
| Passing raw per-row arrays to `go.Histogram`/`go.Box` | Precompute bins (`np.histogram`) / quantiles (Polars `.quantile()`) server-side — required for full-data (2.5M row) scale, see PLAN_UI.md |
| Reading `Notes_Dashboard.md` for instructions | It's the user's personal prompt log, explicitly marked not for AI context |
| Assuming `BE_notes.ipynb` can be edited | It's never modified by this work — see root `CLAUDE.md` |
