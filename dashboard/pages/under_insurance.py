"""
Page 2 — Under-Insurance

Layout (top -> bottom), per dashboard/PLAN_UI.md:
  (shared control row + KPI row, in the app shell — see app.py)
  C4 | C5     : coverage-ratio histogram (colored by status) | 100%-stacked
                bar of status share by flood zone

Ports BE_notes.ipynb section 14. Shares the global filter-state and control
row with Page 1 (see dashboard/AGENTS.md "App shell vs. page content") —
this module only owns Page-2-specific layout, chart callbacks, and
build_kpi_cards().
"""
from __future__ import annotations

import dash
from dash import dcc, html, callback, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from data import get_df, apply_filters
from charts.status_bands import compute_ratio_status
from charts.coverage_histogram import build_coverage_histogram
from charts.under_insurance_by_zone import build_zone_status_bars

dash.register_page(__name__, path="/under-insurance", name="Under-Insurance", order=1)


def _placeholder_figure(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center"),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[
            dict(
                text="placeholder — chart not wired yet",
                showarrow=False,
                font=dict(size=13, color="#94a3b8"),
            )
        ],
        margin=dict(t=40, l=10, r=10, b=10),
    )
    return fig


# ── Layout ───────────────────────────────────────────────────────────────────

layout = dbc.Container(
    [
        html.H4(
            "How under-insured are US flood properties?",
            className="mt-3 mb-3",
        ),

        # ── C4 | C5 ──────────────────────────────────────────────────────
        dbc.Row(
            [
                dbc.Col(
                    dcc.Loading(
                        dcc.Graph(
                            id="coverage-histogram",
                            figure=_placeholder_figure("C4 — Coverage ratio"),
                            config={"displayModeBar": False},
                        ),
                    ),
                    width=6,
                ),
                dbc.Col(
                    dcc.Loading(
                        dcc.Graph(
                            id="zone-status-bars",
                            figure=_placeholder_figure("C5 — Status share by zone"),
                            config={"displayModeBar": False},
                        ),
                    ),
                    width=6,
                ),
            ],
            className="mb-3",
        ),
    ],
    fluid=True,
)


# ── KPI cards (dispatched to by app.py's shared kpi-row callback) ───────────

def build_kpi_cards(filter_state: dict) -> list:
    df = get_df()
    df = apply_filters(
        df,
        year_range=filter_state["year_range"],
        state=filter_state.get("state"),
        zone_family=filter_state.get("zone_family"),
    )
    stat = filter_state["stat"]
    valid = compute_ratio_status(df)

    if valid.height == 0:
        ratio_val, n_assessed, pct_under, pct_severe = "—", "0", "—", "—"
    else:
        ratio = valid["coverage_ratio"].median() if stat == "median" else valid["coverage_ratio"].mean()
        ratio_val = f"{ratio:.0%}"
        n_assessed = f"{valid.height:,}"
        n_severe = valid.filter(valid["status"] == "Severely under-insured").height
        n_under_total = valid.filter(valid["status"] != "Adequately insured").height
        pct_under = f"{100 * n_under_total / valid.height:.0f}%"
        pct_severe = f"{100 * n_severe / valid.height:.0f}%"

    def _card(label: str, value: str) -> dbc.Card:
        return dbc.Card(
            dbc.CardBody([
                html.P(label, className="kpi-label mb-1"),
                html.P(value, className="kpi-value mb-0"),
            ]),
            className="kpi-card",
        )

    return [
        _card(f"Coverage Ratio ({stat.title()})", ratio_val),
        _card("Properties Assessed", n_assessed),
        _card("Under-insured (<80%)", pct_under),
        _card("Severely Under-insured (<50%)", pct_severe),
    ]


# ── Chart callbacks ──────────────────────────────────────────────────────────

@callback(
    Output("filter-state", "data", allow_duplicate=True),
    Input("zone-status-bars", "clickData"),
    State("filter-state", "data"),
    prevent_initial_call=True,
)
def update_filter_state_from_page2_charts(zone_click, current):
    # Page-2-specific chart-click handling — see the comment on
    # shared_controls.update_filter_state for why this can't live there or
    # be combined with pages/overview.py's equivalent callback.
    if not zone_click:
        return dash.no_update
    clicked = zone_click["points"][0]["x"]
    state = dict(current)
    zones = list(state.get("zone_family") or [])
    if clicked in zones:
        zones.remove(clicked)
    else:
        zones.append(clicked)
    state["zone_family"] = zones
    return state


@callback(
    Output("coverage-histogram", "figure"),
    Input("filter-state", "data"),
)
def update_coverage_histogram(filter_state):
    df = get_df()
    df = apply_filters(
        df,
        year_range=filter_state["year_range"],
        state=filter_state.get("state"),
        zone_family=filter_state.get("zone_family"),
    )
    return build_coverage_histogram(df)


@callback(
    Output("zone-status-bars", "figure"),
    Input("filter-state", "data"),
)
def update_zone_status_bars(filter_state):
    df = get_df()
    df = apply_filters(df, year_range=filter_state["year_range"], state=filter_state.get("state"))
    return build_zone_status_bars(df, selected_zones=filter_state.get("zone_family"))
