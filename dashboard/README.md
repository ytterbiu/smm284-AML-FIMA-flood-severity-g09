# Flood Payout Dashboard — Setup & Run

A Plotly Dash app visualising US flood claim severity (FEMA NFIP data).
Page 1 — "How much does flood insurance pay out in the USA?" — is the only
page built so far: a choropleth by state, a nominal-vs-real severity
histogram, and boxplots by flood zone, with year/state/zone filters. Page 2
(prediction model UI) doesn't exist yet.

Currently running on a **~22k-row sample** of the full ~2.7M-claim dataset —
functionality and UX feedback is the goal here, not the exact numbers.

Works on Windows, macOS, and Linux — the commands below are given for both
where they differ.

## Prerequisites

- Python **3.12** (the project's own `.venv` uses 3.12.13; other 3.x
  versions will probably work but aren't tested)
- `git`

## 1. Clone the repo and check out this branch

```bash
git clone https://github.com/ytterbiu/smm284-AML-FIMA-flood-severity-g09.git
cd smm284-AML-FIMA-flood-severity-g09
git checkout dev_ui
```

## 2. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Make sure the `python`/`pip` you use from here on resolve *inside* this
`.venv` (check with `where python` on Windows / `which python3` on macOS) —
a conda install or other system Python on your PATH can otherwise silently
shadow it and produce confusing `ModuleNotFoundError`s.

## 3. Generate the processed sample dataset (one-time)

The dashboard reads `data/processed/claims_sample.parquet`, which is
**gitignored** — every fresh clone needs to generate it once via the data
pipeline. This step needs a few packages the dashboard itself doesn't:

```bash
pip install pandas pyarrow requests
python src/data/pipeline.py --mode sample
```

You should see output ending with something like:
```
[sample] saved -> data/processed/claims_sample.parquet
```

(This also downloads a small CPI series from FRED on first run — needs
network access, but it's a small file, cached afterward.)

## 4. Install the dashboard's own dependencies

```bash
pip install -r dashboard/requirements.txt
```

(If you've already installed the full project environment from the repo
root's `requirements-dev.txt` — e.g. because you're also exploring
`BE_notes.ipynb` — you can skip this; those packages are included there
too.)

## 5. Run it

```bash
python dashboard/app.py
```
(macOS: `python3 dashboard/app.py` if `python` isn't aliased)

Open **http://localhost:8050** in your browser. Dash's dev server
hot-reloads on file changes, so it's fine to leave it running.

## What to try / give feedback on

- Choropleth (C1): year dropdown, median/mean toggle, click a state to
  select it (click again to deselect)
- Histogram (C2): raw vs. log-scale toggle — shows how skewed severity is
- Boxplots (C3): click a flood-zone box to filter by it (same
  click-again-to-deselect behaviour)
- The active-filter chips (next to Reset) show what's currently applied,
  and each is individually clickable to clear just that filter
- General layout, clarity, anything confusing or broken

## Known limitations

- Sample data only — some states/zones have very few claims, so their
  numbers will look noisier than the full dataset would (e.g. small US
  territories are excluded entirely, and a couple of states/zones have
  under 50 claims in the sample)
- Page 2 (model prediction UI) isn't built — blocked on a saved model file
- No production deployment yet; this is local-dev-server only for now

## Troubleshooting

- **Port 8050 already in use**: stop whatever else is using it, or edit the
  last line of `dashboard/app.py` to `app.run(debug=True, port=8051)` and
  use that port instead.
- **`ModuleNotFoundError`**: almost always means `pip install` ran against
  a different Python than the one now running `dashboard/app.py` — confirm
  your virtual environment is activated in the same terminal for both.
- **`FileNotFoundError` for `claims_sample.parquet`**: step 3 above hasn't
  been run yet.
