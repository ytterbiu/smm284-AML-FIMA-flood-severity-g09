"""C3 — Payout by flood zone (zone_family), one box per zone.

Uses Plotly's precomputed-statistics mode for go.Box (q1/median/q3/
lowerfence/upperfence computed server-side with Polars .quantile()) rather
than passing raw per-row arrays — see dashboard/AGENTS.md "C3 — zone
boxplots" for why (payload size independent of row count; avoids
rendering an outlier marker per point on this heavily right-skewed data).

C3 never filters itself by zone_family — the selected zone is highlighted
(full opacity), others dimmed, but all 6 always render. See PLAN_UI.md
"never filter yourself" rule.
"""
from __future__ import annotations

import polars as pl
import plotly.graph_objects as go

from data import TARGET
from src.data.clean import ZONE_ORDER  # sys.path already extended by `data`'s import

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


def build_zone_boxplots(
    df: pl.DataFrame,
    stat: str = "median",
    selected_zone: str | None = None,
) -> go.Figure:
    """df: filtered by year/state (NOT by zone_family; all 6 boxes always shown)."""
    if df.height == 0:
        return _empty_figure("no claims for this filter")

    stats = df.group_by("zone_family").agg(
        q1=pl.col(TARGET).quantile(0.25),
        median=pl.col(TARGET).median(),
        q3=pl.col(TARGET).quantile(0.75),
        min_val=pl.col(TARGET).min(),
        max_val=pl.col(TARGET).max(),
    )
    stats_by_zone = {row["zone_family"]: row for row in stats.to_dicts()}

    fig = go.Figure()
    for zone in ZONE_ORDER:
        s = stats_by_zone.get(zone)
        if s is None:
            continue  # no claims for this zone under the current year/state filter
        iqr = s["q3"] - s["q1"]
        lowerfence = max(s["min_val"], s["q1"] - 1.5 * iqr)
        upperfence = min(s["max_val"], s["q3"] + 1.5 * iqr)
        active = selected_zone is None or zone == selected_zone
        fig.add_trace(
            go.Box(
                x=[zone],
                q1=[s["q1"]],
                median=[s["median"]],
                q3=[s["q3"]],
                lowerfence=[lowerfence],
                upperfence=[upperfence],
                name=zone,
                boxpoints=False,
                opacity=1.0 if active else DIMMED_OPACITY,
                marker_color="steelblue",
                showlegend=False,
            )
        )

    agg_expr = pl.col(TARGET).median() if stat == "median" else pl.col(TARGET).mean()
    ref_val = df.select(agg_expr).item()
    fig.add_hline(
        y=ref_val,
        line_dash="dash",
        line_color="#64748b",
        annotation_text=f"{stat.title()} (all zones): ${ref_val:,.0f}",
        annotation_position="top left",
    )

    fig.update_layout(
        title=dict(text="Payout by flood zone", x=0.5, xanchor="center"),
        yaxis_title="Payout ($)",
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
        margin=dict(t=45, l=10, r=10, b=10),
        height=420,
    )
    return fig
