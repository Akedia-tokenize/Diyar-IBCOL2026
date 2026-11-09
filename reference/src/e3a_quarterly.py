"""E3a (part 2) — the slow gate as one test per period: minimum detectable manipulation.

At test time tau = onset + 90 days, every building's drift is
    delta_b = mean r over (tau-90, tau]  -  mean r over Q1 2017 (the committed reference period),
with r the signed daily residual against the frozen 2016 baseline (fraction of mean daily use).
The calibration set is the peer population at the same tau (same weather, same model vintage).
  one-sided (under-reporting, the direction a green claim is pushed):
      p = (1 + #{peers j : delta_j <= delta_b}) / n
  two-sided: rank of |delta_b - median|.
Flag when p <= alpha. Power = share of manipulated buildings flagged; false-flag rate = share
of clean buildings flagged at the same tau. Shave and relocation, sizes 2.5% to 40%.

Usage: python3 e3a_quarterly.py <e3_fox_daily.npz> <out_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np

D = np.load(sys.argv[1], allow_pickle=True)
OUT = Path(sys.argv[2])
ALPHA, REPS, H = 0.05, 1000, 90
PREVALENCE = [0.01, 0.05, 0.10, 0.20]
ONSET_LO, ONSET_HI, Q1 = 90, 243, slice(0, 90)
SIZES = [0.025, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
rng = np.random.default_rng(20261028)

A, P, SC = D["actual17"], D["pred17"], D["scale"][:, None]
B, T = A.shape


def test(Am, tau):
    R = (Am - P) / SC
    delta = np.nanmean(R[:, tau - H:tau], axis=1) - np.nanmean(R[:, Q1], axis=1)
    ok = ~np.isnan(delta)
    n = ok.sum()
    one = np.full(B, np.nan); two = np.full(B, np.nan)
    d = delta[ok]
    one[ok] = (1 + (d[None, :] <= d[:, None]).sum(1) - 1) / n
    dev = np.abs(d - np.median(d))
    two[ok] = (1 + (dev[None, :] >= dev[:, None]).sum(1) - 1) / n
    return one <= ALPHA, two <= ALPHA, delta


rows = []
def run(kind, s, n_inj, reps):
        hit1, hit2, fp1, fp2 = [], [], [], []
        for _ in range(reps):
            inj = rng.choice(B, size=n_inj, replace=False)
            t0 = int(rng.integers(ONSET_LO, ONSET_HI + 1))          # common onset -> common test date
            tau = min(T, t0 + H)
            Am = A.copy()
            for b in inj:
                if kind == "shave":
                    Am[b, t0:] = A[b, t0:] * (1 - s)
                else:
                    donor = rng.choice(np.setdiff1d(np.arange(B), inj))
                    pre = slice(t0 - 28, t0)
                    k = (1 - s) * np.nanmean(A[b, pre]) / np.nanmean(A[donor, pre])
                    Am[b, t0:] = A[donor, t0:] * k
            f1, f2, _ = test(Am, tau)
            clean = np.setdiff1d(np.arange(B), inj)
            hit1.append(f1[inj].mean()); hit2.append(f2[inj].mean())
            fp1.append(f1[clean].mean()); fp2.append(f2[clean].mean())
        return {"manipulation": kind, "size": s, "manipulated_buildings": n_inj,
                "power_one_sided": round(float(np.mean(hit1)), 3),
                "power_two_sided": round(float(np.mean(hit2)), 3),
                "false_flag_one_sided": round(float(np.mean(fp1)), 3),
                "false_flag_two_sided": round(float(np.mean(fp2)), 3)}


for kind in ("shave", "relocate"):
    for s in SIZES:
        rows.append(run(kind, s, 1, REPS)); print(rows[-1], flush=True)
prev = []
for pr in PREVALENCE:
    prev.append(dict(run("shave", 0.20, max(1, int(round(pr * B))), 300), prevalence=pr)); print(prev[-1], flush=True)

_, _, d0 = test(A, 270)
noise = {"clean_quarter_drift_sd": round(float(np.nanstd(d0)), 4),
         "clean_quarter_drift_p5": round(float(np.nanpercentile(d0, 5)), 4),
         "clean_quarter_drift_median": round(float(np.nanmedian(d0)), 4)}
json.dump({"noise_floor": noise, "power_single_building": rows, "prevalence_sweep_shave20": prev,
           "params": {"alpha": ALPHA, "reps": REPS, "period_days": H, "buildings": B}},
          open(OUT / "e3a_quarterly.json", "w"), indent=1)
print(noise)
