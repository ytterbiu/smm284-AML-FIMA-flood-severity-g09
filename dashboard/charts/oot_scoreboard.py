"""C6 — Cross-model OOT performance comparison, from
exports/dashboard/oot_scoreboard.csv.

Small multiples (one horizontal-bar panel per metric) rather than one
combined chart — MAE/RMSE are dollars, R2/D2 are unitless and can go
negative, so they can't share an axis.

Same model order (ascending MAE, i.e. best-first) fixed across all four
panels, so a model's position can be visually tracked across metrics —
e.g. RF's mid-pack MAE vs. its much worse D2 is otherwise easy to miss.

Not filtered by the Pages 1-2 claims filter-state (see PLAN_UI.md "Model
section") — it IS filtered by the model-selection toggle (PLAN_UI.md
"Model-selection toggle"), so this is now wired to a callback in
pages/model_performance.py rather than built once at layout time.
"""
from __future__ import annotations

import polars as pl
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from model_data import EXPORTS_DIR, MODEL_COLORS
from charts.common import empty_state_figure

# (csv column, panel title, value format, hover format, zero-line)
METRICS = [
    ("MAE ($)", "MAE ($)", "$,.0f", ":$,.0f", False),
    ("RMSE ($)", "RMSE ($)", "$,.0f", ":$,.0f", False),
    ("D2 (gamma)", "D²", ",.3f", ":,.3f", True),
    ("R2", "R²", ",.3f", ":,.3f", True),
]
_POSITIONS = [(1, 1), (1, 2), (2, 1), (2, 2)]


def build_oot_scoreboard(selected_models: list[str] | None = None) -> go.Figure:
    df = pl.read_csv(EXPORTS_DIR / "oot_scoreboard.csv")
    if selected_models is not None:
        df = df.filter(pl.col("Model").is_in(selected_models))
    if df.height == 0:
        return empty_state_figure("Select at least one model to compare.")
    order = df.sort("MAE ($)")["Model"].to_list()  # best (lowest MAE) first

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[label for _, label, *_ in METRICS],
        horizontal_spacing=0.15,
        vertical_spacing=0.2,
    )

    for (col, _, tickfmt, hoverfmt, zero_line), (row, colpos) in zip(METRICS, _POSITIONS):
        first_panel = (row, colpos) == (1, 1)
        for model in order:
            value = df.filter(pl.col("Model") == model)[col].item()
            fig.add_trace(
                go.Bar(
                    y=[model],
                    x=[value],
                    orientation="h",
                    name=model,
                    marker_color=MODEL_COLORS[model],
                    showlegend=first_panel,
                    legendgroup=model,
                    text=[value],
                    texttemplate=f"%{{x{hoverfmt}}}",
                    textposition="outside",
                    hovertemplate=f"<b>{model}</b><br>{col}: %{{x{hoverfmt}}}<extra></extra>",
                ),
                row=row,
                col=colpos,
            )
        fig.update_xaxes(tickformat=tickfmt, row=row, col=colpos, automargin=True)
        if zero_line:
            fig.add_vline(x=0, line_color="#c3c2b7", line_width=1, row=row, col=colpos)

    fig.update_yaxes(autorange="reversed", showticklabels=True)
    fig.update_layout(
        height=750,
        title=dict(
            text="Model Performance Comparison on Test (Out-of-Time) Dataset",
            x=0.5,
            xanchor="center",
            y=0.985,
            yanchor="top",
        ),
        legend=dict(orientation="h", yanchor="top", y=-0.06, xanchor="center", x=0.5),
        margin=dict(t=70, l=10, r=10, b=90),
    )
    return fig
