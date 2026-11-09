"""E3b — the three modes the adjudicator called 'statistical, not ML', on monthly entries
(bill-upload and manual-entry paths), using real 2016/2017 monthly totals at one site.

1. Copy of a prior period
   exact copy  : 2017 entries = 2016 entries            -> rule: equality with prior entries
   near copy   : 2017 entries = 2016 entries x (1 + e), e ~ N(0, 1%)
                 statistic: median_m |x17_m / x16_m - 1| (small = suspicious);
                 one-sided conformal against clean peers.
2. Optimistic rounding
   honest entry: integer kWh. optimistic: floor to 2 significant figures.
   rounding test: number of the 12 entries with >= 3 trailing zeros; flag if >= 6.
   also report the bias rounding introduces, against the site's natural quarter drift.
3. Selective deletion of the worst month (11 of 12 kept, so a 90% coverage rule passes)
   question: is the deleted month identifiable from what remains? We check how often the
   worst-residual month is simply the hottest month (weather-explainable) vs anything else.

Usage: python3 e3b_statistical.py <e3_fox_daily.npz> <e3a_quarterly.json> <out_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

D = np.load(sys.argv[1], allow_pickle=True)
noise = json.load(open(sys.argv[2]))["noise_floor"]
OUT = Path(sys.argv[3])
ALPHA, REPS = 0.05, 1000
rng = np.random.default_rng(20261029)

d16 = pd.date_range("2016-01-01", "2016-12-31")
d17 = pd.date_range("2017-01-01", "2017-12-31")


def monthly(M, days):
    df = pd.DataFrame(M.T, index=days)
    cnt = df.notna().groupby(df.index.month).sum()
    tot = df.groupby(df.index.month).sum(min_count=1)
    days_in = df.index.to_series().groupby(df.index.month).count()
    return (tot / cnt * days_in.values[:, None]).T.values        # scale up for a few missing days


M16, M17, P17 = monthly(D["actual16"], d16), monthly(D["actual17"], d17), monthly(D["pred17"], d17)
ok = ~np.isnan(M16).any(1) & ~np.isnan(M17).any(1)
M16, M17, P17 = M16[ok], M17[ok], P17[ok]
B = len(M16)
T17 = pd.Series(D["temp17"], index=d17).groupby(d17.month).mean().values

# 1. copy ----------------------------------------------------------------------------
clean_stat = np.median(np.abs(M17 / M16 - 1), axis=1)
exact_fp = float(np.mean(np.any(np.isclose(np.round(M17), np.round(M16), rtol=0, atol=0.5), axis=1)))
near_hits, near_fp = [], []
for _ in range(REPS):
    b = rng.integers(B)
    fake = M16[b] * (1 + rng.normal(0, 0.01, 12))
    stat = clean_stat.copy(); stat[b] = np.median(np.abs(fake / M16[b] - 1))
    p = (1 + (stat[None, :] <= stat[:, None]).sum(1) - 1) / B
    near_hits.append(p[b] <= ALPHA)
    near_fp.append(np.mean(np.delete(p, b) <= ALPHA))
copy = {"exact_copy_detected_by_rule": 1.0, "exact_copy_false_match_rate_clean": round(exact_fp, 4),
        "near_copy_power": round(float(np.mean(near_hits)), 3), "near_copy_false_flag": round(float(np.mean(near_fp)), 3),
        "clean_median_month_on_month_change": round(float(np.median(clean_stat)), 3)}


# 2. rounding ------------------------------------------------------------------------
def trailing_zero3(x):
    return (np.round(x).astype(np.int64) % 1000) == 0


def floor2sig(x):
    mag = 10 ** (np.floor(np.log10(x)) - 1)
    return np.floor(x / mag) * mag


honest = np.round(M17)
rounded = floor2sig(M17)
hz = trailing_zero3(honest).sum(1)
rz = trailing_zero3(rounded).sum(1)
bias = (rounded.sum(1) / M17.sum(1) - 1)
rounding = {"rounding_detected": round(float(np.mean(rz >= 6)), 3),
            "honest_flagged": round(float(np.mean(hz >= 6)), 4),
            "optimistic_bias_mean": round(float(bias.mean()), 4),
            "optimistic_bias_worst": round(float(bias.min()), 4),
            "natural_quarter_drift_sd": noise["clean_quarter_drift_sd"]}

# 3. selective deletion --------------------------------------------------------------
resid = (M17 - P17) / P17
worst = np.argmax(resid, axis=1)
hottest = int(np.argmax(T17))
top3_hot = set(np.argsort(T17)[-3:])
deletion = {"buildings": int(B),
            "worst_month_is_hottest": round(float(np.mean(worst == hottest)), 3),
            "worst_month_in_three_hottest": round(float(np.mean([w in top3_hot for w in worst])), 3),
            "chance_level_single": round(1 / 12, 3), "chance_level_three": 0.25,
            "worst_month_distribution": {int(m + 1): int(c) for m, c in zip(*np.unique(worst, return_counts=True))}}

out = {"copy": copy, "rounding": rounding, "selective_deletion": deletion, "params": {"alpha": ALPHA, "reps": REPS}}
json.dump(out, open(OUT / "e3b_results.json", "w"), indent=1)
print(json.dumps(out, indent=1))
