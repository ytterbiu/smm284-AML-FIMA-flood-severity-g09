"""C4 — Coverage-ratio histogram, colored by under-insurance status band.

Same server-side-binning discipline as C2 (np.histogram, never raw arrays
to go.Histogram — see dashboard/AGENTS.md), but bin edges are three
concatenated linspace ranges (0->0.5, 0.5->0.8, 0.8->2.0) so the 0.5/0.8
status thresholds always land exactly on a bin boundary — no bar straddles
two status bands.
"""
from __future__ import annotations

import numpy as np
import polars as pl
import plotly.graph_objects as go

from charts.status_bands import (
    RATIO_CLIP,
    SEVERE_THRESHOLD,
    STATUS_COLORS,
    STATUS_ORDER,
    UNDER_THRESHOLD,
    compute_ratio_status,
)

TOTAL_BINS = 60


def _empty_figure(text: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(text=text, showarrow=False, font=dict(size=13, color="#94a3b8"))],
        margin=dict(t=45, l=10, r=10, b=10),
        height=380,
    )
    return fig


def _band_edges() -> tuple[np.ndarray, list[str]]:
    """Bin edges split proportionally by band width, plus each bin's status."""
    bounds = [0.0, SEVERE_THRESHOLD, UNDER_THRESHOLD, RATIO_CLIP]
    total_width = bounds[-1] - bounds[0]
    all_edges = [bounds[0]]
    bin_status: list[str] = []
    for lo, hi, status in zip(bounds[:-1], bounds[1:], STATUS_ORDER):
        n_bins = max(1, round(TOTAL_BINS * (hi - lo) / total_width))
        edges = np.linspace(lo, hi, n_bins + 1)
        all_edges.extend(edges[1:])
        bin_status.extend([status] * n_bins)
    return np.array(all_edges), bin_status


def build_coverage_histogram(df: pl.DataFrame) -> go.Figure:
    """df: filtered by year/state/zone_family (C4 has no filter of its own)."""
    valid = compute_ratio_status(df)
    if valid.height == 0:
        return _empty_figure("no properties with both coverage and replacement cost for this filter")

    edges, bin_status = _band_edges()
    counts, _ = np.histogram(valid["coverage_ratio"].to_numpy(), bins=edges)
    centers = (edges[:-1] + edges[1:]) / 2
    widths = np.diff(edges)
    colors = [STATUS_COLORS[s] for s in bin_status]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=centers, y=counts, width=widths,
            marker_color=colors,
            showlegend=False,
            hovertemplate="ratio ~%{x:.2f}<br>%{y:,} properties<extra></extra>",
        )
    )
    # Dummy traces purely to produce a legend for the 3 status colors.
    for status in STATUS_ORDER:
        fig.add_trace(
            go.Bar(x=[None], y=[None], name=status, marker_color=STATUS_COLORS[status], showlegend=True)
        )

    for threshold in (SEVERE_THRESHOLD, UNDER_THRESHOLD):
        fig.add_vline(x=threshold, line_dash="dash", line_color="#64748b", line_width=1)

    fig.update_layout(
        title=dict(text="Coverage ÷ replacement cost", x=0.5, xanchor="center"),
        xaxis_title="Coverage ratio",
        yaxis_title="Properties",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=70, l=10, r=10, b=10),
        height=380,
    )
    return fig
