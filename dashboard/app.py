"""dashboard/app.py — Dash app init.

Run locally: ./.venv/Scripts/python.exe dashboard/app.py
Starts the dev server at http://localhost:8050 with hot reload.
"""
from __future__ import annotations

import dash
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
server = app.server  # required for gunicorn

app.layout = dbc.Container(dash.page_container, fluid=True)

if __name__ == "__main__":
    app.run(debug=True)
