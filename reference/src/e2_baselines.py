"""E2 step 1 — per-building baselines on BDG2 electricity, as in the whitepaper's temporal engine.

Model (CalTRACK-style hourly): hour-of-week indicators + piecewise-linear outdoor temperature
with CalTRACK bin edges (30/45/55/65/75/90 F, converted to C). Fitted on 2016.
Acceptance: ASHRAE Guideline 14 hourly criteria on the 2016 fit, CV(RMSE) <= 30% and |NMBE| <= 10%.

Outputs (per accepted building) daily nonconformity scores:
  * 2016: leave-one-month-out residuals (out of sample, used by the seasonal Mondrian scheme)
  * 2017: residuals from the full 2016 model (the live stream)
Score = |sum of hourly residuals over the day| / mean daily consumption in 2016.

Usage: python3 e2_baselines.py <bdg2_root> <out_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BDG2, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
KNOTS_C = np.array([30, 45, 55, 65, 75, 90], dtype=float)
KNOTS_C = (KNOTS_C - 32) * 5 / 9
MIN_COVERAGE = 0.90
MIN_HOURS_PER_DAY = 22

elec = pd.read_csv(BDG2 / "data/meters/cleaned/electricity_cleaned.csv", parse_dates=["timestamp"]).set_index("timestamp")
meta = pd.read_csv(BDG2 / "data/metadata/metadata.csv").set_index("building_id")
wx = pd.read_csv(BDG2 / "data/weather/weather.csv", parse_dates=["timestamp"])
temp = (wx.pivot_table(index="timestamp", columns="site_id", values="airTemperature")
          .reindex(elec.index).interpolate(limit=6, limit_direction="both"))


def temp_basis(t: np.ndarray) -> np.ndarray:
    """Piecewise-linear segments between CalTRACK knots (continuous hinge basis)."""
    cols = [np.minimum(t, KNOTS_C[0])]
    for lo, hi in zip(KNOTS_C[:-1], KNOTS_C[1:]):
        cols.append(np.clip(t, lo, hi) - lo)
    cols.append(np.maximum(t - KNOTS_C[-1], 0))
    return np.column_stack(cols)


def design(idx: pd.DatetimeIndex, t: np.ndarray) -> np.ndarray:
    how = idx.dayofweek * 24 + idx.hour
    X_how = np.zeros((len(idx), 168))
    X_how[np.arange(len(idx)), how] = 1.0
    return np.hstack([X_how, temp_basis(t)])


def fit_predict(X_tr, y_tr, X_te):
    beta, *_ = np.linalg.lstsq(X_tr, y_tr, rcond=None)
    return X_te @ beta


def daily_scores(idx, y, yhat, scale):
    df = pd.DataFrame({"r": y - yhat}, index=idx).dropna()
    g = df.groupby(df.index.normalize())["r"]
    ok = g.count() >= MIN_HOURS_PER_DAY
    return (g.sum()[ok].abs() / scale)


rows, stats = [], {"candidates": 0, "insufficient_data": 0, "failed_g14": 0, "accepted": 0}
g14 = []
for b in elec.columns:
    site = meta.at[b, "site_id"] if b in meta.index else None
    if site is None or site not in temp.columns:
        continue
    stats["candidates"] += 1
    y_all, t_all = elec[b], temp[site]
    y16, y17 = y_all.loc["2016"], y_all.loc["2017"]
    t16, t17 = t_all.loc["2016"], t_all.loc["2017"]
    m16 = y16.notna() & t16.notna() & (y16 > 0)
    m17 = y17.notna() & t17.notna() & (y17 > 0)
    if m16.mean() < MIN_COVERAGE or m17.mean() < MIN_COVERAGE:
        stats["insufficient_data"] += 1
        continue

    X16 = design(y16.index, t16.values)
    X17 = design(y17.index, t17.values)
    yv16 = y16.values
    fit16 = fit_predict(X16[m16], yv16[m16], X16)
    n, p = int(m16.sum()), X16.shape[1]
    resid = yv16[m16] - fit16[m16]
    mean_y = yv16[m16].mean()
    cv = np.sqrt((resid ** 2).sum() / (n - p)) / mean_y
    nmbe = resid.sum() / ((n - p) * mean_y)
    g14.append({"building": b, "cv_rmse": cv, "nmbe": nmbe})
    if cv > 0.30 or abs(nmbe) > 0.10:
        stats["failed_g14"] += 1
        continue
    stats["accepted"] += 1
    scale = mean_y * 24

    # 2016 leave-one-month-out (out of sample)
    lomo = np.full(len(yv16), np.nan)
    months = y16.index.month
    for mth in range(1, 13):
        te = months == mth
        tr = (~te) & m16.values
        lomo[te] = fit_predict(X16[tr], yv16[tr], X16[te])
    y16_masked = np.where(m16, yv16, np.nan)
    s16 = daily_scores(y16.index, y16_masked, lomo, scale)

    # 2017 live stream from the full 2016 model
    pred17 = fit_predict(X16[m16], yv16[m16], X17)
    y17_masked = np.where(m17, y17.values, np.nan)
    s17 = daily_scores(y17.index, y17_masked, pred17, scale)

    for yr, s in (("2016", s16), ("2017", s17)):
        rows.append(pd.DataFrame({"building": b, "site": site, "year": int(yr), "date": s.index, "score": s.values}))

scores = pd.concat(rows, ignore_index=True)
scores.to_csv(OUT / "e2_daily_scores.csv.gz", index=False)
pd.DataFrame(g14).to_csv(OUT / "e2_g14.csv", index=False)
stats["sites_accepted"] = int(scores["site"].nunique())
json.dump(stats, open(OUT / "e2_baseline_stats.json", "w"), indent=2)
print(json.dumps(stats, indent=1))
print(scores.groupby("year")["score"].describe())
