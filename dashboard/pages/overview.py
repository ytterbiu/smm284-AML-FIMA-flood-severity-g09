"""
Page 1 — Flood Payout Overview

Layout (top -> bottom), per dashboard/PLAN_UI.md:
  Title
  Control row : F_Year | F_Stat | I_Payout | I_Freq | Reset
  C1 | C2     : choropleth (state severity) | histogram (nominal vs real, raw/log toggle)
  C3          : row of 6 zone_family boxplots, shared y-axis

All filter state lives in dcc.Store(id="filter-state"). C2's raw/log scale
toggle is a separate dcc.Store(id="c2-scale-state") since it's view-only
(doesn't change what data is selected) — see PLAN_UI.md "Callback topology".
"""
from __future__ import annotations

import dash
from dash import dcc, html, callback, Input, Output, State, ctx, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import polars as pl

from data import get_df, apply_filters, get_stat_range, get_year_bounds, TARGET
from charts.choropleth import build_choropleth
from charts.histogram import build_histogram
from charts.boxplots import build_zone_boxplots

dash.register_page(__name__, path="/", name="Flood Payout Overview")

# ── Filter default ──────────────────────────────────────────────────────────

YEAR_MIN, YEAR_MAX = get_year_bounds()

DEFAULT_FILTER: dict = {
    "year_range": [YEAR_MIN, YEAR_MAX],
    "stat": "median",
    "state": None,
    "zone_family": None,
}

# Only label the two ends — marks at every 5 years overlapped and were
# unreadable across the ~49-year span. The always-visible tooltip already
# shows the exact currently-selected years while dragging.
YEAR_MARKS = {YEAR_MIN: str(YEAR_MIN), YEAR_MAX: str(YEAR_MAX)}


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
        dcc.Store(id="filter-state", data=DEFAULT_FILTER),
        dcc.Store(id="c2-scale-state", data="raw"),

        html.H4(
            "How much does flood insurance pay out in the USA?",
            className="mt-3 mb-3",
        ),

        # ── Control row ──────────────────────────────────────────────────
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.Span("Year", className="me-2 fw-semibold"),
                            html.Div(
                                dcc.RangeSlider(
                                    id="year-range-slider",
                                    min=YEAR_MIN,
                                    max=YEAR_MAX,
                                    step=1,
                                    value=[YEAR_MIN, YEAR_MAX],
                                    marks=YEAR_MARKS,
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    allowCross=False,
                                ),
                                style={"minWidth": "320px"},
                            ),
                        ],
                        className="d-flex align-items-center",
                    ),
                    width="auto",
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.Span("Stat", className="me-2 fw-semibold"),
                            html.Div(
                                [
                                    html.Button("Median", id="stat-btn-median", className="btn btn-primary btn-sm", n_clicks=0),
                                    html.Button("Mean", id="stat-btn-mean", className="btn btn-outline-primary btn-sm", n_clicks=0),
                                ],
                                className="btn-group btn-group-sm",
                            ),
                        ],
                        className="d-flex align-items-center",
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.P(id="kpi-payout-label", className="kpi-label mb-1", children="Real Payout (Median)"),
                            html.P(id="kpi-payout", className="kpi-value mb-0", children="—"),
                        ]),
                        className="kpi-card",
                    ),
                    width=2,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody([
                            html.P("Claims (records)", className="kpi-label mb-1"),
                            html.P(id="kpi-freq", className="kpi-value mb-0", children="—"),
                        ]),
                        className="kpi-card",
                    ),
                    width=2,
                ),
                dbc.Col(
                    html.Div(id="active-filters-display", className="d-flex align-items-center flex-wrap gap-1"),
                    width="auto",
                    className="ms-auto align-self-center",
                ),
                dbc.Col(
                    html.Button(
                        "✕ Reset",
                        id="btn-reset",
                        className="btn btn-sm btn-outline-danger",
                        n_clicks=0,
                    ),
                    width="auto",
                    className="align-self-center",
                ),
            ],
            align="center",
            className="g-2 mb-3",
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


# ── Callbacks ────────────────────────────────────────────────────────────────

@callback(
    Output("filter-state", "data", allow_duplicate=True),
    Input("year-range-slider", "value"),
    Input("stat-btn-median", "n_clicks"),
    Input("stat-btn-mean", "n_clicks"),
    Input("choropleth-map", "clickData"),
    Input("zone-boxplots", "clickData"),
    Input("btn-reset", "n_clicks"),
    State("filter-state", "data"),
    prevent_initial_call=True,
)
def update_filter_state(
    year_range_value, _med_clicks, _mean_clicks, map_click, zone_click, _reset_clicks, current
):
    triggered = ctx.triggered_id
    state = dict(current)

    if triggered == "btn-reset":
        return dict(DEFAULT_FILTER)

    if triggered == "year-range-slider":
        state["year_range"] = year_range_value
    elif triggered == "stat-btn-median":
        state["stat"] = "median"
    elif triggered == "stat-btn-mean":
        state["stat"] = "mean"
    elif triggered == "choropleth-map":
        if map_click:
            clicked = map_click["points"][0]["location"]
            state["state"] = None if state.get("state") == clicked else clicked
    elif triggered == "zone-boxplots":
        if zone_click:
            clicked = zone_click["points"][0]["x"]
            state["zone_family"] = None if state.get("zone_family") == clicked else clicked

    return state


@callback(
    Output("year-range-slider", "value"),
    Input("filter-state", "data"),
)
def sync_year_range_slider(filter_state):
    # The slider's own `value` only reflects user drags by default — nothing
    # else writes it back, so resetting year_range via the chip or Reset
    # button (which both update filter-state directly) would otherwise leave
    # the slider's handles visually stuck at their last dragged position.
    # Same pattern as update_stat_buttons below: driven by filter-state even
    # though this same component is also an Input to it; safe from feedback
    # loops since Dash won't re-fire on an unchanged value.
    return filter_state["year_range"]


@callback(
    Output("stat-btn-median", "className"),
    Output("stat-btn-mean", "className"),
    Input("filter-state", "data"),
)
def update_stat_buttons(filter_state):
    stat = filter_state["stat"]
    return (
        "btn btn-primary btn-sm" if stat == "median" else "btn btn-outline-primary btn-sm",
        "btn btn-primary btn-sm" if stat == "mean" else "btn btn-outline-primary btn-sm",
    )


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


@callback(
    Output("kpi-payout-label", "children"),
    Output("kpi-payout", "children"),
    Output("kpi-freq", "children"),
    Input("filter-state", "data"),
)
def update_kpis(filter_state):
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
        return label, "—", "0"

    agg_expr = pl.col(TARGET).median() if stat == "median" else pl.col(TARGET).mean()
    payout = df.select(agg_expr).item()
    return label, f"${payout:,.0f}", f"{df.height:,}"


# Labels for the active-filter chips that are simple None-means-unset
# fields. year_range is handled separately below since it's never None —
# its "unset" state is the full [YEAR_MIN, YEAR_MAX] range instead.
_CHIP_LABELS = {"state": "State", "zone_family": "Zone"}


def _year_range_label(year_range: list[int]) -> str | None:
    lo, hi = year_range
    if [lo, hi] == [YEAR_MIN, YEAR_MAX]:
        return None
    return f"Year: {lo}" if lo == hi else f"Year: {lo}–{hi}"


@callback(
    Output("active-filters-display", "children"),
    Input("filter-state", "data"),
)
def update_active_filters_display(filter_state):
    chips = [html.Span("Filters:", className="me-1 small text-muted")]

    year_label = _year_range_label(filter_state["year_range"])
    if year_label is not None:
        chips.append(
            html.Span(
                f"{year_label} ×",
                id={"type": "filter-chip", "key": "year_range"},
                n_clicks=0,
                className="badge bg-primary me-1",
                title="Click to remove this filter",
                style={"cursor": "pointer"},
            )
        )

    for key, label in _CHIP_LABELS.items():
        if filter_state.get(key) is not None:
            chips.append(
                html.Span(
                    f"{label}: {filter_state[key]} ×",
                    id={"type": "filter-chip", "key": key},
                    n_clicks=0,
                    className="badge bg-primary me-1",
                    title="Click to remove this filter",
                    style={"cursor": "pointer"},
                )
            )

    if len(chips) == 1:  # only the "Filters:" label, nothing active
        return [html.Span("No filters active", className="text-muted small")]
    return chips


@callback(
    Output("filter-state", "data", allow_duplicate=True),
    Input({"type": "filter-chip", "key": ALL}, "n_clicks"),
    State("filter-state", "data"),
    prevent_initial_call=True,
)
def remove_filter_via_chip(_n_clicks_list, current):
    # Guard against this firing just from a chip being newly added to the
    # DOM (n_clicks starts at 0, not from an actual click) rather than a
    # real click (n_clicks > 0).
    if not ctx.triggered or not ctx.triggered[0]["value"]:
        return dash.no_update
    key = ctx.triggered_id["key"]
    state = dict(current)
    state[key] = [YEAR_MIN, YEAR_MAX] if key == "year_range" else None
    return state
