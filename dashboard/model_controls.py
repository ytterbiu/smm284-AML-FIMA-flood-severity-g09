"""dashboard/model_controls.py — the model-selection control row, shared by
the Model Performance and Lorenz/Lift pages only.

Distinct from shared_controls.py's filter-state: this doesn't filter claims
rows, it filters *which models* appear in these two pages' charts. Lives in
the app shell (app.py) so selection persists across navigation between the
two pages — see PLAN_UI.md "Model-selection toggle (Model performance +
Lorenz/lift only)".
"""
from __future__ import annotations

from dash import html, callback, Input, Output
import dash_bootstrap_components as dbc

from model_data import MODEL_COLORS

DEFAULT_MODELS: list[str] = list(MODEL_COLORS.keys())


def build_model_control_row() -> dbc.Row:
    return dbc.Row(
        dbc.Col(
            html.Div(
                [
                    html.Span("Models", className="me-2 fw-semibold"),
                    dbc.Checklist(
                        id="model-toggle-checklist",
                        options=[{"label": name, "value": name} for name in DEFAULT_MODELS],
                        value=list(DEFAULT_MODELS),
                        inline=True,
                        className="small",
                    ),
                ],
                className="d-flex align-items-center flex-wrap gap-1",
            ),
        ),
        className="g-2 mb-3",
    )


@callback(
    Output("model-selection-state", "data"),
    Input("model-toggle-checklist", "value"),
)
def update_model_selection_state(selected):
    return selected or []
