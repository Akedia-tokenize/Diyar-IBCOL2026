"""E3a extension (6 Nov 2026): one-sided quarterly power at intermediate under-report sizes.

Same test, data and protocol as src/e3a_quarterly.py (alpha 5%, 90-day horizon, one manipulated
building, onset uniform on days 90..243, committed Q1 2017 reference, rank against same-site peers);
only the sizes and the seed differ. Usage: python3 -I e3a_extra.py <e3_fox_daily.npz> <out.json>
"""
import json
import sys

import numpy as np

D = np.load(sys.argv[1], allow_pickle=True)
ALPHA, REPS, H = 0.05, 1000, 90
ONSET_LO, ONSET_HI, Q1 = 90, 243, slice(0, 90)
SIZES = [0.20, 0.225, 0.25, 0.275, 0.30]
rng = np.random.default_rng(20261106)
A, P, SC = D["actual17"], D["pred17"], D["scale"][:, None]
B, T = A.shape


def test(Am, tau):
    R = (Am - P) / SC
    delta = np.nanmean(R[:, tau - H:tau], axis=1) - np.nanmean(R[:, Q1], axis=1)
    ok = ~np.isnan(delta)
    n = ok.sum()
    one = np.full(B, np.nan)
    d = delta[ok]
    one[ok] = (1 + (d[None, :] <= d[:, None]).sum(1) - 1) / n
    return one <= ALPHA


rows = []
for s in SIZES:
    hit, fp = [], []
    for _ in range(REPS):
        inj = rng.choice(B, size=1, replace=False)
        t0 = int(rng.integers(ONSET_LO, ONSET_HI + 1))
        tau = min(T, t0 + H)
        Am = A.copy()
        Am[inj[0], t0:] = A[inj[0], t0:] * (1 - s)
        f = test(Am, tau)
        clean = np.setdiff1d(np.arange(B), inj)
        hit.append(f[inj].mean()); fp.append(f[clean].mean())
    p = float(np.mean(hit))
    se = (p * (1 - p) / REPS) ** 0.5
    rows.append({"size": s, "power_one_sided": round(p, 3), "mc_se": round(se, 3),
                 "false_flag_one_sided": round(float(np.mean(fp)), 3)})
    print(rows[-1], flush=True)
json.dump({"rows": rows, "params": {"alpha": ALPHA, "reps": REPS, "period_days": H, "buildings": int(B),
           "seed": 20261106, "input": "e3_fox_daily.npz (rebuilt by src/e3_prepare.py from the 3 BDG2 files in data_manifest.sha256)"}}, open(sys.argv[2], "w"), indent=1)
