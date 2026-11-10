"""E2 step 2 — flag rates of four conformal calibration schemes on daily scores (alpha = 0.05).

Stream: 2017 daily scores per building (out of sample from the 2016 baseline).
Test window: 1 Mar - 31 Dec 2017, identical for every scheme.

  split       calibrate once on 2017 Jan-Feb
  mondrian    calibrate on 2016 leave-one-month-out scores from the same season (month +/- 1)
  rolling28   calibrate on the previous 28 days of the 2017 stream
  aci         rolling28 p-values with adaptive conformal inference (Gibbs & Candes 2021):
              alpha_{t+1} = alpha_t + gamma * (alpha - err_t)

p-value = (1 + #{calibration scores >= s}) / (n + 1); flag when p <= alpha (alpha_t for ACI).
The data are real and unlabelled, so a flag rate above alpha can include real events; the
comparison between schemes on the same data is the result, not the absolute level.

Usage: python3 e2_conformal.py <e2_daily_scores.csv.gz> <out_dir> [focus_site]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCORES, OUT = Path(sys.argv[1]), Path(sys.argv[2])
FOCUS = sys.argv[3] if len(sys.argv) > 3 else "Fox"
ALPHA, GAMMA, WINDOW = 0.05, 0.005, 28
TEST_START, TEST_END = pd.Timestamp("2017-03-01"), pd.Timestamp("2017-12-31")

df = pd.read_csv(SCORES, parse_dates=["date"])


def pval(cal: np.ndarray, s: float) -> float:
    return (1 + np.sum(cal >= s)) / (len(cal) + 1)


records = []
for b, g in df.groupby("building"):
    site = g["site"].iat[0]
    s16 = g[g.year == 2016].set_index("date")["score"]
    s17 = g[g.year == 2017].set_index("date")["score"].sort_index()
    split_cal = s17[(s17.index >= "2017-01-01") & (s17.index < "2017-03-01")].values
    if len(split_cal) < 40:
        continue
    by_month16 = {m: s16[s16.index.month == m].values for m in range(1, 13)}
    alpha_t = ALPHA
    hist = s17[s17.index < TEST_START]
    stream = list(zip(hist.index, hist.values))
    for d, s in s17[(s17.index >= TEST_START) & (s17.index <= TEST_END)].items():
        m = d.month
        season = np.concatenate([by_month16[((m + k - 1) % 12) + 1] for k in (-1, 0, 1)])
        roll = np.array([v for (dd, v) in stream if (d - dd).days <= WINDOW])
        p_roll = pval(roll, s) if len(roll) >= 20 else np.nan
        flag_aci = bool(p_roll <= alpha_t) if not np.isnan(p_roll) else False
        records.append({
            "building": b, "site": site, "date": d, "month": m,
            "split": pval(split_cal, s) <= ALPHA,
            "mondrian": pval(season, s) <= ALPHA if len(season) >= 40 else np.nan,
            "rolling28": (p_roll <= ALPHA) if not np.isnan(p_roll) else np.nan,
            "aci": flag_aci,
        })
        if not np.isnan(p_roll):
            alpha_t = alpha_t + GAMMA * (ALPHA - float(flag_aci))
        stream.append((d, s))

r = pd.DataFrame(records)
METHODS = ["split", "mondrian", "rolling28", "aci"]
for m in METHODS:
    r[m] = r[m].astype(float)
r.to_csv(OUT / "e2_flags.csv.gz", index=False)


def summarise(sub: pd.DataFrame) -> dict:
    per_b = sub.groupby("building")[METHODS].mean()
    monthly = sub.groupby("month")[METHODS].mean()
    out = {"buildings": int(sub.building.nunique()), "building_days": int(len(sub))}
    for m in METHODS:
        x = per_b[m].dropna()
        mo = monthly[m]
        out[m] = {
            "overall_flag_rate": round(float(sub[m].mean()), 4),
            "worst_month_rate": round(float(mo.max()), 4),
            "best_month_rate": round(float(mo.min()), 4),
            "monthly_spread_max_minus_min": round(float(mo.max() - mo.min()), 4),
            "share_buildings_over_2alpha": round(float((x > 2 * ALPHA).mean()), 4),
            "share_buildings_under_alpha_over_5": round(float((x < ALPHA / 5).mean()), 4),
            "median_building_rate": round(float(x.median()), 4),
        }
    return out


summary = {"alpha": ALPHA, "gamma": GAMMA, "window_days": WINDOW,
           "focus_site": FOCUS,
           "focus": summarise(r[r.site == FOCUS]),
           "all_sites": summarise(r)}
r[r.site == FOCUS].groupby("month")[METHODS].mean().to_csv(OUT / "e2_monthly_focus.csv")
r.groupby("month")[METHODS].mean().to_csv(OUT / "e2_monthly_all.csv")
json.dump(summary, open(OUT / "e2_summary.json", "w"), indent=2)
print(json.dumps(summary, indent=1))
print(r[r.site == FOCUS].groupby("month")[METHODS].mean().round(3))
