"""C10 — Permutation importance for the primary model (GBM only — see
shap_importance.py's module docstring for why this section is GBM-only).

Not exported by the teammate (checked exports/dashboard/ directly — no
permutation-importance file exists there), but fully replicable ourselves:
BE_notes.ipynb cell 60 computes it generically via sklearn's
permutation_importance against best_model, no custom-class dependency like
RF's smearing wrapper, so it works against our own model_gbm.joblib +
our own OOT data. Dual-scored (MAE + gamma deviance, matching the
notebook's "gamma deviance selects, MAE communicates" framing) on the RAW
14 features, not the ~99 one-hot-expanded ones SHAP's export uses.

Deliberately uses the model's raw (unclipped) predictions, matching the
notebook's own choice — "the cap is a post-rule; here we measure the
model's own reliance on each feature" — so this does NOT go through
model_data.predict()'s clip_at_coverage.

Computed once and cached at module level (14 features x 10 repeats x 2
scorers on our own ~2,445-row OOT sample — a real but one-time cost, not
re-run per page view).
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.inspection import permutation_importance
from sklearn.metrics import make_scorer, mean_gamma_deviance

import model_data

N_REPEATS = 10
RANDOM_STATE = 9  # matches BE_notes.ipynb's RANDOM_STATE

# permutation_importance's cost is ~linear in row count (one model.predict()
# per feature x repeat). Sample-mode OOT data (~2,445 rows) never gets near
# this, but full-mode OOT data (~213,746 rows, per the notebook's own
# figures) would take ~10 minutes uncapped -- BE_notes.ipynb cell 60 hit the
# same cost and caps at SUB = min(50_000, len(X_test)); mirroring that here.
MAX_ROWS = 50_000


def _gamma_dev_floored(y_true, y_pred):
    return mean_gamma_deviance(y_true, np.maximum(y_pred, model_data.GAMMA_DEV_FLOOR))


_SCORERS = {
    "gamma_dev": make_scorer(_gamma_dev_floored, greater_is_better=False),
    "MAE": "neg_mean_absolute_error",
}

_cache: dict | None = None


def compute_permutation_importance() -> dict:
    """Returns {"features": [...], "mae_increase": [...], "mae_std": [...],
    "dev_increase": [...]} — one row per raw feature, in a fixed order
    (features and importance values in the same index order across both
    metrics, so a feature's position is trackable across panels)."""
    global _cache
    if _cache is not None:
        return _cache

    df = model_data.get_oot_df()
    if df.height > MAX_ROWS:
        df = df.sample(n=MAX_ROWS, seed=RANDOM_STATE)
    fields = model_data.NUMERIC + model_data.CATEG
    X = df.select(fields).to_pandas()
    y = df[model_data.TARGET].to_numpy().astype(float)
    gbm = model_data.get_model("gbm")  # raw pipeline, unclipped — matches the notebook's choice

    pi = permutation_importance(
        gbm, X, y,
        scoring=_SCORERS,
        n_repeats=N_REPEATS,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    _cache = {
        "features": fields,
        "mae_increase": pi["MAE"].importances_mean.tolist(),
        "mae_std": pi["MAE"].importances_std.tolist(),
        # greater_is_better=False already makes the scorer return -deviance, so
        # importances_mean = scorer(orig) - scorer(permuted) = dev_permuted -
        # dev_original — already positive for a useful feature, no negation
        # needed (matches the notebook's own cell 60, which uses this
        # unnegated too).
        "dev_increase": pi["gamma_dev"].importances_mean.tolist(),
        "dev_std": pi["gamma_dev"].importances_std.tolist(),
    }
    return _cache


def build_permutation_importance_chart() -> go.Figure:
    """C10 — small multiples (MAE increase | deviance increase), same
    feature order (by MAE increase, descending) fixed across both panels
    — same convention as charts/oot_scoreboard.py."""
    result = compute_permutation_importance()
    # descending mae_increase (most important first) so that, combined with
    # autorange="reversed" below, the most important feature ends up at the
    # top — NOT the same "ascending + reversed" recipe oot_scoreboard.py
    # uses, since there ascending MAE means "best model first" (lower is
    # better), whereas here higher mae_increase means "more important."
    order = sorted(
        range(len(result["features"])), key=lambda i: result["mae_increase"][i], reverse=True
    )
    features = [result["features"][i] for i in order]
    mae = [result["mae_increase"][i] for i in order]
    mae_std = [result["mae_std"][i] for i in order]
    dev = [result["dev_increase"][i] for i in order]
    dev_std = [result["dev_std"][i] for i in order]

    def _dollar(v: float) -> str:
        return f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"

    mae_labels = [f"{_dollar(m)} (±${s:,.0f})" for m, s in zip(mae, mae_std)]
    dev_labels = [f"{d:.3f} (±{s:.3f})" for d, s in zip(dev, dev_std)]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["MAE increase when shuffled ($)", "Gamma deviance increase when shuffled"],
        horizontal_spacing=0.2,
    )
    fig.add_trace(
        go.Bar(
            y=features,
            x=mae,
            orientation="h",
            error_x=dict(type="data", array=mae_std),
            marker_color="#2a78d6",
            showlegend=False,
            hovertemplate="%{y}<br>+$%{x:,.0f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            y=features,
            x=dev,
            orientation="h",
            error_x=dict(type="data", array=dev_std),
            marker_color="#1baf7a",
            showlegend=False,
            hovertemplate="%{y}<br>+%{x:.3f}<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # Value+std labels as explicit annotations, not go.Bar's built-in
    # textposition="outside" — that only accounts for the bar's own length,
    # not the error-bar whisker extending past it, so text and whisker
    # collided. Placing each label a fixed gap beyond its own whisker tip
    # (value +/- std, sign-aware for the one negative bar) avoids that.
    _place_value_labels(fig, features, mae, mae_std, mae_labels, row=1, col=1)
    _place_value_labels(fig, features, dev, dev_std, dev_labels, row=1, col=2)

    fig.update_xaxes(tickformat="$,.0f", row=1, col=1)
    fig.update_xaxes(tickformat=",.3f", row=1, col=2)
    for c in (1, 2):
        fig.add_vline(x=0, line_color="#c3c2b7", line_width=1, row=1, col=c)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        title=dict(text="Permutation importance (raw features) — GBM", x=0.5, xanchor="center"),
        height=450,
        margin=dict(t=70, l=10, r=10, b=10),
    )
    return fig


def _place_value_labels(fig, categories, values, stds, labels, row, col):
    """Add one text annotation per bar, positioned a fixed gap beyond that
    bar's own whisker tip (value +/- std) — and widen the axis range to
    leave room for the label text, sign-aware since one bar (state) is
    negative and its whisker/label extend further left instead of right."""
    tips = [v + (s if v >= 0 else -s) for v, s in zip(values, stds)]
    lo, hi = min(0, *tips), max(0, *tips)
    span = (hi - lo) or 1.0
    gap = span * 0.04

    for cat, v, tip, lab in zip(categories, values, tips, labels):
        sign = 1 if v >= 0 else -1
        fig.add_annotation(
            x=tip + sign * gap,
            y=cat,
            text=lab,
            showarrow=False,
            xanchor="left" if v >= 0 else "right",
            font=dict(size=10, color="#0b0b0b"),
            row=row,
            col=col,
        )

    fig.update_xaxes(range=[lo - span * 0.05, hi + span * 0.38], row=row, col=col)
