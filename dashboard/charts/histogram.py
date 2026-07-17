"""C2 — Nominal vs. real severity histogram.

Bin counts/edges computed server-side with numpy (np.histogram), rendered
as overlaid go.Bar traces styled as a histogram — never hand raw per-row
arrays to go.Histogram (see dashboard/AGENTS.md "C2 — histogram" for why:
payload size must stay independent of row count for full-data scale).

Reproduces BE_notes.ipynb section 6 cell 21's approach: "raw" plots values
directly (showing the right-skew), "log" bins log10(value) instead (the
same transform the notebook uses to make the shape legible).
"""
from __future__ import annotations

import numpy as np
import polars as pl
import plotly.graph_objects as go

from data import TARGET

N_BINS = 60


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


def build_histogram(df: pl.DataFrame, log: bool = False) -> go.Figure:
    """df: filtered by year/state/zone_family (C2 has no filter of its own)."""
    nominal = df[f"{TARGET}_nominal"].drop_nulls().to_numpy()
    real = df[TARGET].drop_nulls().to_numpy()

    if log:
        nominal = np.log10(nominal[nominal > 0])
        real = real[real > 0]
        real = np.log10(real)
        xaxis_title = "Payout (log10 $)"
    else:
        xaxis_title = "Payout ($)"

    if len(nominal) == 0 and len(real) == 0:
        return _empty_figure("no claims for this filter")

    lo = min(nominal.min() if len(nominal) else np.inf, real.min() if len(real) else np.inf)
    hi = max(nominal.max() if len(nominal) else -np.inf, real.max() if len(real) else -np.inf)
    bins = np.linspace(lo, hi, N_BINS + 1)

    nominal_counts, edges = np.histogram(nominal, bins=bins)
    real_counts, _ = np.histogram(real, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    widths = np.diff(edges)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=centers, y=nominal_counts, width=widths,
            name="Nominal (as filed)", marker_color="indianred", opacity=0.55,
        )
    )
    fig.add_trace(
        go.Bar(
            x=centers, y=real_counts, width=widths,
            name="Real (2024 USD)", marker_color="steelblue", opacity=0.65,
        )
    )
    fig.update_layout(
        barmode="overlay",
        title=dict(text="Nominal vs. real severity", x=0.5, xanchor="center"),
        xaxis_title=xaxis_title,
        yaxis_title="Claims",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=70, l=10, r=10, b=10),
        height=380,
    )
    return fig
