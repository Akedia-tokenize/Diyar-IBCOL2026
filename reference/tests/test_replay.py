"""Replay demonstration against a published run (records.jsonl, ledger.json, public_keys.json,
params.json, published_reports_jan.json). Uses only those files and the reference code.

Checks:
  1. the signature chain (ECDSA + SLH-DSA) verifies for every day
  2. the full state recomputed at the end of every day equals that day's signed root
  3. every device and issuer signature behind A1/A2 fields re-verifies
  4. bitemporal replay: January as known on 4 Feb reproduces the published report hash exactly;
     January as known now differs only for the building whose outage was backfilled on 20 Feb
  5. tampering with one committed reading is detected (signature and root), on the right day
  6. selective disclosure: one field verifies against the root with only that record revealed
  7. a field that was never entered is proved absent (non-membership), not silently missing

Run new V2 artifact: python3 -I tests/test_replay.py <run_dir> --issuer-pins /outside/repo/trusted.json
Run archival V1 only: python3 -I tests/test_replay.py <run_dir> --allow-archived-v1
The archival mode must check ledger signatures AND signed state roots first.
"""
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diyar import replay  # noqa: E402
from diyar.records import Store, record_hash  # noqa: E402
from diyar.smt import SMT, proof_size, verify  # noqa: E402

RUN = Path(sys.argv[1])
art = replay.load(RUN)
P = art["params"]
published = json.load(open(RUN / "published_reports_jan.json"))
results, details = [], {}


def check(name, ok, info=""):
    results.append((name, ok, info))


t0 = time.time()
ok, bad_day = replay.verify_all(art)
check("1 signature chain verifies (ECDSA + SLH-DSA)", ok, f"{len(art['ledger'])} days, param {art['keys']['slh_param']}")
details["chain_seconds"] = round(time.time() - t0, 1)

t0 = time.time()
mism = [e["day"] for e in art["ledger"] if not replay.check_root(art, f"{e['day']}T23:59")[0]]
check("2 recomputed state root = signed root, every day", not mism, f"mismatches: {mism[:3]}")
details["root_recompute_seconds_all_days"] = round(time.time() - t0, 1)

final = art["store"].as_of("2017-03-31T23:59")
# Archived v1.1 records used {field,value}-only feed signatures.
# Compatibility is explicit and requires separately checking the signed ledger roots.
legacy = "--allow-archived-v1" in sys.argv
pins = None
if "--issuer-pins" in sys.argv:
    i = sys.argv.index("--issuer-pins")
    pins = json.loads(Path(sys.argv[i + 1]).read_text())
inst_pins = None
if "--installer-pins" in sys.argv:
    i = sys.argv.index("--installer-pins")
    inst_pins = json.loads(Path(sys.argv[i + 1]).read_text())
if legacy and (not ok or mism):
    raise RuntimeError("archival V1 feed verification requires an intact signed history and state roots")
bad = replay.verify_evidence(art, final, trusted_issuers=pins, trusted_installers=inst_pins,
                             allow_legacy_feed=legacy, allow_legacy_binding=legacy)
check("3 all A1/A2 evidence signatures re-verify", not bad, f"{len(bad)} bad")

then = art["store"].as_of(P["report_root"])
now = final
same, differ = [], []
for b in P["buildings"]:
    r_then = replay.report(then, b, "2017-01", P["site"], legacy_archival=legacy, trusted_installers=inst_pins)
    r_now = replay.report(now, b, "2017-01", P["site"], legacy_archival=legacy, trusted_installers=inst_pins)
    committed = art["store"].as_of("2017-02-05T23:59")[f"report/2017-01/{b}"]["value"]["output_hash"]
    same.append(r_then["output_hash"] == committed == published[b]["output_hash"])
    if r_now["output_hash"] != r_then["output_hash"]:
        differ.append(b)
        details["correction_effect"] = {
            "building": b,
            "actual_kwh_as_of_4Feb": r_then["actual_kwh"]["value"], "actual_kwh_now": r_now["actual_kwh"]["value"],
            "coverage_as_of_4Feb": r_then["coverage"]["value"], "coverage_now": r_now["coverage"]["value"],
            "performance_as_of_4Feb": r_then["performance_vs_baseline"]["value"],
            "performance_now": r_now["performance_vs_baseline"]["value"]}
check("4a replay(Jan, as of 4 Feb) reproduces every published report hash", all(same))
check("4b replay(Jan, now) differs only for the backfilled building", differ == [P["outage"]["building"]], f"differs: {differ}")

# 5. tamper: shave 10% off one committed reading of building 0 on 20 Jan
tam = copy.deepcopy(art)
victim = f"{P['buildings'][0]}/elec/2017-01-20"
rec = tam["store"].versions[victim][-1]
rec["value"][12]["v"] = round(rec["value"][12]["v"] * 0.9, 4)
ev = replay.verify_evidence(tam, tam["store"].as_of("2017-03-31T23:59"),
                            trusted_issuers=pins, trusted_installers=inst_pins,
                             allow_legacy_feed=legacy, allow_legacy_binding=legacy)
first_bad = next((e["day"] for e in tam["ledger"] if not replay.check_root(tam, f"{e['day']}T23:59")[0]), None)
check("5 tampered reading detected by device signature and by root", victim in ev and first_bad == "2017-01-20",
      f"first root mismatch: {first_bad}")

# 6. selective disclosure of one field
t = SMT()
for f, r in final.items():
    t.update(f, record_hash(r))
f = f"{P['buildings'][1]}/elec/2017-02-10"
pr = t.prove(f)
root = bytes.fromhex(art["ledger"][-1]["smt_root"])
check("6 one field verifies alone against the signed root", verify(root, f, record_hash(final[f]), pr),
      f"proof {proof_size(pr)} bytes, {len(pr['siblings'])} siblings")

# 7. non-membership: the third building never had occupants entered
g = f"{P['buildings'][2]}/occupants"
check("7 a never-entered field is proved absent", g not in final and verify(root, g, None, t.prove(g)))

w = max(len(r[0]) for r in results)
for name, ok, info in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name:<{w}}  {info}")
print(json.dumps(details, indent=1))
json.dump({"checks": [{"name": n, "ok": o, "info": i} for n, o, i in results], **details},
          open(RUN / "replay_checks.json", "w"), indent=1)
sys.exit(0 if all(r[1] for r in results) else 1)
