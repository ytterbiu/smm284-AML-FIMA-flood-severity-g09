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
"""
from __future__ import annotations

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

from charts.shap_importance import build_shap_bar_chart, build_shap_beeswarm
from charts.permutation_importance import build_permutation_importance_chart

dash.register_page(__name__, path="/model/importance", name="Feature Importance", order=4)

layout = dbc.Container(
    [
        html.H4("Feature importance", className="mt-3 mb-3"),
        dbc.Row(
            [
                dbc.Col(
                    dcc.Loading(
                        dcc.Graph(figure=build_shap_bar_chart(), config={"displayModeBar": False}),
                    ),
                    width=5,
                ),
                dbc.Col(
                    dcc.Loading(
                        dcc.Graph(figure=build_shap_beeswarm(), config={"displayModeBar": False}),
                    ),
                    width=7,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row(
            dbc.Col(
                dcc.Loading(
                    dcc.Graph(figure=build_permutation_importance_chart(), config={"displayModeBar": False}),
                ),
            ),
        ),
    ],
    fluid=True,
)
