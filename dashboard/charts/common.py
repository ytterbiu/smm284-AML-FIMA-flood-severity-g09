"""dashboard/charts/common.py — small helpers shared across chart modules."""
from __future__ import annotations

import plotly.graph_objects as go


def empty_state_figure(text: str, height: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(text=text, showarrow=False, font=dict(size=14, color="#94a3b8"))],
        height=height,
        margin=dict(t=20, l=10, r=10, b=10),
    )
    return fig
