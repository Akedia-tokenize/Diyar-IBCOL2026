"""Validation gate. Rules first (deterministic, auditable); then the fast statistical gate:
rolling 28-day split-conformal p-value on the daily residual against the committed baseline.
The gate never decides: it emits a flag and the reasons, and the decision record is itself
committed, so a verification event can be replayed (whitepaper IV, 'Ledger').
"""
import numpy as np

from .crypto import H, canonical

ALPHA, WINDOW, MIN_CAL, MIN_HOURS = 0.05, 28, 20, 22


def _hour_ok(h, day):
    """'YYYY-MM-DDTHH:00' on the given day, hour 00-23."""
    if not (isinstance(h, str) and len(h) == 16 and h[10] == "T" and h.endswith(":00")):
        return False
    if day is not None and h[:10] != day:
        return False
    return h[11:13].isdigit() and 0 <= int(h[11:13]) <= 23


def rules(readings, max_hourly, day=None):
    """Coverage counts DISTINCT valid hours of the day, never the number of rows: a repeated
    or out-of-period timestamp is not evidence of an hour (audit 2 Nov, P0-06)."""
    hours = [r["h"] for r in readings]
    valid = {h for h in hours if _hour_ok(h, day)}
    duplicates = len(hours) - len(set(hours))
    out_of_period = sum(1 for h in set(hours) if not _hour_ok(h, day))
    plausible = all(isinstance(r["v"], (int, float)) and 0 <= r["v"] <= max_hourly for r in readings)
    reasons = ([f"duplicate_interval x{duplicates}"] if duplicates else []) + \
              ([f"out_of_period x{out_of_period}"] if out_of_period else []) + \
              ([f"insufficient_coverage {len(valid)}/24"] if len(valid) < MIN_HOURS else []) + \
              ([] if plausible else ["implausible_value"])
    return {
        "coverage_ok": len(valid) >= MIN_HOURS and duplicates == 0 and out_of_period == 0,
        "hours_present": len(valid),
        "duplicate_readings": duplicates,
        "plausible_ok": plausible,
        "reasons": reasons,
    }


def score(actual_sum, pred_sum, scale):
    return abs(actual_sum - pred_sum) / scale


def conformal_p(cal_scores, s):
    cal = np.asarray(cal_scores, dtype=float)
    return float((1 + np.sum(cal >= s)) / (len(cal) + 1))


def decide(rule_res, s, cal_scores, model_ver):
    cal_ver = H(canonical([round(c, 8) for c in cal_scores])).hex()[:16]
    if not (rule_res["coverage_ok"] and rule_res["plausible_ok"]):
        return {"flag": True, "reason": "rule", "rules": rule_res, "score": None, "p": None,
                "alpha": ALPHA, "model_ver": model_ver, "calibration_ver": cal_ver}
    if len(cal_scores) < MIN_CAL:
        return {"flag": False, "reason": "calibrating", "rules": rule_res, "score": round(s, 6), "p": None,
                "alpha": ALPHA, "model_ver": model_ver, "calibration_ver": cal_ver}
    p = conformal_p(cal_scores, s)
    return {"flag": p <= ALPHA, "reason": "conformal" if p <= ALPHA else "pass", "rules": rule_res,
            "score": round(s, 6), "p": round(p, 6), "alpha": ALPHA, "model_ver": model_ver,
            "calibration_ver": cal_ver}
