"""
Model section — Lorenz Curve / Double Lift (path="/model/lift")

Placeholder layout only (Build Order step 1). Does not participate in the
shared filter-state/control row — see dashboard/AGENTS.md "Hiding the
shared control row on the Model section". Real content (Lorenz curve +
double lift chart, computed ourselves against our own OOT-filtered data
using the exported model artifacts) lands in a later Build Order step.
"""
from __future__ import annotations

import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/model/lift", name="Lorenz & Lift", order=4)

layout = dbc.Container(
    [
        html.H4("Lorenz curve & double lift", className="mt-3 mb-3"),
        html.P("Coming soon.", className="text-muted"),
    ],
    fluid=True,
)
