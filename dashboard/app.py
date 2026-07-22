"""dashboard/app.py — Dash app init + app shell.

Run locally: ./.venv/Scripts/python.exe dashboard/app.py
Starts the dev server at http://localhost:8050 with hot reload.

The app shell (filter-state Store, nav, shared control row, kpi-row) lives
here, outside dash.page_container, so it persists across page navigation —
see dashboard/AGENTS.md "App shell vs. page content".
"""
from __future__ import annotations

import dash
from dash import dcc, html, callback, Input, Output
import dash_bootstrap_components as dbc

from shared_controls import DEFAULT_FILTER, build_control_row
from model_controls import DEFAULT_MODELS, build_model_control_row

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,  # each page's chart IDs only exist while that page is mounted
)
server = app.server  # required for gunicorn

# Imported after the Dash app exists so use_pages' own page discovery has
# already registered them; needed here (not just via page_registry) because
# we call each page's own build_kpi_cards(), not just its layout.
from pages import overview, under_insurance  # noqa: E402

_NAV_LINKS = dbc.Nav(
    [
        dbc.NavLink(page["name"], href=page["path"], active="exact")
        for page in dash.page_registry.values()
    ],
    pills=True,
    className="mb-3",
)

app.layout = dbc.Container(
    [
        dcc.Location(id="url"),
        dcc.Store(id="filter-state", data=DEFAULT_FILTER),
        dcc.Store(id="c2-scale-state", data="raw"),
        dcc.Store(id="model-selection-state", data=list(DEFAULT_MODELS)),
        _NAV_LINKS,
        html.Div(id="control-row-wrapper", children=[build_control_row()]),
        html.Div(id="model-control-row-wrapper", children=[build_model_control_row()]),
        dash.page_container,
    ],
    fluid=True,
)


def _is_model_section(pathname: str | None) -> bool:
    return bool(pathname) and pathname.startswith("/model")


_MODEL_TOGGLE_PATHS = {"/model/performance", "/model/lift"}


@callback(
    Output("control-row-wrapper", "style"),
    Input("url", "pathname"),
)
def toggle_control_row(pathname):
    # The Model section (/model/*) doesn't filter the claims dataset at all
    # — it shows properties of a fitted model, not a filterable subset — so
    # the shared control row (and, via update_kpi_row below, the KPI cards
    # nested inside it) is hidden entirely rather than shown with stale/
    # irrelevant content. See AGENTS.md "Hiding the shared control row on
    # the Model section".
    return {"display": "none"} if _is_model_section(pathname) else {}


@callback(
    Output("model-control-row-wrapper", "style"),
    Input("url", "pathname"),
)
def toggle_model_control_row(pathname):
    # Shown only on the two pages that compare models against each other
    # (Model Performance, Lorenz/Lift) — not Feature Importance (GBM-only
    # by design) or Predict (already shows all 4 non-degenerate models
    # side by side). See PLAN_UI.md "Model-selection toggle".
    return {} if pathname in _MODEL_TOGGLE_PATHS else {"display": "none"}


@callback(
    Output("kpi-row", "children"),
    Input("url", "pathname"),
    Input("filter-state", "data"),
)
def update_kpi_row(pathname, filter_state):
    # Each page module exposes its own build_kpi_cards(filter_state) -> list
    # of dbc.Card components — content AND count vary per page (2 on "/",
    # 4 on "/under-insurance"). Model section pages have none (row is
    # hidden entirely by toggle_control_row above).
    if _is_model_section(pathname):
        return []
    if pathname == "/under-insurance":
        return under_insurance.build_kpi_cards(filter_state)
    return overview.build_kpi_cards(filter_state)


if __name__ == "__main__":
    app.run(debug=True)
