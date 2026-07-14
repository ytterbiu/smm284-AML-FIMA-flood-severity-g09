"""
Model section — Feature Importance / SHAP (path="/model/importance")

Placeholder layout only (Build Order step 1). Does not participate in the
shared filter-state/control row — see dashboard/AGENTS.md "Hiding the
shared control row on the Model section". Real content (shap_mean_abs_by_
feature.csv bar chart + a beeswarm plot from shap_values_oot_sample.npz)
lands in a later Build Order step.
"""
from __future__ import annotations

import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/model/importance", name="Feature Importance", order=3)

layout = dbc.Container(
    [
        html.H4("Feature importance", className="mt-3 mb-3"),
        html.P("Coming soon.", className="text-muted"),
    ],
    fluid=True,
)
