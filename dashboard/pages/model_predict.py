"""
Model section — Predict (path="/model/predict")

Feature-input form (the 6 NUMERIC + 8 CATEG fields from metadata.json's
input_schema) -> live prediction from all 4 models (Baseline/GLM/RF/GBM)
side by side, as cards + a comparison chart. Does not participate in the
shared filter-state/control row — see dashboard/AGENTS.md "Hiding the
shared control row on the Model section".

Dropdown options and defaults are derived dynamically from our own
processed data (model_data.get_model_df()), not hardcoded — guarantees the
form never offers a category the models weren't trained on.
"""
from __future__ import annotations

import sys
from pathlib import Path

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import polars as pl

import model_data
from charts.predict_comparison import build_predict_comparison

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.data.clean import US_STATES, ZONE_ORDER  # noqa: E402

dash.register_page(__name__, path="/model/predict", name="Predict", order=5)

BOOLEAN_FIELDS = {
    "postFIRMConstructionIndicator_i",
    "elevatedBuildingIndicator_i",
    "primaryResidenceIndicator_i",
}

FIELD_LABELS = {
    "totalBuildingInsuranceCoverage": "Building Coverage ($)",
    "totalContentsInsuranceCoverage": "Contents Coverage ($)",
    "deductible_amount": "Deductible ($)",
    "building_age": "Building Age (years)",
    "crsClassificationCode": "CRS Classification Code",
    "elevationDifference": "Elevation Difference (ft)",
    "zone_family": "Flood Zone",
    "occupancy_class": "Occupancy Type",
    "state": "State",
    "floors_cat": "Number of Floors",
    "basement_cat": "Basement / Enclosure Type",
    "postFIRMConstructionIndicator_i": "Post-FIRM Construction",
    "elevatedBuildingIndicator_i": "Elevated Building",
    "primaryResidenceIndicator_i": "Primary Residence",
}


def _sort_key(v):
    """Numeric-coded strings sort numerically; non-numeric ("missing") last."""
    try:
        return (0, int(v))
    except (TypeError, ValueError):
        return (1, str(v))


def _input_id(field: str) -> str:
    return f"predict-input-{field}"


# ── Derive dropdown options + defaults from our own data (once, at import) ──

_df = model_data.get_model_df()

NUMERIC_DEFAULTS: dict[str, float] = {
    c: float(_df[c].drop_nulls().median()) for c in model_data.NUMERIC
}


def _valid_values(field: str) -> pl.Series:
    vals = _df[field].drop_nulls()
    if field == "state":
        vals = vals.filter(vals.is_in(list(US_STATES)))
    return vals


def _options_and_default(field: str) -> tuple[list, object]:
    if field in BOOLEAN_FIELDS:
        return [0, 1], 0
    vals = _valid_values(field)
    if field == "zone_family":
        present = set(vals.to_list())
        options = [z for z in ZONE_ORDER if z in present]
    else:
        options = sorted(vals.unique().to_list(), key=_sort_key)
    default = vals.value_counts().sort("count", descending=True)[field][0]
    return options, default


CATEG_OPTIONS: dict[str, list] = {}
CATEG_DEFAULTS: dict[str, object] = {}
for _field in model_data.CATEG:
    CATEG_OPTIONS[_field], CATEG_DEFAULTS[_field] = _options_and_default(_field)


# ── Layout ───────────────────────────────────────────────────────────────────

def _numeric_field(field: str) -> dbc.Col:
    return dbc.Col(
        html.Div(
            [
                html.Label(FIELD_LABELS[field], className="small fw-semibold mb-1"),
                dcc.Input(
                    id=_input_id(field),
                    type="number",
                    value=round(NUMERIC_DEFAULTS[field], 2),
                    className="form-control form-control-sm",
                ),
            ]
        ),
        width=4,
        className="mb-3",
    )


def _categ_field(field: str) -> dbc.Col:
    if field in BOOLEAN_FIELDS:
        options = [{"label": "No", "value": 0}, {"label": "Yes", "value": 1}]
    else:
        options = [{"label": v, "value": v} for v in CATEG_OPTIONS[field]]
    return dbc.Col(
        html.Div(
            [
                html.Label(FIELD_LABELS[field], className="small fw-semibold mb-1"),
                dcc.Dropdown(
                    id=_input_id(field),
                    options=options,
                    value=CATEG_DEFAULTS[field],
                    clearable=False,
                ),
            ]
        ),
        width=3,
        className="mb-3",
    )


def _result_card(key: str, label: str) -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.P(label, className="kpi-label mb-1"),
                    html.P(id=f"predict-result-{key}", className="kpi-value mb-0", children="—"),
                ]
            ),
            className="kpi-card",
        ),
        width=3,
    )


RESULT_CARDS = [
    ("baseline", "Baseline (zone mean)"),
    ("glm", "GLM"),
    ("rf", "RF"),
    ("gbm", "GBM"),
]

layout = dbc.Container(
    [
        html.H4("Predict flood claim severity", className="mt-3 mb-3"),
        html.H6("Property features", className="text-muted mb-2"),
        dbc.Row([_numeric_field(f) for f in model_data.NUMERIC], className="g-3"),
        dbc.Row([_categ_field(f) for f in model_data.CATEG], className="g-3"),
        dbc.Button("Predict", id="predict-btn", color="primary", className="mb-4", n_clicks=0),
        dbc.Row([_result_card(k, l) for k, l in RESULT_CARDS], className="g-2 mb-3"),
        dcc.Loading(
            dcc.Graph(id="predict-comparison-chart", config={"displayModeBar": False}),
        ),
    ],
    fluid=True,
)


# ── Callback ─────────────────────────────────────────────────────────────────

ALL_FIELDS = model_data.NUMERIC + model_data.CATEG


@callback(
    Output("predict-result-baseline", "children"),
    Output("predict-result-glm", "children"),
    Output("predict-result-rf", "children"),
    Output("predict-result-gbm", "children"),
    Output("predict-comparison-chart", "figure"),
    Input("predict-btn", "n_clicks"),
    [State(_input_id(f), "value") for f in ALL_FIELDS],
)
def run_prediction(_n_clicks, *values):
    row = dict(zip(ALL_FIELDS, values))
    X = pl.DataFrame([row])

    results = {
        "Baseline (zone mean)": model_data.predict_baseline(row["zone_family"]),
        "GLM (Gamma, log-link)": float(model_data.predict("glm", X)[0]),
        "RF (bagging, smeared log target)": float(model_data.predict("rf", X)[0]),
        "GBM (gamma loss)": float(model_data.predict("gbm", X)[0]),
    }
    fig = build_predict_comparison(results)

    return (
        f"${results['Baseline (zone mean)']:,.0f}",
        f"${results['GLM (Gamma, log-link)']:,.0f}",
        f"${results['RF (bagging, smeared log target)']:,.0f}",
        f"${results['GBM (gamma loss)']:,.0f}",
        fig,
    )
