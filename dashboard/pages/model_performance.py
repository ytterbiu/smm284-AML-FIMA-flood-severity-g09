"""
Model section — Performance (path="/model/performance")

Does not participate in the shared filter-state/control row — see
dashboard/AGENTS.md "Hiding the shared control row on the Model section".

C6 (cross-model OOT scoreboard) is the first real chart in the Model
section. The tuning-diagnostics chart (cv_results_*/tuned_params.json)
lands in a later Build Order step, on this same page.
"""
from __future__ import annotations

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

from charts.oot_scoreboard import build_oot_scoreboard

dash.register_page(__name__, path="/model/performance", name="Model Performance", order=2)

layout = dbc.Container(
    [
        html.H4("Model performance", className="mt-3 mb-3"),
        dcc.Loading(
            dcc.Graph(
                id="oot-scoreboard",
                figure=build_oot_scoreboard(),
                config={"displayModeBar": False},
            ),
        ),
    ],
    fluid=True,
)
