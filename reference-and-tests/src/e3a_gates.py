"""E3a — fast gate vs slow gate on injected manipulations at one site (alpha = 0.05).

Signed daily residual r = (actual - frozen 2016 baseline prediction) / 2016 mean daily use.

Fast gate (E2's best calibrated scheme): rolling 28-day split-conformal p-value on |r|.
  The live stream feeds its own calibration window.
Slow gate (proposed): drift against the committed, frozen baseline, judged against peers.
  D_b(t) = mean of r over the last 28 days; z_b(t) = (D_b(t) - median_peers(t)) / sigma_b,
  sigma_b = std of daily r in Jan-Feb 2017 (before any onset).
  p = (1 + #{peers j : |z_j| >= |z_b|}) / n_t.  Calibration set = the peer population on the
  same day, so no history of the manipulated building enters it.

Manipulations, injected into one building per repetition, onset uniform in [1 Apr, 1 Sep] 2017:
  shave     persistent under-reporting: actual * (1 - s) from onset to year end
  burst     same, but only for 7 days
  relocate  from onset the signed meter reads another building's load, rescaled so its
            mean over the 28 days before onset is (1 - s) x the target's mean
Sizes s in {5%, 10%, 20%}; 300 repetitions per scenario.

Metric: per-day sensitivity (share of manipulated building-days flagged in the first 90 days
after onset; first 7 days for burst) against the per-day false-flag rate on clean buildings
in the same runs. Also the flag rate by day since onset (absorption curve).

Usage: python3 e3a_gates.py <e3_fox_daily.npz> <out_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

D = np.load(sys.argv[1], allow_pickle=True)
OUT = Path(sys.argv[2])
ALPHA, W, MINW, H = 0.05, 28, 20, 90
REPS, FRAC = 300, 0.0
rng = np.random.default_rng(20261027)

A, P, SC = D["actual17"], D["pred17"], D["scale"][:, None]
B, T = A.shape
days = np.array(D["days17"], dtype="datetime64[D]")
doy = (days - np.datetime64("2017-01-01")).astype(int)
ONSET_LO = 90   # 1 Apr 2017 (day index)
ONSET_HI = 243  # 1 Sep 2017 (day index)
JF = doy < 59


def fast_gate(R: np.ndarray) -> np.ndarray:
    """Rolling 28-day conformal flags on |r|; NaN where the window is too thin."""
    S = np.abs(R)
    pad = np.concatenate([np.full((R.shape[0], W), np.nan), S], axis=1)
    win = sliding_window_view(pad, W, axis=1)[:, :T, :]            # previous 28 days for day t
    n = np.sum(~np.isnan(win), axis=2)
    ge = np.sum(win >= S[:, :, None], axis=2)
    p = (1 + ge) / (n + 1)
    flag = (p <= ALPHA).astype(float)
    flag[(n < MINW) | np.isnan(S)] = np.nan
    return flag


def slow_gate(R: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    win = sliding_window_view(np.concatenate([np.full((R.shape[0], W - 1), np.nan), R], axis=1), W, axis=1)
    cnt = np.sum(~np.isnan(win), axis=2)
    Dm = np.where(cnt >= MINW, np.nanmean(np.where(np.isnan(win), np.nan, win), axis=2), np.nan)
    med = np.nanmedian(Dm, axis=0)
    Z = np.abs((Dm - med) / sigma[:, None])
    flag = np.full_like(Z, np.nan)
    for t in range(T):
        z = Z[:, t]
        ok = ~np.isnan(z)
        n = ok.sum()
        if n < 30:
            continue
        zz = z[ok]
        ge = (zz[None, :] >= zz[:, None]).sum(axis=1) - 1          # peers at least as extreme
        flag[ok, t] = ((1 + ge) / n <= ALPHA).astype(float)
    return flag


def residuals(Aobs):
    return (Aobs - P) / SC


R0 = residuals(A)
sigma = np.nanstd(R0[:, JF], axis=1)
F0, S0 = fast_gate(R0), slow_gate(R0, sigma)

scenarios = [(k, s) for k in ("shave", "burst", "relocate") for s in (0.05, 0.10, 0.20)]
results, curves = [], {}
for kind, s in scenarios:
    sens_f, sens_s, sens_e, fp_f, fp_s, fp_e = [], [], [], [], [], []
    curve_f, curve_s = np.zeros(H), np.zeros(H)
    curve_n = np.zeros(H)
    for rep in range(REPS):
        inj = rng.choice(B, size=max(1, int(round(FRAC * B))), replace=False)
        onsets = rng.integers(ONSET_LO, ONSET_HI + 1, size=len(inj))
        Am = A.copy()
        for b, t0 in zip(inj, onsets):
            end = t0 + 7 if kind == "burst" else T
            if kind in ("shave", "burst"):
                Am[b, t0:end] = A[b, t0:end] * (1 - s)
            else:
                donor = rng.choice(np.setdiff1d(np.arange(B), inj))
                pre = slice(max(0, t0 - 28), t0)
                k = (1 - s) * np.nanmean(A[b, pre]) / np.nanmean(A[donor, pre])
                Am[b, t0:] = A[donor, t0:] * k
        R = residuals(Am)
        F, S = fast_gate(R), slow_gate(R, sigma)
        clean = np.setdiff1d(np.arange(B), inj)
        horizon = 7 if kind == "burst" else H
        mf, ms, me = [], [], []
        for b, t0 in zip(inj, onsets):
            sl = slice(t0, min(T, t0 + horizon))
            f, sg = F[b, sl], S[b, sl]
            mf.append(np.nanmean(f)); ms.append(np.nanmean(sg))
            me.append(np.nanmean(np.fmax(f, sg)))
            k_end = min(H, T - t0)
            curve_f[:k_end] += np.nan_to_num(F[b, t0:t0 + k_end])
            curve_s[:k_end] += np.nan_to_num(S[b, t0:t0 + k_end])
            curve_n[:k_end] += 1
        window = (doy >= ONSET_LO) & (doy < min(T, ONSET_HI + horizon))
        fp_f.append(np.nanmean(F[clean][:, window])); fp_s.append(np.nanmean(S[clean][:, window]))
        fp_e.append(np.nanmean(np.fmax(F[clean][:, window], S[clean][:, window])))
        sens_f.append(np.mean(mf)); sens_s.append(np.mean(ms)); sens_e.append(np.mean(me))
    results.append({
        "manipulation": kind, "size": s, "days_scored": 7 if kind == "burst" else H,
        "sens_fast": round(float(np.mean(sens_f)), 3), "sens_slow": round(float(np.mean(sens_s)), 3),
        "sens_either": round(float(np.mean(sens_e)), 3),
        "fp_fast": round(float(np.mean(fp_f)), 3), "fp_slow": round(float(np.mean(fp_s)), 3),
        "fp_either": round(float(np.mean(fp_e)), 3),
    })
    curves[f"{kind}_{int(s * 100)}"] = {"fast": (curve_f / curve_n).round(4).tolist(),
                                       "slow": (curve_s / curve_n).round(4).tolist()}
    print(results[-1], flush=True)

base = {"clean_fast_rate": round(float(np.nanmean(F0[:, doy >= ONSET_LO])), 4),
        "clean_slow_rate": round(float(np.nanmean(S0[:, doy >= ONSET_LO])), 4),
        "slow_flags_concentration_top10pct_buildings": None}
per_b = np.nanmean(S0[:, doy >= ONSET_LO], axis=1)
top = np.sort(per_b)[::-1][: max(1, B // 10)]
base["slow_flags_concentration_top10pct_buildings"] = round(float(top.sum() / per_b.sum()), 3)
base["slow_buildings_never_flagged"] = round(float((per_b == 0).mean()), 3)
json.dump({"clean": base, "scenarios": results, "curves": curves,
           "params": {"alpha": ALPHA, "window": W, "horizon": H, "reps": REPS, "fraction": FRAC, "buildings": B}},
          open(OUT / "e3a_results.json", "w"), indent=1)
print(json.dumps(base))
