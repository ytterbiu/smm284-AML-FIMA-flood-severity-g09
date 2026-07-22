"""C8/C9 — SHAP feature importance for the primary model (GBM only — see
PLAN_UI.md "Model section": BE_notes.ipynb cell 85 computes SHAP against
best_model exclusively, and shap.TreeExplainer only works on tree models
anyway, so there's no GLM/RF equivalent to show here).

Reimplemented in Plotly rather than the `shap` library's own matplotlib
plots — the library was only needed to *compute* these values (already
done, exported to exports/dashboard/), not to draw them. Both charts read
directly from that export, no live SHAP computation at dashboard runtime.
"""
from __future__ import annotations

import numpy as np
import polars as pl
import plotly.graph_objects as go

from model_data import EXPORTS_DIR

TOP_N = 12


def _clean_name(name: str) -> str:
    """Strip the ColumnTransformer prefix (money__/cat__/num__) for readability."""
    _, _, rest = name.partition("__")
    return rest or name


def build_shap_bar_chart() -> go.Figure:
    """C8 — mean |SHAP| by feature, from shap_mean_abs_by_feature.csv."""
    df = pl.read_csv(EXPORTS_DIR / "shap_mean_abs_by_feature.csv")
    df = df.rename({df.columns[0]: "feature"})
    df = df.sort("mean_abs_shap", descending=True).head(TOP_N)

    names = [_clean_name(f) for f in df["feature"].to_list()]
    values = df["mean_abs_shap"].to_list()

    fig = go.Figure(
        go.Bar(
            y=names[::-1],
            x=values[::-1],
            orientation="h",
            marker_color="#ff0051",  # shap library's own high-value color, matching the beeswarm
            text=values[::-1],
            texttemplate="+%{text:.2f}",
            textposition="outside",
            hovertemplate="%{y}<br>mean |SHAP|: %{x:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text="Feature importance (mean |SHAP|) — GBM", x=0.5, xanchor="center"),
        xaxis_title="mean |SHAP value|",
        # Outside text labels need room beyond the longest bar, or the
        # top bar's label gets clipped by the plot boundary — pad the
        # range rather than relying on the data's own max.
        xaxis_range=[0, max(values) * 1.2],
        height=450,
        margin=dict(t=45, l=10, r=60, b=10),
    )
    return fig


def build_shap_beeswarm() -> go.Figure:
    """C9 — SHAP summary (beeswarm), from shap_values_oot_sample.npz.

    One go.Scatter trace per feature: x = SHAP value per row, y = feature's
    row position + random jitter (approximates the density-packed "swarm"),
    color = that feature's own transformed value (min-max normalized per
    feature — SHAP's own beeswarm colors within each feature's own scale
    too, since different features have very different ranges).
    """
    npz = np.load(EXPORTS_DIR / "shap_values_oot_sample.npz", allow_pickle=True)
    shap_values = npz["shap_values"]
    X_transformed = npz["X_transformed"]
    feature_names = npz["feature_names"]

    mean_abs = np.abs(shap_values).mean(axis=0)
    top_idx = np.argsort(mean_abs)[::-1][:TOP_N]

    rng = np.random.default_rng(9)  # RANDOM_STATE=9, matches project convention
    fig = go.Figure()
    for rank, idx in enumerate(top_idx):
        fname = _clean_name(str(feature_names[idx]))
        sv = shap_values[:, idx]
        fv = X_transformed[:, idx]
        fv_min, fv_max = fv.min(), fv.max()
        fv_norm = (fv - fv_min) / (fv_max - fv_min) if fv_max > fv_min else np.zeros_like(fv)
        y_jitter = rank + rng.uniform(-0.35, 0.35, size=len(sv))

        fig.add_trace(
            go.Scatter(
                x=sv,
                y=y_jitter,
                mode="markers",
                marker=dict(
                    size=5,
                    color=fv_norm,
                    colorscale=[[0, "#008bfb"], [1, "#ff0051"]],  # shap library's own default red_blue colors
                    showscale=(rank == 0),
                    colorbar=dict(title="Feature value", tickvals=[0, 1], ticktext=["Low", "High"])
                    if rank == 0
                    else None,
                ),
                showlegend=False,
                hovertemplate=f"<b>{fname}</b><br>SHAP: %{{x:.3f}}<extra></extra>",
            )
        )

    fig.add_vline(x=0, line_color="#c3c2b7", line_width=1)
    fig.update_yaxes(
        tickmode="array",
        tickvals=list(range(len(top_idx))),
        ticktext=[_clean_name(str(feature_names[i])) for i in top_idx],
        autorange="reversed",
    )
    fig.update_layout(
        title=dict(text="SHAP summary (beeswarm) — GBM", x=0.5, xanchor="center"),
        xaxis_title="SHAP value",
        height=500,
        margin=dict(t=45, l=10, r=10, b=10),
    )
    return fig
