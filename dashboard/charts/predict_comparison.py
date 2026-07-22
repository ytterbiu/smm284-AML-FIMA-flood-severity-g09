"""C7 — Predicted severity comparison across models, for the Predict page.

One horizontal bar per model, same identity colors as the performance
page's oot_scoreboard (model_data.MODEL_COLORS) so the two pages read as
one system.
"""
from __future__ import annotations

import plotly.graph_objects as go

from model_data import MODEL_COLORS

# display order: baseline first (the thing being beaten), then the 3 fitted models
DISPLAY_ORDER = [
    "Baseline (zone mean)",
    "GLM (Gamma, log-link)",
    "RF (bagging, smeared log target)",
    "GBM (gamma loss)",
]


def build_predict_comparison(results: dict[str, float]) -> go.Figure:
    """results: {model display name -> predicted $ severity}, keys matching
    MODEL_COLORS / DISPLAY_ORDER."""
    order = [m for m in DISPLAY_ORDER if m in results]

    fig = go.Figure()
    for model in order:
        fig.add_trace(
            go.Bar(
                y=[model],
                x=[results[model]],
                orientation="h",
                marker_color=MODEL_COLORS[model],
                showlegend=False,
                text=[results[model]],
                texttemplate="%{x:$,.0f}",
                textposition="outside",
                hovertemplate=f"<b>{model}</b><br>$%{{x:,.0f}}<extra></extra>",
            )
        )

    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat="$,.0f")
    fig.update_layout(
        title=dict(text="Predicted severity by model", x=0.5, xanchor="center"),
        height=280,
        margin=dict(t=45, l=10, r=40, b=10),
    )
    return fig
