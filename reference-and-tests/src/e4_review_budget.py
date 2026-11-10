"""E4 — review budget: what each gate setting costs in human review, and what it buys in detection.

Input: the Fox daily matrices built by e3_prepare.py (same 106 buildings, same frozen 2016 baselines).
Signed daily residual r = (actual - frozen 2016 baseline prediction) / 2016 mean daily use.

Part A — slow quarterly gate (the gate the paper budgets review on).
  The test is exactly the one in e3a_quarterly.py: at tau = onset + 90 days,
      delta_b = mean r over (tau-90, tau] - mean r over Q1 2017 (the committed reference period),
      one-sided p_b = #{peers j : delta_j <= delta_b} / n   (rank of b among the n buildings, b included).
  The simulation replays e3a_quarterly.py draw for draw (same seed, same order), so at alpha = 5% the
  powers equal Table IV-a exactly; other alphas are read off the same p-values.
  Review load. The test flags the buildings whose rank is <= alpha * n, so every quarterly test opens
  floor(alpha * n) cases per peer group whether or not anyone manipulates. Two numbers are reported:
    cases_per_building_year      = 4 x (cases opened / n), on clean data at the three 2017 quarter ends
                                    (30 Jun, 30 Sep, 31 Dec). This is the review workload.
    false_alarms_per_building_year = 4 x (share of honest buildings flagged) in the runs with one manipulated
                                    building (20% shave). Honest buildings only, so it is lower whenever the
                                    manipulated building takes one of the floor(alpha * n) slots.

Part B — fast daily gate used as a human-review trigger (to show why it should only raise a watch status).
  Rolling W-day split-conformal p-value on |r| over the building's own previous W days (2017 stream),
  p = (1 + #{window scores >= s}) / (n + 1), flag when p <= alpha, no flag while the window holds < 20 days.
  A case opens on day t when the 7 days ending at t hold >= 3 flags and no case opened in the previous 6 days.
  Scored from 1 Apr 2017 (day 90) to 31 Dec 2017.
    cases_per_building_year on clean data;
    burst_opened_within_7_days: a 20% under-report lasting 7 days, onset uniform in [1 Apr, 1 Sep], one
    building per repetition; share of repetitions in which a case opens during the burst week.

Usage: python3 e4_review_budget.py <e3_fox_daily.npz> <out_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

D = np.load(sys.argv[1], allow_pickle=True)
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

A, P, SC = D["actual17"], D["pred17"], D["scale"][:, None]
B, T = A.shape
H, REPS = 90, 1000
ONSET_LO, ONSET_HI, Q1 = 90, 243, slice(0, 90)
SIZES = [0.025, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
PREVALENCE = [0.01, 0.05, 0.10, 0.20]
ALPHAS = [0.01, 0.02, 0.05, 0.10]


# ---------------- Part A: slow quarterly gate ----------------
def deltas(Am, tau):
    R = (Am - P) / SC
    return np.nanmean(R[:, tau - H:tau], axis=1) - np.nanmean(R[:, Q1], axis=1)


def one_sided_p(delta):
    ok = ~np.isnan(delta)
    n = int(ok.sum())
    p = np.full(B, np.nan)
    d = delta[ok]
    p[ok] = (d[None, :] <= d[:, None]).sum(1) / n
    return p, n


rng = np.random.default_rng(20261028)          # the seed of e3a_quarterly.py


def run(kind, s, n_inj, reps):
    hit = {a: [] for a in ALPHAS}
    fa = {a: [] for a in ALPHAS}
    for _ in range(reps):
        inj = rng.choice(B, size=n_inj, replace=False)
        t0 = int(rng.integers(ONSET_LO, ONSET_HI + 1))
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
        p, _ = one_sided_p(deltas(Am, tau))
        clean = np.setdiff1d(np.arange(B), inj)
        for a in ALPHAS:
            f = p <= a
            hit[a].append(f[inj].mean())
            fa[a].append(f[clean].mean())
    return {"manipulation": kind, "size": s, "manipulated_buildings": int(n_inj),
            "power_one_sided": {f"{a:.2f}": round(float(np.mean(hit[a])), 3) for a in ALPHAS},
            "false_flag_honest": {f"{a:.2f}": round(float(np.mean(fa[a])), 4) for a in ALPHAS}}


rows = []
for kind in ("shave", "relocate"):
    for s in SIZES:
        rows.append(run(kind, s, 1, REPS))
        print(kind, s, rows[-1]["power_one_sided"], flush=True)
prev = []
for pr in PREVALENCE:
    prev.append(dict(run("shave", 0.20, max(1, int(round(pr * B))), 300), prevalence=pr))

QUARTER_ENDS = [181, 273, 365]               # tau (exclusive end index) for 30 Jun, 30 Sep, 31 Dec 2017
caseload = {}
for a in ALPHAS:
    shares, ns = [], []
    for tau in QUARTER_ENDS:
        p, n = one_sided_p(deltas(A, min(T, tau)))
        shares.append(float(np.nansum(p <= a)) / n)
        ns.append(n)
    caseload[f"{a:.2f}"] = {"cases_per_test": [int(round(x * n)) for x, n in zip(shares, ns)], "peers": ns,
                            "cases_per_building_year": round(4 * float(np.mean(shares)), 4)}
shave20 = next(r for r in rows if r["manipulation"] == "shave" and r["size"] == 0.20)
slow_table = []
for a in ALPHAS:
    k = f"{a:.2f}"
    p20 = next(r for r in rows if r["manipulation"] == "shave" and r["size"] == 0.20)["power_one_sided"][k]
    p30 = next(r for r in rows if r["manipulation"] == "shave" and r["size"] == 0.30)["power_one_sided"][k]
    slow_table.append({"alpha": a, "cases_per_building_year": caseload[k]["cases_per_building_year"],
                       "false_alarms_per_building_year": round(4 * shave20["false_flag_honest"][k], 4),
                       "power_shave20": p20, "power_shave30": p30})

# ---------------- Part B: fast daily gate as a review trigger ----------------
R0 = (A - P) / SC
START = 90


def fast_flags(R, W, alpha, minw=20):
    S = np.abs(R)
    pad = np.concatenate([np.full((R.shape[0], W), np.nan), S], axis=1)
    win = sliding_window_view(pad, W, axis=1)[:, :T, :]
    n = np.sum(~np.isnan(win), axis=2)
    ge = np.sum(win >= S[:, :, None], axis=2)
    p = (1 + ge) / (n + 1)
    flag = (p <= alpha).astype(float)
    flag[(n < minw) | np.isnan(S)] = 0.0
    return flag


def open_cases(flag):
    """case opens at t when the 7 days ending at t hold >= 3 flags and none opened in the previous 6 days"""
    Bn = flag.shape[0]
    cases = np.zeros_like(flag, dtype=bool)
    csum = np.concatenate([np.zeros((Bn, 1)), np.cumsum(flag, axis=1)], axis=1)
    last = np.full(Bn, -10**6)
    for t in range(START, T):
        win7 = csum[:, t + 1] - csum[:, max(0, t - 6)]
        o = (win7 >= 3) & (t - last > 6)
        cases[o, t] = True
        last[o] = t
    return cases


brng = np.random.default_rng(20261029)
fast_table = []
for W, a in [(28, 0.05), (56, 0.05), (56, 0.02), (112, 0.05), (112, 0.02), (112, 0.01)]:
    F0 = fast_flags(R0, W, a)
    C0 = open_cases(F0)
    valid = ~np.isnan(R0[:, START:])
    rate = C0[:, START:].sum() / valid.sum() * 365
    opened = []
    for _ in range(REPS):
        b = int(brng.integers(0, B)); t0 = int(brng.integers(ONSET_LO, ONSET_HI + 1))
        Ab = A[b:b + 1].copy(); Ab[0, t0:t0 + 7] *= 0.8
        Rb = (Ab - P[b:b + 1]) / SC[b:b + 1]
        Cb = open_cases(fast_flags(Rb, W, a))
        opened.append(bool(Cb[0, t0:t0 + 7].any()))
    fast_table.append({"window_days": W, "alpha": a, "cases_per_building_year": round(float(rate), 3),
                       "burst20_opened_within_7_days": round(float(np.mean(opened)), 3),
                       "clean_flag_rate": round(float(F0[:, START:][valid].mean()), 4)})
    print(fast_table[-1], flush=True)

json.dump({"slow_quarterly_gate": slow_table, "caseload_detail": caseload,
           "power_single_building": rows, "prevalence_sweep_shave20": prev,
           "fast_gate_as_review": fast_table,
           "params": {"reps": REPS, "period_days": H, "buildings": B, "seed_slow": 20261028, "seed_fast": 20261029,
                      "quarter_end_tau": QUARTER_ENDS}},
          open(OUT / "e4_results.json", "w"), indent=1)
print(json.dumps(slow_table, indent=1))
