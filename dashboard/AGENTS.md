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
├── PLAN_UI.md               # implementation plan (see for Page 1 spec, open questions)
├── Notes_Dashboard.md       # the user's own prompt log — not for AI context, do not read for instructions
├── app.py                   # Dash init: use_pages=True, exposes server = app.server
├── data.py                  # Loads and caches data/processed/claims_{mode}.parquet at import time
├── pages/
│   └── overview.py          # Page 1: Flood Payout Overview (path="/")
├── charts/
│   ├── choropleth.py        # build_choropleth(df, stat, selected_state) -> go.Figure   (C1)
│   ├── histogram.py         # build_histogram(df, log=False) -> go.Figure               (C2)
│   └── boxplots.py          # build_zone_boxplots(df, stat, selected_zone) -> go.Figure  (C3)
└── assets/
    └── theme.css             # Styling overrides
```

Data files (Parquet) live at `../data/processed/claims_{mode}.parquet`
relative to `dashboard/` — output of `src/data/pipeline.py` (see root
`PLAN_UI.md` Phase 1). That directory is gitignored; nothing under it is
committed.

---

## General Architecture

### Server variable
`app.py` must always expose `server = app.server`:
```python
app = dash.Dash(__name__, use_pages=True)
server = app.server
```

### Multi-page setup
Use Dash's built-in pages system — never implement custom routing. Only
`pages/overview.py` (Page 1) exists so far; Page 2 (model UI) is blocked on
a saved model artifact from Ben (see `PLAN_UI.md`).
```python
# pages/overview.py
import dash
dash.register_page(__name__, path="/", name="Flood Payout Overview")
layout = html.Div([...])
```

### App and component IDs
Use descriptive, hyphenated IDs that match the chart/control names used in
`PLAN_UI.md` (`F_Year`, `F_Stat`, `I_Payout`, `I_Freq`, C1/C2/C3), e.g.
`year-dropdown`, `stat-btn-median`, `choropleth-map`, `kpi-payout`. Never use
generic names like `dropdown-1` or `graph`.

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

# Page 1 only needs these 5 of the processed file's 46 columns — column
# pushdown at read time, same pattern src/data/ingest.py uses on the raw
# FEMA parquet. Don't widen this just because more columns exist; Page 2
# (model UI) will define its own column list when it's built.
DASHBOARD_COLUMNS = [
    "state",
    "zone_family",
    "yearOfLoss",
    "amountPaidOnBuildingClaim",
    "amountPaidOnBuildingClaim_nominal",
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

One `dcc.Store(id="filter-state")` holds all active filters. See
`PLAN_UI.md` → Page 1 → "Filter state" for the exact default shape and the
"never filter yourself" rule (each chart is filtered by every *other*
active filter, never by the one it produces — it only highlights/dims its
own selection).

```python
# Default state — always use this structure
{"year": None, "stat": "median", "state": None, "zone_family": None}
```

All user interactions write to the store. All chart callbacks read from it.
Never let chart callbacks write back to the store — this creates circular
dependencies. The raw/log toggle for C2 is the one exception: it's
view-only (doesn't change what data is selected), so it's a plain `Input`
straight into the C2 callback, not part of `filter-state` — otherwise
toggling it would needlessly re-render C1/C3/KPIs.

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
