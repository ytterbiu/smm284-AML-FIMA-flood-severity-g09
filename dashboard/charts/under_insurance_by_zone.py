"""C5 — Under-insurance status share by flood zone, 100%-stacked bar.

Upgrades BE_notes.ipynb section 14's single-metric version (share under 80%
only) to a full 3-segment breakdown, same status colors as C4. Clickable
like C3: clicking a zone's bar sets the shared zone_family filter (dims
non-selected zones, never filters itself — see PLAN_UI.md "never filter
yourself" rule).
"""
from __future__ import annotations

import polars as pl
import plotly.graph_objects as go

from charts.status_bands import STATUS_COLORS, STATUS_ORDER, compute_ratio_status
from src.data.clean import ZONE_ORDER  # sys.path already extended by data's import

DIMMED_OPACITY = 0.35


def _empty_figure(text: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(text=text, showarrow=False, font=dict(size=13, color="#94a3b8"))],
        margin=dict(t=45, l=10, r=10, b=10),
        height=420,
    )
    return fig


def build_zone_status_bars(df: pl.DataFrame, selected_zone: str | None = None) -> go.Figure:
    """df: filtered by year/state (NOT by zone_family; all zones always shown)."""
    valid = compute_ratio_status(df)
    if valid.height == 0:
        return _empty_figure("no properties with both coverage and replacement cost for this filter")

    counts = valid.group_by(["zone_family", "status"]).agg(pl.len().alias("n"))
    zones_present = [z for z in ZONE_ORDER if z in counts["zone_family"].unique().to_list()]
    if not zones_present:
        return _empty_figure("no properties with both coverage and replacement cost for this filter")

    zone_totals = {
        z: counts.filter(pl.col("zone_family") == z)["n"].sum() for z in zones_present
    }
    opacities = [1.0 if (selected_zone is None or z == selected_zone) else DIMMED_OPACITY for z in zones_present]

    fig = go.Figure()
    for status in STATUS_ORDER:
        pct = []
        for z in zones_present:
            row = counts.filter((pl.col("zone_family") == z) & (pl.col("status") == status))
            n = row["n"].item() if row.height else 0
            pct.append(100 * n / zone_totals[z])
        fig.add_trace(
            go.Bar(
                x=zones_present,
                y=pct,
                name=status,
                marker=dict(color=STATUS_COLORS[status], opacity=opacities),
                hovertemplate="%{x}<br>" + status + ": %{y:.0f}%<extra></extra>",
            )
        )

    fig.update_layout(
        barmode="stack",
        title=dict(text="Under-insurance status share by flood zone", x=0.5, xanchor="center"),
        yaxis_title="Share of properties (%)",
        yaxis_range=[0, 100],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=70, l=10, r=10, b=10),
        height=420,
    )
    return fig
