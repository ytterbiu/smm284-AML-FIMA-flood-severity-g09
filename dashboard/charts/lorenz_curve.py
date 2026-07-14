"""C11 — Lorenz curve, Model section (path="/model/lift").

Not exported by the teammate (`oot_scoreboard_insurance.csv` has the
resulting Gini per model, but not the curve itself), so computed here
against our own OOT-filtered data via model_data.get_oot_predictions() —
same "compute ourselves, cross-check against the exported summary metric"
approach as charts/permutation_importance.py.

Convention: for a given model, rank OOT rows ascending by that model's
predicted severity, then plot cumulative % of policies (x) against
cumulative % of actual loss (y). A model with no discrimination ability
(e.g. a constant baseline) produces the diagonal; a model that separates
cheap from expensive claims well sags below the diagonal at low ranks and
rises above it at high ranks. Gini = 1 - 2*(area under the curve) — verified
against oot_scoreboard_insurance.csv's own Gini column before shipping:
same ranking (GBM > RF > GLM > zone-mean baseline > global baselines near
zero) and same order of magnitude, on our own ~2,445-row OOT sample vs.
their full OOT set.

Filtered by the model-selection toggle (model-selection-state), not the
Pages 1-2 claims filter-state — see PLAN_UI.md "Model-selection toggle".
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from model_data import MODEL_COLORS, TARGET, get_oot_df, get_oot_predictions
from charts.common import empty_state_figure


def _lorenz_xy(actual: np.ndarray, predicted: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(predicted, kind="stable")
    cum_actual = np.concatenate([[0.0], np.cumsum(actual[order])])
    cum_actual = cum_actual / cum_actual[-1]
    cum_policies = np.linspace(0.0, 1.0, len(actual) + 1)
    return cum_policies, cum_actual


def _gini(cum_policies: np.ndarray, cum_actual: np.ndarray) -> float:
    return 1 - 2 * np.trapezoid(cum_actual, cum_policies)


def compute_ginis(selected_models: list[str] | None) -> list[tuple[str, float]]:
    """(model, gini) pairs for the selected models, sorted descending by Gini
    (best risk-ranking ability first) — feeds the Gini table under the
    Lorenz curve (pages/model_lift.py), computed from the same _lorenz_xy
    curve the chart itself draws, so the table and chart can never disagree."""
    selected = [m for m in MODEL_COLORS if m in (selected_models or [])]
    if not selected:
        return []
    oot = get_oot_df()
    actual = oot[TARGET].to_numpy().astype(float)
    ginis = []
    for model in selected:
        x, y = _lorenz_xy(actual, get_oot_predictions(model))
        ginis.append((model, _gini(x, y)))
    return sorted(ginis, key=lambda pair: pair[1], reverse=True)


def build_lorenz_curve(selected_models: list[str] | None) -> go.Figure:
    # Fixed MODEL_COLORS order (not selection-click order) so a model's
    # legend position/color stays stable as the toggle changes.
    selected = [m for m in MODEL_COLORS if m in (selected_models or [])]
    if not selected:
        return empty_state_figure("Select at least one model to compare.")

    oot = get_oot_df()
    actual = oot[TARGET].to_numpy().astype(float)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            line=dict(color="#c3c2b7", dash="dash", width=1),
            name="No discrimination",
            hoverinfo="skip",
        )
    )
    for model in selected:
        pred = get_oot_predictions(model)
        x, y = _lorenz_xy(actual, pred)
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                line=dict(color=MODEL_COLORS[model], width=2),
                name=model,
                hovertemplate=f"<b>{model}</b><br>%{{x:.0%}} of policies<br>%{{y:.0%}} of loss<extra></extra>",
            )
        )

    fig.update_layout(
        title=dict(text="Lorenz curve — risk-ranking ability by model", x=0.5, xanchor="center"),
        xaxis=dict(title="Cumulative % of policies (ranked by predicted severity, ascending)", tickformat=".0%"),
        yaxis=dict(title="Cumulative % of actual loss", tickformat=".0%"),
        height=460,
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5),
        margin=dict(t=45, l=10, r=10, b=110),
    )
    return fig
