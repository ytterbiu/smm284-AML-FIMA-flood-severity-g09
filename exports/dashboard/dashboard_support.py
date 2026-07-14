"""Support module for the flood-severity model artifacts.

Usage in the dashboard:

    from dashboard_support import load_model, clip_at_coverage
    gbm = load_model("model_gbm.joblib")          # works for glm/gbm/rf
    pred = clip_at_coverage(gbm.predict(X_raw), X_raw)

X_raw must contain the raw (untransformed) columns listed in
metadata.json["input_schema"]; each pipeline does its own preprocessing.
"""
from __future__ import annotations

import sys

import joblib
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin, clone


def clip_at_coverage(y_pred, X, cap_col="totalBuildingInsuranceCoverage"):
    """Cap predictions at the policy's building coverage limit (business
    rule: a payout above the cap is contractually impossible). Rows with no
    recorded limit are left unclipped."""
    cap = X[cap_col].to_numpy(dtype=float)
    cap = np.where(np.isfinite(cap) & (cap > 0), cap, np.inf)
    return np.minimum(y_pred, cap)


class CoverageClippedRegressor(BaseEstimator, RegressorMixin):
    """Applies the coverage-cap rule inside predict()."""

    def __init__(self, estimator, cap_col="totalBuildingInsuranceCoverage"):
        self.estimator = estimator
        self.cap_col = cap_col

    def fit(self, X, y):
        self.estimator_ = clone(self.estimator).fit(X, y)
        return self

    def predict(self, X):
        return clip_at_coverage(self.estimator_.predict(X), X, self.cap_col)


class SmearedLogTargetRegressor(BaseEstimator, RegressorMixin):
    """Fits the inner regressor on z = log1p(y) and back-transforms with
    Duan's smearing correction (estimated from OOB residuals where
    available). Must match the notebook definition byte-for-byte in
    behaviour, or unpickled RF predictions change."""

    def __init__(self, estimator):
        self.estimator = estimator

    def fit(self, X, y):
        z = np.log1p(np.asarray(y, dtype=float))
        self.estimator_ = clone(self.estimator).fit(X, z)
        oob = getattr(self.estimator_, "oob_prediction_", None)
        pred_z = oob if oob is not None else self.estimator_.predict(X)
        resid = z - pred_z
        resid = resid[np.isfinite(resid)]
        self.smear_ = float(np.mean(np.exp(resid)))
        return self

    def predict(self, X):
        return np.maximum(
            np.exp(self.estimator_.predict(X)) * self.smear_ - 1.0, 0.0
        )


_NOTEBOOK_CLASSES = (CoverageClippedRegressor, SmearedLogTargetRegressor)


def load_model(path):
    """joblib.load that first registers the notebook-defined classes into
    __main__, so pickles created inside a notebook unpickle anywhere."""
    main = sys.modules["__main__"]
    for cls in _NOTEBOOK_CLASSES:
        if not hasattr(main, cls.__name__):
            setattr(main, cls.__name__, cls)
    return joblib.load(path)
