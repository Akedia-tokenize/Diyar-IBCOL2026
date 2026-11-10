"""DIYAR-ref end to end on three BDG2 'Fox' buildings, 1 Jan - 31 Mar 2017.

Scenario (all data real except the keys, which are simulated):
  31 Dec 2016  device installation records (B), authoritative floor areas (A2), committed
               baselines fitted on 2016 (derived), an owner-uploaded occupancy schedule (C+)
               and manually entered occupants (C) for two of the three buildings.
  each day     signed weather feed (A2); device-signed hourly meter readings (A1);
               rules + rolling conformal gate; decision committed; state root signed
               (ECDSA + SLH-DSA-256s) and chained.
  15 Jan       building X's meter loses six hours (06:00-11:59) in transit.
  5 Feb        January reports published from the 4 Feb root and committed.
  20 Feb       the operator backfills X's six missing hours (device-signed): a correction
               with valid time 15 Jan and transaction time 20 Feb. Nothing is overwritten.

Usage: python3 -I run_pipeline.py <bdg2_root> <out_dir> [--fast]
  --fast uses SLH-DSA-128f for quick development runs; the reported run uses 256s.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diyar import baseline as bl  # noqa: E402
from diyar import binding, gate, intake, replay, trust  # noqa: E402
from diyar.crypto import ECKey, SLHKey  # noqa: E402
from diyar.ledger import Ledger  # noqa: E402
from diyar.records import Store, make_record, record_hash, weakest  # noqa: E402
from diyar.smt import SMT, proof_size  # noqa: E402

BDG2, OUT = Path(sys.argv[1]), Path(sys.argv[2])
FAST = "--fast" in sys.argv
OUT.mkdir(parents=True, exist_ok=True)
SITE = "Fox"
BUILDINGS = ["Fox_office_Joy", "Fox_education_Wendell", "Fox_assembly_Renna"]
OUTAGE = {"building": BUILDINGS[0], "day": "2017-01-15", "hours": range(6, 12)}
REPORT_TX, REPORT_ROOT = "2017-02-05T09:00", "2017-02-04T23:59"
BACKFILL_TX = "2017-02-20T10:00"
DAYS = pd.date_range("2017-01-01", "2017-03-31").strftime("%Y-%m-%d").tolist()

# --- data ------------------------------------------------------------------------------
meta = pd.read_csv(BDG2 / "data/metadata/metadata.csv").set_index("building_id")
elec = pd.read_csv(BDG2 / "data/meters/cleaned/electricity_cleaned.csv", usecols=["timestamp"] + BUILDINGS,
                   parse_dates=["timestamp"]).set_index("timestamp")
wx = pd.read_csv(BDG2 / "data/weather/weather.csv", parse_dates=["timestamp"])
temp = (wx[wx.site_id == SITE].set_index("timestamp")["airTemperature"].reindex(elec.index)
        .interpolate(limit_direction="both"))

# --- keys (simulated parties) -----------------------------------------------------------
operator_ec = ECKey()
operator_slh = SLHKey("sha2_128f" if FAST else "sha2_256s")
weather_issuer, registry_issuer = ECKey(), ECKey()
# Simulation ONLY: key pins are created in the same local scenario. Real operations
# must load these pins from an independently governed issuer identity registry.
TRUSTED_ISSUERS = {
    "weather-service": {"weather-key-01": weather_issuer.pk_bytes},
    "land-registry": {"registry-key-01": registry_issuer.pk_bytes},
}
meters = {b: intake.Meter(f"meter-{i:03d}", ECKey()) for i, b in enumerate(BUILDINGS)}
# SIMULATED accredited installer. Its key must be independently pinned in reality.
installer_key = ECKey()
TRUSTED_INSTALLERS = {"independent-installer": {"installer-key-01": installer_key.pk_bytes}}

store, smt, ledger = Store(), SMT(), Ledger(operator_ec, operator_slh)
models, stats = {}, {"gate": {"pass": 0, "flag_rule": 0, "flag_conformal": 0, "calibrating": 0}}


def add(rec):
    store.add(rec)
    smt.update(rec["field"], record_hash(rec))


# --- 31 Dec 2016: setup records ----------------------------------------------------------
T0 = "2016-12-31T12:00"
for b in BUILDINGS:
    m = meters[b]
    cert_fields = dict(certificate_id=f"install-{m.device_id}-2016", device_id=m.device_id,
                       public_key=m.key.pk_bytes.hex(), building_id=b, channel="electricity",
                       unit="kWh", location=f"{b} main incomer",
                       valid_from="2016-12-31", valid_to=None,
                       installer_id="independent-installer", installer_key_id="installer-key-01")
    sig = binding.sign_binding(installer_key, **cert_fields)
    add(binding.ingest_binding(**cert_fields, signature=sig,
                               trusted_installers=TRUSTED_INSTALLERS, tx_time=T0))
    area = float(meta.at[b, "sqm"])
    add(intake.ingest_authoritative(f"{b}/floor_area", area, intake.issue_signed(registry_issuer, f"{b}/floor_area", area,
                                                        issuer_id="land-registry", issuer_key_id="registry-key-01", unit="m2",
                                                        valid_from="2016-12-31", valid_to=None),
                                    "land-registry", registry_issuer.pk_bytes, issuer_key_id="registry-key-01",
                                    trusted_issuers=TRUSTED_ISSUERS, unit="m2",
                                    valid_from="2016-12-31", valid_to=None, tx_time=T0))
    y16 = elec.loc["2016", b]
    mdl = bl.fit(y16.index, temp.loc["2016"].values, y16.values)
    assert mdl["accepted"], (b, mdl["cv_rmse"], mdl["nmbe"])
    models[b] = mdl
    # The 2016 BDG2 training arrays are NOT signed/committed meter-day records.
    # A fitted model cannot inherit a hypothetical A1/B source grade. Hash the
    # input arrays for reproducibility, but label provenance C until independently
    # authenticated 2016 evidence is available in the ledger.
    add(trust.baseline_record(f"{b}/baseline", mdl,
                              valid_from="2017-01-01", tx_time=T0,
                              source_payloads={"hours": [str(t) for t in y16.index],
                                               "meter_kwh": [None if pd.isna(v) else float(v) for v in y16.values],
                                               "weather_C": [None if pd.isna(v) else float(v) for v in temp.loc["2016"].values]}))
add(intake.ingest_upload(f"{BUILDINGS[0]}/occupancy_schedule", b"weekday 07:00-19:00, closed Sundays",
                         {"weekday_hours": "07:00-19:00", "closed": ["Sunday"]},
                         valid_from="2017-01-01", valid_to=None, tx_time=T0))
for b, n in [(BUILDINGS[0], 240), (BUILDINGS[1], 410)]:                      # BUILDINGS[2]: none entered
    add(intake.ingest_manual(f"{b}/occupants", n, unit="persons", valid_from="2017-01-01", valid_to=None, tx_time=T0))
ledger.commit("2016-12-31", smt.root)


def run_gate(b, day, readings, tx, state_now):
    hours = [r["h"] for r in readings]
    wxv = state_now[f"{SITE}/temp/{day}"]["value"]
    temps = [wxv[int(h[11:13])] for h in hours]
    pred = bl.predict(models[b], hours, temps) if hours else np.array([])
    scale = models[b]["mean_hourly_kwh"] * 24
    max_h = 5 * float(np.nanmax(elec.loc["2016", b]))
    rr = gate.rules(readings, max_h, day)
    s = gate.score(sum(r["v"] for r in readings), float(pred.sum()), scale) if hours else None
    prior = sorted((f for f in state_now if f.startswith(f"{b}/gate/") and f.rsplit("/", 1)[1] < day))[-gate.WINDOW:]
    cal = [state_now[f]["value"]["score"] for f in prior if state_now[f]["value"]["score"] is not None]
    d = gate.decide(rr, s if s is not None else 0.0, cal, bl.model_version(models[b]))
    meter_field, wx_field, baseline_field = f"{b}/elec/{day}", f"{SITE}/temp/{day}", f"{b}/baseline"
    binding_grade, _ = replay._binding_grade(state_now, b, day[:7],
                                             trusted_installers=TRUSTED_INSTALLERS)
    model_grade, _ = trust.baseline_grade(state_now, baseline_field)
    weather_grade = trust.source_grade(state_now, wx_field)
    source_grades = ["A1", binding_grade, model_grade, weather_grade]
    # Calibration uses past gate scores. They are necessary dependencies too.
    source_grades += [trust.source_grade(state_now, f) for f in prior if state_now[f]["value"]["score"] is not None]
    gate_grade = weakest(source_grades)
    return make_record(f"{b}/gate/{day}", d, grade=gate_grade,
                       adapter="diyar-ref/0.3/gate-trust-v1",
                       valid_from=day, valid_to=day, tx_time=tx,
                       evidence={"trust_protocol": trust.TRUST_PROTOCOL,
                                 "source_grades": source_grades},
                       derived_from=[meter_field, baseline_field, wx_field] +
                                    [f for f in prior if state_now[f]["value"]["score"] is not None])


t_start = time.time()
reports = {}
for day in DAYS:
    tx = f"{day}T23:30"
    if day == "2017-02-05":                                          # publish January reports
        st = store.as_of(REPORT_ROOT)
        for b in BUILDINGS:
            rep = replay.report(st, b, "2017-01", SITE, trusted_installers=TRUSTED_INSTALLERS)
            reports[b] = rep
            add(make_record(f"report/2017-01/{b}", {"output_hash": rep["output_hash"], "as_of": REPORT_ROOT},
                            grade="derived", adapter="diyar-ref/0.1/report", valid_from="2017-01-01",
                            valid_to="2017-01-31", tx_time=REPORT_TX))
    if day == "2017-02-20":                                          # backfill the outage (correction)
        b, d0 = OUTAGE["building"], OUTAGE["day"]
        s = elec.loc[d0, b].dropna()
        f = f"{b}/elec/{d0}"
        rd = meters[b].emit(f, [ts.strftime("%Y-%m-%dT%H:00") for ts in s.index], [round(float(v), 4) for v in s.values])
        add(intake.ingest_meter_day(f, rd, meters[b].device_id, meters[b].key.pk_bytes,
                                    valid_from=d0, valid_to=d0, tx_time=BACKFILL_TX,
                                    binding_state=store.as_of(BACKFILL_TX), trusted_installers=TRUSTED_INSTALLERS))
        add(run_gate(b, d0, rd, BACKFILL_TX, store.as_of(BACKFILL_TX)))
    temps = [round(float(v), 2) for v in temp.loc[day].values]
    fwx = f"{SITE}/temp/{day}"
    add(intake.ingest_authoritative(fwx, temps, intake.issue_signed(weather_issuer, fwx, temps, issuer_id="weather-service", issuer_key_id="weather-key-01",
                                                                               unit="degC", valid_from=day, valid_to=day), "weather-service",
                                    weather_issuer.pk_bytes, issuer_key_id="weather-key-01",
                                    trusted_issuers=TRUSTED_ISSUERS, unit="degC", valid_from=day, valid_to=day, tx_time=tx))
    for b in BUILDINGS:
        s = elec.loc[day, b].dropna()
        if b == OUTAGE["building"] and day == OUTAGE["day"]:
            s = s[~s.index.hour.isin(list(OUTAGE["hours"]))]
        f = f"{b}/elec/{day}"
        rd = meters[b].emit(f, [ts.strftime("%Y-%m-%dT%H:00") for ts in s.index], [round(float(v), 4) for v in s.values])
        add(intake.ingest_meter_day(f, rd, meters[b].device_id, meters[b].key.pk_bytes,
                                    valid_from=day, valid_to=day, tx_time=tx,
                                    binding_state=store.as_of(tx), trusted_installers=TRUSTED_INSTALLERS))
        g = run_gate(b, day, rd, f"{day}T23:45", store.as_of(f"{day}T23:31"))
        add(g)
        v = g["value"]
        stats["gate"]["flag_rule" if v["reason"] == "rule" else "flag_conformal" if v["flag"] else
                      "calibrating" if v["reason"] == "calibrating" else "pass"] += 1
    ledger.commit(day, smt.root)
elapsed = time.time() - t_start

# --- publish artefacts ------------------------------------------------------------------
store.dump(OUT / "records.jsonl")
json.dump(ledger.entries, open(OUT / "ledger.json", "w"), indent=0)
json.dump({"operator_ecdsa": operator_ec.pk_bytes.hex(), "operator_slh": operator_slh.pk_bytes.hex(),
           "slh_param": operator_slh.param,
           "devices": {m.device_id: m.key.pk_bytes.hex() for m in meters.values()},
           "issuers": {issuer: {kid: key.hex() for kid, key in keys.items()}
                       for issuer, keys in TRUSTED_ISSUERS.items()},
           "issuer_keys_format": "issuer-keyid-v2",
           "installers": {issuer: {kid: key.hex() for kid, key in keys.items()}
                          for issuer, keys in TRUSTED_INSTALLERS.items()},
           "installer_pins_format": "installer-keyid-v2 (DEMO; NOT independently trusted)"},
          open(OUT / "public_keys.json", "w"), indent=1)
# This is a TEST-ONLY illustration of the pin-file structure. It is NOT an
# independently authenticated issuer registry: created by the same simulator.
json.dump({issuer: {kid: pk.hex() for kid, pk in keys.items()}
           for issuer, keys in TRUSTED_ISSUERS.items()},
          open(OUT / "issuer_pins_DEMO_NOT_TRUSTED.json", "w"), indent=2)
json.dump({issuer: {kid: pk.hex() for kid, pk in keys.items()}
           for issuer, keys in TRUSTED_INSTALLERS.items()},
          open(OUT / "installer_pins_DEMO_NOT_TRUSTED.json", "w"), indent=2)
json.dump({"site": SITE, "buildings": BUILDINGS, "alpha": gate.ALPHA, "window": gate.WINDOW,
           "report_root": REPORT_ROOT, "outage": {**OUTAGE, "hours": list(OUTAGE["hours"])},
           "backfill_tx": BACKFILL_TX}, open(OUT / "params.json", "w"), indent=1)
json.dump(reports, open(OUT / "published_reports_jan.json", "w"), indent=1)

n_versions = sum(len(v) for v in store.versions.values())
pr = smt.prove(f"{BUILDINGS[0]}/elec/2017-01-20")
stats.update({
    "days_committed": len(ledger.entries), "fields": len(store.versions), "record_versions": n_versions,
    "corrected_fields": [f for f, v in store.versions.items() if len(v) > 1],
    "records_bytes": (OUT / "records.jsonl").stat().st_size, "ledger_bytes": (OUT / "ledger.json").stat().st_size,
    "slh_param": operator_slh.param, "slh_signature_bytes": len(bytes.fromhex(ledger.entries[-1]["slh_dsa"])),
    "example_proof_bytes": proof_size(pr), "pipeline_seconds": round(elapsed, 1),
    "baselines": {b: {"cv_rmse": m["cv_rmse"], "nmbe": m["nmbe"]} for b, m in models.items()},
})
json.dump(stats, open(OUT / "run_stats.json", "w"), indent=1)
print(json.dumps(stats, indent=1))
