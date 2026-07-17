"""C1 — Choropleth map: median/mean amountPaidOnBuildingClaim by state.

go.Choropleth (not px) so a second highlight-overlay trace can be added for
the selected state — same pattern as the reference app's choropleth.py.
"""
from __future__ import annotations

import polars as pl
import plotly.graph_objects as go

from data import TARGET


def build_choropleth(
    df: pl.DataFrame,
    stat: str = "median",
    selected_state: str | None = None,
    zmin: float | None = None,
    zmax: float | None = None,
) -> go.Figure:
    """
    df             : filtered by year and zone_family (NOT by state; map shows all states).
    stat           : 'median' or 'mean'
    selected_state : 2-letter code to highlight, or None.
    zmin, zmax     : fixed colorbar range (see data.get_stat_range) so colors
                     mean the same $ amount across different filter states.
                     Falls back to Plotly's auto-range (per-call, not fixed)
                     if omitted.
    """
    agg_expr = (
        pl.col(TARGET).median() if stat == "median" else pl.col(TARGET).mean()
    )
    state_df = (
        df.group_by("state")
        .agg(agg_expr.alias("value"), pl.len().alias("n"))
        .sort("state")
    )

    states = state_df["state"].to_list()
    values = state_df["value"].to_list()
    counts = state_df["n"].to_list()

    fig = go.Figure()

    fig.add_trace(
        go.Choropleth(
            locations=states,
            z=values,
            zmin=zmin,
            zmax=zmax,
            locationmode="USA-states",
            colorscale="YlOrRd",
            colorbar=dict(title=dict(text="Payout ($)"), tickformat="$,.0f"),
            customdata=counts,
            marker_line_color="white",
            marker_line_width=0.5,
            hovertemplate="<b>%{location}</b><br>$%{z:,.0f}<br>%{customdata:,} claims<extra></extra>",
        )
    )

    if selected_state and selected_state in states:
        idx = states.index(selected_state)
        fig.add_trace(
            go.Choropleth(
                locations=[selected_state],
                z=[values[idx]],
                locationmode="USA-states",
                colorscale=[[0, "#1d4ed8"], [1, "#1d4ed8"]],
                marker_line_color="#0f172a",
                marker_line_width=3,
                showscale=False,
                showlegend=False,
                hovertemplate=(
                    f"<b>{selected_state}</b> (selected — click to deselect)"
                    "<br>$%{z:,.0f}<extra></extra>"
                ),
            )
        )

    stat_label = "Median" if stat == "median" else "Mean"
    subtitle = f" — <b>{selected_state}</b> selected" if selected_state else ""

    fig.update_layout(
        title=dict(text=f"{stat_label} payout by state{subtitle}", x=0.5, xanchor="center"),
        geo=dict(scope="usa", projection_type="albers usa", showlakes=False),
        margin=dict(t=45, l=0, r=0, b=0),
        height=420,
        clickmode="event",
    )

    return fig
