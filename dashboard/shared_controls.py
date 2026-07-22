"""dashboard/shared_controls.py — the app-shell control row + its callbacks.

Lives in app.py's top-level layout (outside dash.page_container) so it's
mounted once and persists across page navigation — see dashboard/AGENTS.md
"App shell vs. page content" and PLAN_UI.md "Architecture change for
multi-page". Registered exactly once regardless of how many pages exist.

The KPI cards are NOT built here — they're the one part of the control row
that varies per page (content and count). build_control_row() only reserves
an empty html.Div(id="kpi-row") in the right spot; app.py's kpi-row
dispatch callback fills it based on the current page.
"""
from __future__ import annotations

import dash
from dash import dcc, html, callback, Input, Output, State, ctx, ALL
import dash_bootstrap_components as dbc

from data import get_year_bounds

YEAR_MIN, YEAR_MAX = get_year_bounds()

DEFAULT_FILTER: dict = {
    "year_range": [YEAR_MIN, YEAR_MAX],
    "stat": "median",
    "state": None,
    "zone_family": [],  # multi-select: plain click toggles a zone in/out of this list
}

# Only label the two ends — marks at every 5 years overlapped and were
# unreadable across the ~49-year span. The always-visible tooltip already
# shows the exact currently-selected years while dragging.
YEAR_MARKS = {YEAR_MIN: str(YEAR_MIN), YEAR_MAX: str(YEAR_MAX)}


def build_control_row() -> dbc.Row:
    return dbc.Row(
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
                html.Div(id="kpi-row", className="d-flex align-items-stretch gap-2"),
                width="auto",
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
    )


# ── Callbacks ────────────────────────────────────────────────────────────────

@callback(
    Output("filter-state", "data", allow_duplicate=True),
    Input("year-range-slider", "value"),
    Input("stat-btn-median", "n_clicks"),
    Input("stat-btn-mean", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    State("filter-state", "data"),
    prevent_initial_call=True,
)
def update_filter_state(year_range_value, _med_clicks, _mean_clicks, _reset_clicks, current):
    # Deliberately does NOT include chart clickData (choropleth-map,
    # zone-boxplots, zone-status-bars) as Inputs here, even though they also
    # write to filter-state. Those components only exist on their own page,
    # not in the always-mounted app shell — bundling an Input from a
    # not-currently-rendered page into this callback made Dash try to
    # resolve its value on every fire and throw "nonexistent object" errors
    # at runtime (suppress_callback_exceptions only skips *startup*
    # validation, it doesn't fix this). Each page handles its own chart
    # clicks in its own callback instead — see pages/overview.py and
    # pages/under_insurance.py.
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


# Labels for the active-filter chips that are simple None-means-unset
# fields. year_range is handled separately below since it's never None —
# its "unset" state is the full [YEAR_MIN, YEAR_MAX] range instead.
# zone_family is handled separately too — it's a list (multi-select), so it
# gets one chip per selected zone rather than a single "field: value" chip.
_CHIP_LABELS = {"state": "State"}


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

    # zone_family: one chip per selected zone (not one "Zone: A, B, C" chip),
    # so a single click removes just that zone — key encodes which one via
    # "zone_family::<zone>", parsed back out in remove_filter_via_chip below.
    for zone in filter_state.get("zone_family") or []:
        chips.append(
            html.Span(
                f"Zone: {zone} ×",
                id={"type": "filter-chip", "key": f"zone_family::{zone}"},
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
    if key == "year_range":
        state["year_range"] = [YEAR_MIN, YEAR_MAX]
    elif key.startswith("zone_family::"):
        zone = key.split("zone_family::", 1)[1]
        state["zone_family"] = [z for z in (state.get("zone_family") or []) if z != zone]
    else:
        state[key] = None
    return state
