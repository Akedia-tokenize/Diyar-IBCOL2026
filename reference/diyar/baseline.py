"""Temporal engine: per-building baseline (CalTRACK-style hourly), accepted only if it meets
ASHRAE Guideline 14 (CV(RMSE) <= 30%, |NMBE| <= 10%). The fitted coefficients are committed
as a record BEFORE the period they will judge, so the baseline is fixed while it is still
unknown whom it favours (whitepaper VII).
"""
import numpy as np
import pandas as pd

from .crypto import H, canonical

KNOTS_C = (np.array([30, 45, 55, 65, 75, 90], dtype=float) - 32) * 5 / 9
SPEC = {"model": "hour-of-week + piecewise-linear temperature (CalTRACK bins)", "knots_C": [round(k, 4) for k in KNOTS_C],
        "acceptance": "ASHRAE Guideline 14 hourly: CV(RMSE)<=0.30, |NMBE|<=0.10"}


def design(hours, temps) -> np.ndarray:
    idx = pd.DatetimeIndex(hours)
    how = idx.dayofweek * 24 + idx.hour
    X = np.zeros((len(idx), 168))
    X[np.arange(len(idx)), how] = 1.0
    t = np.asarray(temps, dtype=float)
    cols = [np.minimum(t, KNOTS_C[0])]
    cols += [np.clip(t, lo, hi) - lo for lo, hi in zip(KNOTS_C[:-1], KNOTS_C[1:])]
    cols.append(np.maximum(t - KNOTS_C[-1], 0))
    return np.hstack([X, np.column_stack(cols)])


def fit(hours, temps, y):
    X, y = design(hours, temps), np.asarray(y, dtype=float)
    m = ~np.isnan(y) & ~np.isnan(X).any(1) & (y > 0)
    beta, *_ = np.linalg.lstsq(X[m], y[m], rcond=None)
    res = y[m] - X[m] @ beta
    n, p = int(m.sum()), X.shape[1]
    mu = float(y[m].mean())
    cv = float(np.sqrt((res ** 2).sum() / (n - p)) / mu)
    nmbe = float(res.sum() / ((n - p) * mu))
    return {"beta": [round(float(b), 6) for b in beta], "cv_rmse": round(cv, 4), "nmbe": round(nmbe, 4),
            "mean_hourly_kwh": round(mu, 4), "accepted": cv <= 0.30 and abs(nmbe) <= 0.10, "spec": SPEC}


def predict(model, hours, temps) -> np.ndarray:
    return design(hours, temps) @ np.asarray(model["beta"])


def model_version(model) -> str:
    return H(canonical({"beta": model["beta"], "spec": model["spec"]})).hex()[:16]
