"""Out-of-time check of the committed baselines (audit 2 Nov 2026, P0-03).

ASHRAE Guideline 14 acceptance (CV(RMSE), NMBE) is computed on the 2016 data each baseline was
fitted on, so in-sample NMBE is ~0 by construction. This script scores the SAME frozen 2016
baselines on 2017, a year they never saw, at daily resolution, for the 106 Fox buildings used in
E2-E4.

Input : e3_fox_daily.npz from e3_prepare.py (actual17, pred17 = frozen-2016-baseline prediction)
Output: e2_out_of_time.json
Usage : python3 -I src/e2_out_of_time.py <e3_fox_daily.npz> <out_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np

D = np.load(sys.argv[1], allow_pickle=True)
OUT = Path(sys.argv[2])
A, P = D["actual17"], D["pred17"]
cv, nmbe, days = [], [], []
for a, p in zip(A, P):
    ok = ~np.isnan(a) & ~np.isnan(p)
    a, p = a[ok], p[ok]
    m = a.mean()
    cv.append(float(np.sqrt(np.mean((a - p) ** 2)) / m))
    nmbe.append(float((a - p).sum() / (len(a) * m)))
    days.append(int(ok.sum()))
cv, nmbe = np.array(cv), np.array(nmbe)
res = {
    "buildings": int(len(cv)), "resolution": "daily", "year": 2017, "baseline_fitted_on": 2016,
    "cv_rmse": {"median": round(float(np.median(cv)), 4), "p25": round(float(np.percentile(cv, 25)), 4),
                "p75": round(float(np.percentile(cv, 75)), 4), "max": round(float(cv.max()), 4)},
    "nmbe": {"median": round(float(np.median(nmbe)), 4), "p25": round(float(np.percentile(nmbe, 25)), 4),
             "p75": round(float(np.percentile(nmbe, 75)), 4)},
    "share_abs_nmbe_le_10pct": round(float(np.mean(np.abs(nmbe) <= 0.10)), 3),
    "share_cv_le_30pct": round(float(np.mean(cv <= 0.30)), 3),
    "note": "Daily aggregation; G14 hourly thresholds (CV 30%, NMBE 10%) are quoted for orientation only.",
}
json.dump(res, open(OUT / "e2_out_of_time.json", "w"), indent=1)
print(json.dumps(res, indent=1))
