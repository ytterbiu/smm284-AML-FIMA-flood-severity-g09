"""
Model section — Feature Importance / SHAP (path="/model/importance")

Does not participate in the shared filter-state/control row — see
dashboard/AGENTS.md "Hiding the shared control row on the Model section".

GBM only throughout this page — see charts/shap_importance.py's module
docstring for why (BE_notes.ipynb computes SHAP/permutation importance
against best_model exclusively; SHAP TreeExplainer is tree-model-only
anyway). Three charts, all static (not filtered by the global filter-state):
- C8: SHAP bar chart (mean |SHAP|), from the teammate's export
- C9: SHAP beeswarm, reimplemented in Plotly from the same export
- C10: permutation importance, computed by us (not exported — see that
  module's docstring)

`layout` is a zero-arg function, not a static object — Dash's pages system
calls it fresh on every navigation to this page instead of once at module
import (all three build_*() calls are expensive; permutation importance
alone is ~7s on sample data, capped at 50K rows but still ~1-2 min at
full-data scale — see charts/permutation_importance.py's module docstring).
It returns instantly with "Loading…" placeholders rather than building the
charts inline — same fix as pages/model_lift.py, and for the same reason:
a callable layout that calls build_*() directly defers the cost from "app
startup" to "first page visit," but the cost is still paid synchronously
before the page reaches the browser, so dcc.Loading's spinner never gets a
chance to show. Instead, the three charts are built in callbacks
triggered by Input("url", "pathname") — the app shell's dcc.Location,
always mounted, fires this the moment the page's own dcc.Graph components
newly appear in the DOM (same mechanism Page 1 uses for filter-state, and
model_lift.py uses for model-selection-state). The underlying build
functions still cache their own results at module level, so only the
first visit is slow — reopening the page later is instant.
"""
from __future__ import annotations

import dash
from dash import dcc, html, callback, Input, Output
import dash_bootstrap_components as dbc

from charts.shap_importance import build_shap_bar_chart, build_shap_beeswarm
from charts.permutation_importance import build_permutation_importance_chart
from charts.common import empty_state_figure

dash.register_page(__name__, path="/model/importance", name="Feature Importance", order=4)


def layout(**_kwargs):
    return dbc.Container(
        [
            html.H4("Feature importance", className="mt-3 mb-3"),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Loading(
                            dcc.Graph(
                                id="shap-bar-chart",
                                figure=empty_state_figure("Loading…", height=450),
                                config={"displayModeBar": False},
                            ),
                        ),
                        width=5,
                    ),
                    dbc.Col(
                        dcc.Loading(
                            dcc.Graph(
                                id="shap-beeswarm-chart",
                                figure=empty_state_figure("Loading…", height=500),
                                config={"displayModeBar": False},
                            ),
                        ),
                        width=7,
                    ),
                ],
                className="mb-3",
            ),
            dbc.Row(
                dbc.Col(
                    dcc.Loading(
                        dcc.Graph(
                            id="permutation-importance-chart",
                            figure=empty_state_figure("Loading…", height=450),
                            config={"displayModeBar": False},
                        ),
                    ),
                ),
            ),
        ],
        fluid=True,
    )


@callback(
    Output("shap-bar-chart", "figure"),
    Input("url", "pathname"),
)
def load_shap_bar_chart(_pathname):
    return build_shap_bar_chart()


@callback(
    Output("shap-beeswarm-chart", "figure"),
    Input("url", "pathname"),
)
def load_shap_beeswarm_chart(_pathname):
    return build_shap_beeswarm()


@callback(
    Output("permutation-importance-chart", "figure"),
    Input("url", "pathname"),
)
def load_permutation_importance_chart(_pathname):
    return build_permutation_importance_chart()
