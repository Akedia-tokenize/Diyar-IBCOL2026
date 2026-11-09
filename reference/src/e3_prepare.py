"""E3 data preparation: daily matrices for one site, from the same baseline as E2.

For every building at the site that passes ASHRAE Guideline 14 on its 2016 fit:
  actual daily kWh 2016 and 2017, frozen-baseline predicted daily kWh 2017 (2016 model),
  daily mean temperature, and the 2016 mean daily consumption used as scale.
A day counts only if it has >= 22 valid hours; otherwise it is NaN (BDG2's own gaps).

Usage: python3 e3_prepare.py <bdg2_root> <site> <out.npz>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BDG2, SITE, OUT = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
KNOTS_C = (np.array([30, 45, 55, 65, 75, 90], dtype=float) - 32) * 5 / 9

elec = pd.read_csv(BDG2 / "data/meters/cleaned/electricity_cleaned.csv", parse_dates=["timestamp"]).set_index("timestamp")
meta = pd.read_csv(BDG2 / "data/metadata/metadata.csv").set_index("building_id")
wx = pd.read_csv(BDG2 / "data/weather/weather.csv", parse_dates=["timestamp"])
t_site = (wx[wx.site_id == SITE].set_index("timestamp")["airTemperature"]
          .reindex(elec.index).interpolate(limit=6, limit_direction="both"))


def design(idx, t):
    how = idx.dayofweek * 24 + idx.hour
    X = np.zeros((len(idx), 168))
    X[np.arange(len(idx)), how] = 1.0
    cols = [np.minimum(t, KNOTS_C[0])]
    cols += [np.clip(t, lo, hi) - lo for lo, hi in zip(KNOTS_C[:-1], KNOTS_C[1:])]
    cols.append(np.maximum(t - KNOTS_C[-1], 0))
    return np.hstack([X, np.column_stack(cols)])


def daily(idx, v, valid):
    s = pd.Series(np.where(valid, v, np.nan), index=idx)
    g = s.groupby(s.index.normalize())
    out = g.sum(min_count=1)
    out[g.count() < 22] = np.nan
    return out


buildings = [b for b in elec.columns if b in meta.index and meta.at[b, "site_id"] == SITE]
days16 = pd.date_range("2016-01-01", "2016-12-31")
days17 = pd.date_range("2017-01-01", "2017-12-31")
keep, A16, A17, P17, SC = [], [], [], [], []
for b in buildings:
    y16, y17 = elec.loc["2016", b], elec.loc["2017", b]
    t16, t17 = t_site.loc["2016"], t_site.loc["2017"]
    m16 = (y16.notna() & t16.notna() & (y16 > 0)).values
    m17 = (y17.notna() & t17.notna() & (y17 > 0)).values
    if m16.mean() < 0.9 or m17.mean() < 0.9:
        continue
    X16, X17 = design(y16.index, t16.values), design(y17.index, t17.values)
    beta, *_ = np.linalg.lstsq(X16[m16], y16.values[m16], rcond=None)
    res = y16.values[m16] - X16[m16] @ beta
    n, p = int(m16.sum()), X16.shape[1]
    mu = y16.values[m16].mean()
    cv, nmbe = np.sqrt((res ** 2).sum() / (n - p)) / mu, res.sum() / ((n - p) * mu)
    if cv > 0.30 or abs(nmbe) > 0.10:
        continue
    keep.append(b)
    A16.append(daily(y16.index, y16.values, m16).reindex(days16).values)
    A17.append(daily(y17.index, y17.values, m17).reindex(days17).values)
    P17.append(daily(y17.index, X17 @ beta, m17).reindex(days17).values)
    SC.append(mu * 24)

temp17 = t_site.loc["2017"].groupby(t_site.loc["2017"].index.normalize()).mean().reindex(days17).values
temp16 = t_site.loc["2016"].groupby(t_site.loc["2016"].index.normalize()).mean().reindex(days16).values
np.savez_compressed(OUT, buildings=np.array(keep), actual16=np.array(A16), actual17=np.array(A17),
                    pred17=np.array(P17), scale=np.array(SC), temp16=temp16, temp17=temp17,
                    days17=days17.strftime("%Y-%m-%d").values)
print(SITE, "buildings kept:", len(keep), "missing day share 2017:",
      round(float(np.isnan(np.array(A17)).mean()), 4))
