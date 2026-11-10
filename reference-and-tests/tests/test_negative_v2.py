"""Negative tests added after the independent audit of 2 Nov 2026.

Each check states the audit finding it closes. Every check must PASS on the published run.

  N1 (P0-05)  a day of weather removed: metered energy and coverage unchanged, weather coverage
              drops, status becomes 'partial' (it used to report coverage 1.0 silently)
  N2 (P0-05)  six metered hours removed: coverage falls by exactly 6/744
  N3 (P0-06)  24 copies of the same hour: coverage_ok False, 1 distinct hour, reason duplicate_interval
  N4 (P0-06)  readings stamped on another day do not count for this day
  N5 (P1-17)  2,000 malformed proofs: no exception, no false accept; genuine proofs still verify
  N6 (P1-15)  bitemporal query on both axes with overlapping corrections
  N7 (P0-10)  building-level grade follows the installation binding: B -> B, C -> C, none -> C
  N8 (P1-18)  canonical encoding refuses NaN / Infinity

Run (V2 artefacts): python3 -I tests/test_negative_v2.py <run_dir> --installer-pins <pins.json>
Same checks as test_negative.py; N7 is rewritten for METER-BIND-V2 certificates (6 Nov 2026).
"""
import copy
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diyar import gate, replay  # noqa: E402
from diyar.crypto import canonical  # noqa: E402
from diyar.records import Store, make_record  # noqa: E402
from diyar.smt import SMT, verify  # noqa: E402

RUN = Path(sys.argv[1])
PINS = json.loads(Path(sys.argv[sys.argv.index("--installer-pins") + 1]).read_text())
art = replay.load(RUN)
P = art["params"]
SITE, B0, B1 = P["site"], P["buildings"][0], P["buildings"][1]
results = []


def check(name, ok, info=""):
    results.append((name, bool(ok), info))


final = art["store"].as_of("2017-03-31T23:59")

# N1 -- weather removed for one day
base = replay.report(final, B1, "2017-01", SITE, legacy_archival=True)
st = dict(final)
st.pop(f"{SITE}/temp/2017-01-12")
r = replay.report(st, B1, "2017-01", SITE, legacy_archival=True)
check("N1 missing weather -> status partial, metered energy and coverage unchanged",
      r["status"] == "partial" and r["actual_kwh"]["value"] == base["actual_kwh"]["value"]
      and r["coverage"]["value"] == base["coverage"]["value"]
      and abs(r["coverage_weather"]["value"] - 30 / 31) < 1e-5 and base["status"] == "complete",
      f"status {base['status']} -> {r['status']}, weather coverage {r['coverage_weather']['value']}")

# N2 -- six metered hours removed
st = copy.deepcopy(final)
f = f"{B1}/elec/2017-01-12"
st[f]["value"] = [x for x in st[f]["value"] if int(x["h"][11:13]) not in range(6, 12)]
r2 = replay.report(st, B1, "2017-01", SITE, legacy_archival=True)
drop = round(base["coverage"]["value"] - r2["coverage"]["value"], 5)
check("N2 six metered hours removed -> coverage falls by 6/744", abs(drop - 6 / 744) < 2e-5, f"drop {drop}")

# N3 / N4 -- duplicate and out-of-period timestamps
dup = gate.rules([{"h": "2017-01-12T00:00", "v": 10.0} for _ in range(24)], 1e6, "2017-01-12")
check("N3 24 identical timestamps -> coverage_ok False, 1 distinct hour, duplicate_interval",
      not dup["coverage_ok"] and dup["hours_present"] == 1 and any("duplicate_interval" in x for x in dup["reasons"]),
      json.dumps(dup))
other = gate.rules([{"h": f"2017-01-13T{h:02d}:00", "v": 10.0} for h in range(24)], 1e6, "2017-01-12")
check("N4 readings stamped on another day do not count", not other["coverage_ok"] and other["hours_present"] == 0,
      json.dumps(other["reasons"]))

# N5 -- malformed proofs (fuzz)
rng = random.Random(20261102)
t = SMT()
for i in range(50):
    t.update(f"f{i}", bytes([i]) * 32)
good = t.prove("f7")
ok_genuine = verify(t.root, "f7", bytes([7]) * 32, good) and verify(t.root, "absent", None, t.prove("absent"))
crashes, false_accepts = 0, 0
for _ in range(2000):
    pr = {"mask": good["mask"], "siblings": list(good["siblings"])}
    k = rng.randrange(8)                                            # every branch changes the proof
    if k == 0:
        free = [b for b in range(256) if not (good["mask"] >> b) & 1]
        pr["mask"] |= 1 << rng.choice(free)                         # extra bit, missing sibling
    elif k == 1:
        pr["siblings"] = pr["siblings"][:-1]                        # too few siblings
    elif k == 2:
        pr["siblings"].append(bytes(32))                            # surplus sibling
    elif k == 3:
        pr["mask"] = rng.choice([-1, 1 << 256, 2 ** 300, "x", None, 1.5, True])
    elif k == 4:
        i = rng.randrange(len(pr["siblings"]))
        pr["siblings"][i] = rng.choice([b"", b"\x00" * 31, b"\x00" * 33, "00" * 32, None, 7])
    elif k == 5:
        pr = rng.choice([{}, {"mask": 0}, {"siblings": []}, None, [], "proof"])
    elif k == 6:
        i = rng.randrange(len(pr["siblings"]))
        s = bytearray(pr["siblings"][i]); s[rng.randrange(32)] ^= 1 << rng.randrange(8)
        pr["siblings"][i] = bytes(s)                                # one flipped bit
    elif k == 7:
        pr["mask"] ^= 1 << rng.randrange(256)                       # flipped mask bit
    if isinstance(pr, dict) and pr.get("mask") == good["mask"] and pr.get("siblings") == good["siblings"]:
        raise AssertionError("fuzz case left the proof unchanged")
    try:
        res = verify(t.root, "f7", bytes([7]) * 32, pr)
        false_accepts += res is True
    except Exception:                                               # noqa: BLE001
        crashes += 1
check("N5 2,000 malformed proofs: zero crashes, zero false accepts, genuine proofs verify",
      ok_genuine and crashes == 0 and false_accepts == 0, f"crashes {crashes}, false accepts {false_accepts}")

# N6 -- bitemporal query, overlapping corrections
s = Store()
s.add(make_record("b/use", 100, grade="A1", adapter="t", valid_from="2017-01-01", valid_to="2017-01-31", tx_time="2017-02-01T00:00"))
s.add(make_record("b/use", 90, grade="A1", adapter="t", valid_from="2017-01-01", valid_to="2017-01-15", tx_time="2017-02-10T00:00"))
s.add(make_record("b/use", 95, grade="A1", adapter="t", valid_from="2017-01-10", valid_to="2017-01-31", tx_time="2017-02-20T00:00"))
q = [s.query(v, k).get("b/use", {}).get("value") for v, k in
     [("2017-01-05", "2017-02-05T00:00"), ("2017-01-05", "2017-02-15T00:00"), ("2017-01-20", "2017-02-15T00:00"),
      ("2017-01-20", "2017-02-25T00:00"), ("2017-01-05", "2017-02-25T00:00"), ("2017-01-05", "2017-01-20T00:00")]]
check("N6 bitemporal query answers both axes", q == [100, 90, 100, 95, 90, None], f"got {q}")

# N7 (V2) -- building-level grade follows the signed installation certificate; unbound evidence fails closed
from diyar.binding import BindingError  # noqa: E402


def _grade(state):
    try:
        return replay.report(state, B1, "2017-01", SITE, trusted_installers=PINS)["actual_kwh"]["grade"]
    except BindingError:
        return "refused"


_cert = next(f for f, rec in final.items() if f.startswith("certificates/") and rec["value"].get("building_id") == B1)
_gone = copy.deepcopy(final); _gone.pop(_cert)
_moved = copy.deepcopy(final); _moved[_cert]["value"]["building_id"] = P["buildings"][0]
_res = (_grade(final), _grade(_gone), _grade(_moved))
check("N7 grade follows the signed certificate (B; removed -> refused; relabelled -> refused)",
      _res == ("B", "refused", "refused"), str(_res))

# N8 -- canonical encoding refuses NaN / Infinity
refused = 0
for bad in (float("nan"), float("inf"), -float("inf")):
    try:
        canonical({"v": bad})
    except ValueError:
        refused += 1
check("N8 canonical encoding refuses NaN and Infinity", refused == 3, f"{refused}/3 refused")

w = max(len(n) for n, _, _ in results)
for n, ok, info in results:
    print(f"{'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {info}")
json.dump([{"check": n, "pass": ok, "info": info} for n, ok, info in results],
          open(RUN / "negative_checks_v2.json", "w"), indent=1)
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} PASS")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
