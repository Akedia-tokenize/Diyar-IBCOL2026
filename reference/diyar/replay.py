"""Independent replay. Reads ONLY the published artefacts (records, ledger, public keys,
parameters) and the reference code; never the operator's running state. A replay that runs
only on the operator's server is not replay (whitepaper VII).

replay(period, as_of=T) answers 'what number did the system produce, with what it knew at T'.
replay(period)          answers 'what is the number with everything known now'.
Both are correct; they differ exactly by the corrections committed after T.
"""
import calendar
import json
from pathlib import Path

import numpy as np

from . import baseline as bl
from . import binding, trust
from .crypto import OUTPUT, H, canonical, ec_verify
from .intake import FEED_V2, pinned_issuer_key, reading_msg, verify_authoritative_v2
from .ledger import verify_chain
from .records import RESIDUAL, Store, record_hash, weakest
from .smt import SMT


def load(out_dir: Path):
    out_dir = Path(out_dir)
    return {
        "store": Store.load(out_dir / "records.jsonl"),
        "ledger": json.load(open(out_dir / "ledger.json")),
        "keys": json.load(open(out_dir / "public_keys.json")),
        "params": json.load(open(out_dir / "params.json")),
    }


def state_root(state: dict) -> bytes:
    t = SMT()
    for f, rec in state.items():
        t.update(f, record_hash(rec))
    return t.root


def check_root(art, as_of: str):
    """Recompute the whole state at as_of and compare with the signed daily root of that day."""
    day = as_of[:10]
    entry = next((e for e in art["ledger"] if e["day"] == day), None)
    if entry is None:
        return False, f"no ledger entry for {day}"
    got = state_root(art["store"].as_of(as_of)).hex()
    return got == entry["smt_root"], ("ok" if got == entry["smt_root"] else
                                      f"root mismatch on {day}: recomputed {got[:16]}…, signed {entry['smt_root'][:16]}…")


def verify_evidence(art, state: dict, *, trusted_issuers=None, trusted_installers=None,
                    allow_legacy_feed=False, allow_legacy_binding=False):
    """Verify source signatures. V2 is mandatory unless explicitly reviewing a V1 archive.

    New V2 verification REQUIRES trusted_issuers, a separately governed key map.
    Never infer trust from public_keys.json alone.
    ``allow_legacy_feed`` is for archival forensics ONLY. A V1 {field,value}
    signature does NOT authenticate unit or valid interval. Verify the archived
    state against its signed ledger commitment before relying on ANY legacy field.
    Never set this flag on newly ingested data.
    """
    bad = []
    for f, rec in state.items():
        adapter = rec.get("adapter", "")
        evidence = rec.get("evidence", {})
        if not isinstance(evidence, dict):
            bad.append(f)
            continue
        if adapter == "diyar-ref/0.2/dlms-suite1-sim-bound-v2":
            if not binding.validate_meter_record(state, rec,
                                                  trusted_installers=trusted_installers,
                                                  published_devices=art.get("keys", {}).get("devices"),
                                                  expected_field=f):
                bad.append(f)
        elif adapter.endswith("dlms-suite1-sim"):
            if not allow_legacy_binding:
                bad.append(f)
                continue
            try:
                dev = evidence["device_id"]
                pk = bytes.fromhex(art["keys"]["devices"][dev])
                for r in rec["value"]:
                    if not ec_verify(pk, reading_msg(dev, f, r["h"], r["v"]), bytes.fromhex(r["sig"])):
                        bad.append(f)
                        break
            except (KeyError, TypeError, ValueError, AttributeError):
                bad.append(f)
        elif adapter == "diyar-ref/0.2/installation-v2":
            if not binding.verify_binding_record(f, rec, trusted_installers):
                bad.append(f)
        elif adapter == "diyar-ref/0.2/revocation-v2":
            if not binding.verify_revocation_record(f, rec, trusted_installers):
                bad.append(f)
        elif adapter.endswith("/feed-v2"):
            if evidence.get("sig_format") != FEED_V2:
                bad.append(f)
                continue
            try:
                issuer_id, key_id = evidence["issuer"], evidence["issuer_key_id"]
                pk = pinned_issuer_key(trusted_issuers, issuer_id, key_id)
                # V2 publication indexes issuer keys by BOTH identity and key ID.
                # V1 flat mappings are accepted only by the explicit legacy branch.
                published = bytes.fromhex(art["keys"]["issuers"][issuer_id][key_id])
                ok = (pk is not None and pk == published and
                      verify_authoritative_v2(pk, evidence["sig"], issuer_id, f,
                                              rec["value"], issuer_key_id=key_id,
                                              unit=rec["unit"], valid_from=rec["valid_from"],
                                              valid_to=rec["valid_to"], schema_ver=rec["schema_ver"]))
                if not ok:
                    bad.append(f)
            except (KeyError, TypeError, ValueError, AttributeError):
                bad.append(f)
        elif adapter.endswith("/feed"):
            if not allow_legacy_feed or evidence.get("sig_format") is not None:
                bad.append(f)
                continue
            try:
                pk = bytes.fromhex(art["keys"]["issuers"][evidence["issuer"]])
                if not ec_verify(pk, canonical({"f": f, "v": rec["value"]}), bytes.fromhex(evidence["sig"])):
                    bad.append(f)
            except (KeyError, TypeError, ValueError, AttributeError):
                bad.append(f)
        elif adapter.endswith("/installation") or adapter.endswith("/revocation"):
            # Old unsigned installation is a historical artifact only. It cannot
            # authenticate the location of new V2 meter evidence.
            if not allow_legacy_binding:
                bad.append(f)
        elif rec.get("grade") == "A2" and ("sig" in evidence or "issuer" in evidence or "/feed" in adapter):
            # Unknown feed format must never bypass the signing path.
            bad.append(f)
        elif rec.get("grade") == "A1" or f.startswith("certificates/") or f.startswith("revocations/"):
            # An unrecognized signed meter or installation family is NOT a
            # reason to assume that provenance was verified.
            bad.append(f)
    return bad


SUFFICIENCY = 0.90   # data-sufficiency rule: at least 90% of the calendar hours metered (Table II)


def _binding_grade(state: dict, building: str, month: str, *, trusted_installers=None,
                   legacy_archival=False) -> tuple[str, list[str]]:
    """Find the cert for the ACTUAL DEVICE behind every used meter-day record.

    Strict default. Legacy grades are available only with explicit archival
    consent, and are not a replacement for a trusted physical installation.
    """
    if legacy_archival:
        inst = [(f, r) for f, r in state.items()
                if f.startswith("devices/") and isinstance(r["value"], dict)
                and r["value"].get("building") == building]
        if not inst:
            return "C", []
        return weakest([r["grade"] for _, r in inst]), [f for f, _ in inst]

    fields, grades = set(), []
    for f, rec in state.items():
        if not f.startswith(f"{building}/elec/{month}-"):
            continue
        if not binding.validate_meter_record(state, rec, trusted_installers=trusted_installers,
                                             expected_field=f):
            raise binding.BindingError(f"unbound or invalid meter evidence: {f}")
        cert_f = f"certificates/{rec['evidence']['binding_cert_id']}"
        fields.add(cert_f)
        grades.append(state[cert_f]["grade"])
    if not grades:
        return "C", []
    return weakest(grades), sorted(fields)


def report(state: dict, building: str, month: str, site: str, *,
           trusted_installers=None, legacy_archival=False):
    """Monthly performance report for one building, every output field carrying its grade.

    Coverage is measured against the CALENDAR (24 x days in the month), never against the days
    that happen to have weather, so a missing feed cannot look like full coverage (audit 2 Nov,
    P0-05). Weather coverage is reported separately; the baseline comparison uses only hours with
    both meter and weather, and the report says so in `status`.

    A signed reading is A1 for what the device measured; a BUILDING-level figure also rests on
    the device-to-building binding, so it takes the weaker of the two grades (whitepaper VI,
    audit P0-10)."""
    y, m = int(month[:4]), int(month[5:7])
    n_days = calendar.monthrange(y, m)[1]
    expected_hours = 24 * n_days
    # Validate the exact device behind each meter field BEFORE computing any
    # financial metric. Fail closed on misplaced/expired/unpinned evidence.
    g_bind, bind_fields = _binding_grade(state, building, month,
                                          trusted_installers=trusted_installers,
                                          legacy_archival=legacy_archival)
    model_rec = state[f"{building}/baseline"]
    model = model_rec["value"]

    metered, m_hours, m_vals, m_temps = {}, [], [], []
    wx_days = 0
    for d in range(1, n_days + 1):
        day = f"{month}-{d:02d}"
        wx = state.get(f"{site}/temp/{day}")
        wx_days += wx is not None
        rec = state.get(f"{building}/elec/{day}")
        if rec is None:
            continue
        for r in rec["value"]:
            if r["h"][:10] != day or r["h"] in metered:      # out-of-period or repeated hour: not evidence
                continue
            metered[r["h"]] = r["v"]
            if wx is not None:
                m_hours.append(r["h"])
                m_vals.append(r["v"])
                m_temps.append(wx["value"][int(r["h"][11:13])])

    coverage = len(metered) / expected_hours
    coverage_wx = wx_days / n_days
    status = ("insufficient" if coverage < SUFFICIENCY else "complete" if wx_days == n_days else "partial")
    actual = float(sum(metered.values()))
    act_matched = float(np.sum(m_vals)) if m_vals else 0.0
    predicted = float(np.sum(bl.predict(model, m_hours, m_temps))) if m_hours else 0.0
    gate_records = [r for f, r in state.items() if f.startswith(f"{building}/gate/{month}")]
    flags = sum(1 for r in gate_records if r["value"]["flag"])

    g_meter = weakest(["A1", g_bind])                     # building-level metered energy
    base_grade, base_status = trust.baseline_grade(state, f"{building}/baseline",
                                                   legacy_archival=legacy_archival)
    # Weather used for the displayed prediction is a mandatory input. Merely
    # obtaining the number from a feed cannot justify an automatic A2 label.
    wx_fields = [f"{site}/temp/{month}-{d:02d}" for d in range(1, n_days + 1)
                 if f"{site}/temp/{month}-{d:02d}" in state]
    wx_grades = [trust.source_grade(state, f) for f in wx_fields]
    g_weather = weakest(wx_grades) if wx_grades else None
    g_base = weakest([base_grade, g_weather]) if g_weather else base_grade
    # An unvalidated legacy 'derived' tag has no ordinal grade. In strict V2,
    # never upgrade it; C is the conservative ceiling. Historical replay keeps
    # the original label to reproduce the old signed output exactly.
    if legacy_archival:
        g_gate = "derived"
    else:
        gate_grades = [r.get("grade") if r.get("grade") in trust.GRADES else "C" for r in gate_records]
        g_gate = weakest([g_meter, g_base] + gate_grades)
    area = state.get(f"{building}/floor_area")
    occ = state.get(f"{building}/occupants")
    usable = status != "insufficient"
    out = {
        "building": building, "month": month, "status": status,
        "actual_kwh": {"value": round(actual, 3), "grade": g_meter},
        "baseline_kwh": {"value": round(predicted, 3), "grade": g_base,
                         "over": "hours with meter and weather",
                         **({"training_provenance": base_status} if not legacy_archival else {})},
        "performance_vs_baseline": ({"value": round(act_matched / predicted - 1, 5), "grade": weakest([g_meter, g_base])}
                                    if usable and predicted > 0 else {"value": None, "grade": None, "reason": status}),
        "coverage": {"value": round(coverage, 5), "grade": g_meter, "denominator_hours": expected_hours},
        "coverage_weather": {"value": round(coverage_wx, 5), "grade": (g_weather or "C") if not legacy_archival else "A2", "denominator_days": n_days},
        "binding": {"grade": g_bind, "evidence": bind_fields},
        "gate_flags": {"value": flags, "grade": g_gate},
        "kwh_per_m2": ({"value": round(actual / area["value"], 5), "grade": weakest([g_meter, area["grade"]])}
                       if area and usable else {"value": None, "grade": None,
                                                "absent": "proved by non-membership" if not area else status}),
        "kwh_per_occupant": ({"value": round(actual / occ["value"], 3), "grade": weakest([g_meter, occ["grade"]])}
                             if occ and usable else {"value": None, "grade": None,
                                                     "absent": "proved by non-membership" if not occ else status}),
    }
    out["residual_assumptions"] = {k: RESIDUAL[v["grade"]] for k, v in out.items()
                                   if isinstance(v, dict) and v.get("grade") in RESIDUAL}
    out["output_hash"] = H(OUTPUT, canonical({k: v for k, v in out.items() if k != "output_hash"})).hex()
    return out


def verify_all(art):
    k = art["keys"]
    return verify_chain(art["ledger"], bytes.fromhex(k["operator_ecdsa"]), k["slh_param"], bytes.fromhex(k["operator_slh"]))
