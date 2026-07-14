"""C12 — Double lift chart, Model section (path="/model/lift").

Standard double-lift method: rank OOT rows by the ratio of two models'
predictions (model_a / model_b), bucket into ~equal-sized deciles, and plot
average actual severity alongside both models' average predictions per
decile. Deciles are where the two models disagree most (low/high ratio) —
whichever model tracks the actual-severity line more closely there is the
better discriminator on the cases the other model gets most wrong.

Model pair is chosen on the page (pages/model_lift.py's two dropdowns,
restricted to whatever's toggled on in model-selection-state), not a
parameter of the model-selection toggle itself.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from model_data import MODEL_COLORS, TARGET, get_oot_df, get_oot_predictions
from charts.common import empty_state_figure

N_BINS = 10
_ACTUAL_COLOR = "#333333"  # neutral "ground truth" reference line, not a model identity color


def build_double_lift_chart(model_a: str | None, model_b: str | None, n_bins: int = N_BINS) -> go.Figure:
    if not model_a or not model_b:
        return empty_state_figure("Select two models to compare.")
    if model_a == model_b:
        return empty_state_figure("Select two different models to compare.")

    oot = get_oot_df()
    actual = oot[TARGET].to_numpy().astype(float)
    pred_a = get_oot_predictions(model_a)
    pred_b = get_oot_predictions(model_b)

    ratio = pred_a / np.maximum(pred_b, 1e-6)
    order = np.argsort(ratio, kind="stable")
    bins = np.array_split(order, n_bins)

    x = list(range(1, len(bins) + 1))
    actual_means = [actual[idx].mean() for idx in bins]
    a_means = [pred_a[idx].mean() for idx in bins]
    b_means = [pred_b[idx].mean() for idx in bins]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x, y=actual_means, mode="lines+markers", name="Actual",
            line=dict(color=_ACTUAL_COLOR, width=2, dash="dot"), marker=dict(size=8),
            hovertemplate="Decile %{x}<br>Actual: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=a_means, mode="lines+markers", name=model_a,
            line=dict(color=MODEL_COLORS[model_a], width=2), marker=dict(size=8),
            hovertemplate=f"Decile %{{x}}<br>{model_a}: $%{{y:,.0f}}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=b_means, mode="lines+markers", name=model_b,
            line=dict(color=MODEL_COLORS[model_b], width=2), marker=dict(size=8),
            hovertemplate=f"Decile %{{x}}<br>{model_b}: $%{{y:,.0f}}<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(text=f"Double lift chart — {model_a} vs. {model_b}", x=0.5, xanchor="center"),
        xaxis=dict(
            title=f"Decile, ranked by {model_a} / {model_b} predicted-severity ratio (ascending)",
            tickmode="linear",
            dtick=1,
        ),
        yaxis=dict(title="Average claim severity ($)", tickformat="$,.0f"),
        height=450,
        legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5),
        margin=dict(t=45, l=10, r=10, b=110),
    )
    return fig
