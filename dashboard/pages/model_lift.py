"""
Model section — Lorenz Curve / Double Lift (path="/model/lift")

Does not participate in the shared filter-state/control row — see
dashboard/AGENTS.md "Hiding the shared control row on the Model section".
Does participate in the model-selection toggle (model-selection-state) —
see PLAN_UI.md "Model-selection toggle" — same store as
pages/model_performance.py, so selection persists across navigation
between the two pages.

Layout: two charts side by side (no page-level title — each chart already
titles itself). Left: Lorenz curve (C11) + a Gini table underneath (values
shown there instead of in the chart legend). Right: double lift chart
(C12), comparing exactly 2 models at a time (dropdowns, options restricted
to whatever's toggled on in model-selection-state).
"""
from __future__ import annotations

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc

from charts.lorenz_curve import build_lorenz_curve, compute_ginis
from charts.double_lift import build_double_lift_chart
from model_controls import DEFAULT_MODELS
from model_data import MODEL_COLORS

dash.register_page(__name__, path="/model/lift", name="Lorenz & Lift", order=3)

# Preferred default pair for the double lift chart, per user request — falls
# back to the first two toggled-on models if either isn't currently selected.
DEFAULT_PAIR = ("GBM (gamma loss)", "Baseline (zone mean)")


def _build_gini_table(selected_models: list[str] | None) -> dbc.Table | html.P:
    ginis = compute_ginis(selected_models)
    if not ginis:
        return html.P("Select at least one model to compare.", className="text-muted small mt-2")

    rows = [
        html.Tr(
            [
                html.Td(
                    html.Span(
                        [
                            html.Span(
                                style={
                                    "display": "inline-block",
                                    "width": "10px",
                                    "height": "10px",
                                    "borderRadius": "50%",
                                    "backgroundColor": MODEL_COLORS[model],
                                    "marginRight": "6px",
                                }
                            ),
                            model,
                        ]
                    )
                ),
                html.Td(f"{gini:.3f}"),
            ]
        )
        for model, gini in ginis
    ]
    return dbc.Table(
        [html.Thead(html.Tr([html.Th("Model"), html.Th("Gini index")])), html.Tbody(rows)],
        bordered=False,
        hover=True,
        size="sm",
        className="mt-2",
    )


layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        # Invisible spacer, same markup as the dropdown row on
                        # the right, so the two charts' top edges align — the
                        # dropdowns above the double lift chart push it down
                        # by their own height, which this mirrors exactly
                        # rather than a hand-tuned pixel offset.
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.Span("Model A", className="me-2 small text-muted"),
                                            dcc.Dropdown(clearable=False),
                                        ],
                                        className="d-flex align-items-center",
                                    ),
                                    width="auto",
                                ),
                            ],
                            className="g-2 mb-2",
                            style={"visibility": "hidden"},
                        ),
                        dcc.Loading(
                            dcc.Graph(
                                id="lorenz-curve",
                                figure=build_lorenz_curve(DEFAULT_MODELS),
                                config={"displayModeBar": False},
                            ),
                        ),
                        html.Div(id="gini-table", children=_build_gini_table(DEFAULT_MODELS)),
                    ],
                    width=6,
                ),
                dbc.Col(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.Span("Model A", className="me-2 small text-muted"),
                                            dcc.Dropdown(id="lift-model-a", clearable=False),
                                        ],
                                        className="d-flex align-items-center",
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.Span("Model B", className="me-2 small text-muted"),
                                            dcc.Dropdown(id="lift-model-b", clearable=False),
                                        ],
                                        className="d-flex align-items-center",
                                    ),
                                    width="auto",
                                ),
                            ],
                            className="g-2 mb-2",
                        ),
                        dcc.Loading(
                            dcc.Graph(
                                id="double-lift-chart",
                                figure=build_double_lift_chart(None, None),
                                config={"displayModeBar": False},
                            ),
                        ),
                    ],
                    width=6,
                ),
            ],
            className="mt-3",
        ),
    ],
    fluid=True,
)


@callback(
    Output("lorenz-curve", "figure"),
    Input("model-selection-state", "data"),
)
def update_lorenz_curve(selected_models):
    return build_lorenz_curve(selected_models)


@callback(
    Output("gini-table", "children"),
    Input("model-selection-state", "data"),
)
def update_gini_table(selected_models):
    return _build_gini_table(selected_models)


@callback(
    Output("lift-model-a", "options"),
    Output("lift-model-a", "value"),
    Output("lift-model-b", "options"),
    Output("lift-model-b", "value"),
    Input("model-selection-state", "data"),
    State("lift-model-a", "value"),
    State("lift-model-b", "value"),
)
def sync_lift_dropdowns(selected_models, current_a, current_b):
    # Fixed MODEL_COLORS order for a stable dropdown ordering as the toggle changes.
    selected = [m for m in MODEL_COLORS if m in (selected_models or [])]
    options = [{"label": m, "value": m} for m in selected]

    if len(selected) < 2:
        return options, None, options, None

    a = current_a if current_a in selected else None
    b = current_b if current_b in selected else None
    if a is None or b is None or a == b:
        if DEFAULT_PAIR[0] in selected and DEFAULT_PAIR[1] in selected:
            a, b = DEFAULT_PAIR
        else:
            a, b = selected[0], selected[1]
    return options, a, options, b


@callback(
    Output("lift-model-a", "disabled"),
    Output("lift-model-b", "disabled"),
    Input("model-selection-state", "data"),
)
def toggle_lift_dropdowns_disabled(selected_models):
    too_few = len(selected_models or []) < 2
    return too_few, too_few


@callback(
    Output("double-lift-chart", "figure"),
    Input("lift-model-a", "value"),
    Input("lift-model-b", "value"),
)
def update_double_lift_chart(model_a, model_b):
    return build_double_lift_chart(model_a, model_b)
