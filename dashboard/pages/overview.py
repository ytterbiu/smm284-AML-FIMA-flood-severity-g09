"""
Page 1 — Flood Payout Overview

Layout (top -> bottom), per dashboard/PLAN_UI.md:
  (shared control row + KPI row, in the app shell — see app.py)
  C1 | C2     : choropleth (state severity) | histogram (nominal vs real, raw/log toggle)
  C3          : row of 6 zone_family boxplots, shared y-axis

The control row, filter-state Store, and KPI-row dispatch all live in the
app shell (app.py / shared_controls.py), not here — see dashboard/AGENTS.md
"App shell vs. page content". This module only owns Page-1-specific layout,
chart callbacks, and build_kpi_cards().
"""
from __future__ import annotations

import dash
from dash import dcc, html, callback, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import polars as pl

from data import get_df, apply_filters, get_stat_range, TARGET
from charts.choropleth import build_choropleth
from charts.histogram import build_histogram
from charts.boxplots import build_zone_boxplots

dash.register_page(__name__, path="/", name="Flood Payout Overview", order=0)


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
            "How much does flood insurance pay out in the USA?",
            className="mt-3 mb-3",
        ),

        # ── C1 | C2 ──────────────────────────────────────────────────────
        dbc.Row(
            [
                dbc.Col(
                    dcc.Loading(
                        dcc.Graph(
                            id="choropleth-map",
                            figure=_placeholder_figure("C1 — Median/mean severity by state"),
                            config={"displayModeBar": False},
                        ),
                    ),
                    width=7,
                ),
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.Span("Scale:", className="me-2 small text-muted"),
                                html.Div(
                                    [
                                        html.Button("Raw", id="c2-scale-raw", className="btn btn-outline-secondary btn-sm", n_clicks=0),
                                        html.Button("Log", id="c2-scale-log", className="btn btn-outline-secondary btn-sm", n_clicks=0),
                                    ],
                                    className="btn-group btn-group-sm",
                                ),
                            ],
                            className="d-flex align-items-center justify-content-end mb-1",
                        ),
                        dcc.Loading(
                            dcc.Graph(
                                id="severity-histogram",
                                figure=_placeholder_figure("C2 — Nominal vs. real severity"),
                                config={"displayModeBar": False},
                            ),
                        ),
                    ],
                    width=5,
                ),
            ],
            className="mb-3",
        ),

        # ── C3 ───────────────────────────────────────────────────────────
        dbc.Row(
            dbc.Col(
                dcc.Loading(
                    dcc.Graph(
                        id="zone-boxplots",
                        figure=_placeholder_figure("C3 — Payout by flood zone"),
                        config={"displayModeBar": False},
                    ),
                ),
            ),
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
    label = f"Real Payout ({stat.title()})"

    if df.height == 0:
        payout, freq = "—", "0"
    else:
        agg_expr = pl.col(TARGET).median() if stat == "median" else pl.col(TARGET).mean()
        payout = f"${df.select(agg_expr).item():,.0f}"
        freq = f"{df.height:,}"

    return [
        dbc.Card(
            dbc.CardBody([
                html.P(label, className="kpi-label mb-1"),
                html.P(payout, className="kpi-value mb-0"),
            ]),
            className="kpi-card",
        ),
        dbc.Card(
            dbc.CardBody([
                html.P("Claims (records)", className="kpi-label mb-1"),
                html.P(freq, className="kpi-value mb-0"),
            ]),
            className="kpi-card",
        ),
    ]


# ── Chart callbacks ──────────────────────────────────────────────────────────

@callback(
    Output("choropleth-map", "figure"),
    Input("filter-state", "data"),
)
def update_choropleth(filter_state):
    df = get_df()
    df = apply_filters(df, year_range=filter_state["year_range"], zone_family=filter_state.get("zone_family"))
    zmin, zmax = get_stat_range(filter_state["stat"])
    return build_choropleth(
        df,
        stat=filter_state["stat"],
        selected_state=filter_state.get("state"),
        zmin=zmin,
        zmax=zmax,
    )


@callback(
    Output("filter-state", "data", allow_duplicate=True),
    Input("choropleth-map", "clickData"),
    Input("zone-boxplots", "clickData"),
    State("filter-state", "data"),
    prevent_initial_call=True,
)
def update_filter_state_from_page1_charts(map_click, zone_click, current):
    # Page-1-specific chart-click handling — kept out of shared_controls.py
    # since these component IDs only exist while this page is mounted (see
    # the comment on shared_controls.update_filter_state for why mixing
    # cross-page Inputs in one callback breaks at runtime).
    triggered = ctx.triggered_id
    state = dict(current)

    if triggered == "choropleth-map":
        if map_click:
            clicked = map_click["points"][0]["location"]
            state["state"] = None if state.get("state") == clicked else clicked
    elif triggered == "zone-boxplots":
        if zone_click:
            clicked = zone_click["points"][0]["x"]
            state["zone_family"] = None if state.get("zone_family") == clicked else clicked

    return state


@callback(
    Output("c2-scale-state", "data"),
    Input("c2-scale-raw", "n_clicks"),
    Input("c2-scale-log", "n_clicks"),
    prevent_initial_call=True,
)
def update_c2_scale(_raw_clicks, _log_clicks):
    return "log" if ctx.triggered_id == "c2-scale-log" else "raw"


@callback(
    Output("c2-scale-raw", "className"),
    Output("c2-scale-log", "className"),
    Input("c2-scale-state", "data"),
)
def update_c2_scale_buttons(scale):
    active, inactive = "btn btn-secondary btn-sm", "btn btn-outline-secondary btn-sm"
    return (
        active if scale == "raw" else inactive,
        active if scale == "log" else inactive,
    )


@callback(
    Output("severity-histogram", "figure"),
    Input("filter-state", "data"),
    Input("c2-scale-state", "data"),
)
def update_histogram(filter_state, scale):
    df = get_df()
    df = apply_filters(
        df,
        year_range=filter_state["year_range"],
        state=filter_state.get("state"),
        zone_family=filter_state.get("zone_family"),
    )
    return build_histogram(df, log=(scale == "log"))


@callback(
    Output("zone-boxplots", "figure"),
    Input("filter-state", "data"),
)
def update_boxplots(filter_state):
    df = get_df()
    df = apply_filters(df, year_range=filter_state["year_range"], state=filter_state.get("state"))
    return build_zone_boxplots(df, stat=filter_state["stat"], selected_zone=filter_state.get("zone_family"))
