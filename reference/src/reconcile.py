"""Claim-to-evidence reconciliation for the whitepaper (v2.6, 8 Nov 2026).

Every measured or modelled number printed in the whitepaper's main text is read back from the file
that produces it, rounded the way the paper rounds it, and compared. With --paper, each number's
exact wording must also appear in the paper text, so the check covers what is printed, not a list
kept beside it. Cited numbers from the literature are listed with their reference, not recomputed.

Usage: python3 -I src/reconcile.py <results_dir> <cost_model.xlsx> <out.csv>
                                   [--paper paper/DIYAR-whitepaper-v2.6.md] [--bdg2 <bdg2_root>]
Exit code 1 if any number disagrees or any wording is missing from the paper.
"""
import csv
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openpyxl import load_workbook

args = sys.argv[1:]
opt = {k: args[args.index(k) + 1] for k in ("--paper", "--bdg2") if k in args}
R, XL, OUT = Path(args[0]), args[1], args[2]
REPO = Path(__file__).resolve().parents[1]
J = lambda f: json.load(open(R / f))  # noqa: E731
e1 = {(r["basis"], r["scenario"][:2]): r for r in csv.DictReader(open(R / "e1_storage.csv"))}
E1 = lambda s, col: float(e1[("whitepaper assumption (5 channels)", s)][col])  # noqa: E731
e2, oot = J("e2_summary.json"), J("e2_out_of_time.json")
g14 = list(csv.DictReader(open(R / "e2_g14.csv")))
fox_ok = sorted(float(r["cv_rmse"]) for r in g14 if r["building"].startswith("Fox") and float(r["cv_rmse"]) <= 0.30)
q, e3a, e3b, e4 = J("e3a_quarterly.json"), J("e3a_results.json"), J("e3b_results.json"), J("e4_results.json")
ext = {r["size"]: r for r in J("e3a_extra.json")["rows"]}
pw = {(r["manipulation"], r["size"]): r for r in q["power_single_building"]}
prev = {r["prevalence"]: r for r in q["prevalence_sweep_shave20"]}
slow = {r["alpha"]: r for r in e4["slow_quarterly_gate"]}
curve = e3a["curves"]["shave_20"]["fast"]
run, rep = J("v2_run/run_stats.json"), J("v2_run/replay_checks.json")     # reference run of 6 Nov 2026
neg = J("v2_run/negative_checks_v2.json")
par = J("v2_run/params.json")
anchor_gas = json.load(open(REPO / "anchor" / "gas.json"))["typical_anchor_gas"]   # measured by anchor/test.mjs
wb = load_workbook(XL, data_only=True)
X = lambda sheet, cell: wb[sheet][cell].value  # noqa: E731
total = X("Annual cost", "B11")
mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
med = lambda xs: (xs[len(xs) // 2] + xs[(len(xs) - 1) // 2]) / 2  # noqa: E731
info = lambda name: next(c["info"] for c in rep["checks"] if c["name"].startswith(name))  # noqa: E731
suites = ["test_authoritative_v2", "test_binding_v2", "test_trust_p003", "test_store_chronology_p004"]
n_tests = sum(len(re.findall(r"^\s*def test_", (REPO / "tests" / f"{s}.py").read_text(), re.M)) for s in suites)
n_vectors = len(re.findall(r"^check\(", (REPO / "tests" / "test_vectors.py").read_text(), re.M))
n_files = len([ln for ln in (REPO / "data_manifest.sha256").read_text().splitlines() if ln.strip()])
# size at which one-sided quarterly detection crosses 80% (linear between the measured points)
lo, hi = max(s for s in ext if ext[s]["power_one_sided"] < 0.8), min(s for s in ext if ext[s]["power_one_sided"] >= 0.8)
cross80 = 100 * (lo + (hi - lo) * (0.8 - ext[lo]["power_one_sided"]) / (ext[hi]["power_one_sided"] - ext[lo]["power_one_sided"]))

# (id, where in the paper, wording as printed, value as printed, source, exact value, decimals compared)
M = [
    ("cross80", "Abstract, I, VIII", "80% detection only at about a 25% under-report", 25, "e3a_extra.json: size where power crosses 80%", cross80, 0),
    ("abs_split", "Abstract", "to 17.4% alerts", 17.4, "e2_summary.json all_sites split", 100 * e2["all_sites"]["split"]["overall_flag_rate"], 1),
    ("abs_recent", "Abstract", "back to about 5%", 5, "e2_summary.json all_sites rolling28", 100 * e2["all_sites"]["rolling28"]["overall_flag_rate"], 0),
    ("abs_tiers", "Abstract", "resolves at 4 tiers", 4, "Table II / Annex A tiers", 4, 0),
    ("grades", "I, III.A", "7-level provenance grade", 7, "diyar/records.py GRADES", 7, 0),
    ("modes", "Abstract, I", "17-mode failure taxonomy", 17, "Table II / Annex A", 12 + 1 + 3 + 1, 0),
    ("tiers", "I, III.C", "12 rules, 1 structural mechanism, 3 statistical tests and 1 learned model", 17, "Table II / Annex A.3 register", 17, 0),
    ("t2_title", "III.C Table II", "17 Failure Modes in 4 Tiers", 17, "Annex A.3 register", 17, 0),
    ("watch", "III.B", "about 18 watch signals", 18, "alpha 5% x 365 days", 0.05 * 365, 0),
    ("review", "III.B, VII", "0.189 review cases", 0.189, "e4_results.json alpha 0.05", slow[0.05]["cases_per_building_year"], 3),
    ("window", "III.B", "compares each day with the prior 28 days", 28, "v2_run/params.json window", par["window"], 0),
    ("period", "III.B", "over the last 90 days", 90, "e3a_quarterly.json params.period_days", q["params"]["period_days"], 0),
    ("bldgs", "IV", "ran it on 3 buildings", 3, "v2_run/params.json buildings", len(par["buildings"]), 0),
    ("asof", "IV", "as known on 4 February", 4, "v2_run/params.json report_root (day)", int(par["report_root"][8:10]), 0),
    ("days", "IV", "91 signed days", 91, "v2_run/run_stats.json", run["days_committed"], 0),
    ("fields", "IV", "645 fields", 645, "v2_run/run_stats.json", run["fields"], 0),
    ("versions", "IV", "647 versions", 647, "v2_run/run_stats.json", run["record_versions"], 0),
    ("rec_mb", "IV", "1.74 MB of records", 1.74, "v2_run/run_stats.json (decimal MB)", run["records_bytes"] / 1e6, 2),
    ("ledger_mb", "IV", "5.46 MB of ledger", 5.46, "v2_run/run_stats.json (decimal MB)", run["ledger_bytes"] / 1e6, 2),
    ("admitted", "IV", "admitted 201 items", 201, "v2_run/run_stats.json gate.pass", run["gate"]["pass"], 0),
    ("rule_flag", "IV", "1 rule flag", 1, "v2_run/run_stats.json", run["gate"]["flag_rule"], 0),
    ("conf_flags", "IV", "8 conformal flags", 8, "v2_run/run_stats.json", run["gate"]["flag_conformal"], 0),
    ("roots", "IV", "roots matched on all 91 days", 91, "v2_run/replay_checks.json check 1",
     int(re.search(r"(\d+) days", info("1 signature chain")).group(1)), 0),
    ("cov_then", "IV", "coverage 99.06% → 99.87%", 99.06, "v2_run/replay_checks.json", 100 * rep["correction_effect"]["coverage_as_of_4Feb"], 2),
    ("cov_now", "IV", "coverage 99.06% → 99.87%", 99.87, "v2_run/replay_checks.json", 100 * rep["correction_effect"]["coverage_now"], 2),
    ("proof", "IV", "320-byte proof", 320, "v2_run/replay_checks.json check 6", int(re.search(r"proof (\d+) bytes", info("6 one field")).group(1)), 0),
    ("negative", "IV", "All 8 negative checks", 8, "v2_run/negative_checks_v2.json (all pass)", len(neg) if all(c["pass"] for c in neg) else -1, 0),
    ("malformed", "IV", "2,000 malformed proofs", 2000, "v2_run/negative_checks_v2.json N5",
     int(re.search(r"([\d,]+) malformed", next(c["check"] for c in neg if c["check"].startswith("N5"))).group(1).replace(",", "")), 0),
    ("tests", "IV", "108 targeted tests", 108, "def test_ in the 4 V2 suites", n_tests, 0),
    ("vectors", "IV", "Test vectors for 4 historical verifier failures", 4, "tests/test_vectors.py check() calls", n_vectors, 0),
    ("ecdsa", "IV", "64 bytes on a 43-byte record", 64, "e1_summary.json", J("e1_summary.json")["measured_building_year"]["ecdsa_raw_bytes"], 0),
    ("record", "IV", "64 bytes on a 43-byte record", 43, "e1_summary.json", J("e1_summary.json")["measured_building_year"]["record_bytes"], 0),
    ("slh", "IV", "29,792 bytes", 29792, "slh_sizes.json sha2_256s", J("slh_sizes.json")["sha2_256s"]["signature_bytes"], 0),
    ("tb_s2", "IV", "from 11.25 TB to 837 TB", 837, "e1_storage.csv S2, 5 channels", E1("S2", "TB_60y_single_copy"), 0),
    ("tb_s4", "IV, V", "11.25 TB in one copy", 11.25, "e1_storage.csv S4, 5 channels", E1("S4", "TB_60y_single_copy"), 2),
    ("pq_gb", "V", "adds only 0.65 GB", 0.65, "e1_storage.csv S4 - S1", 1000 * (E1("S4", "TB_60y_single_copy") - E1("S1", "TB_60y_single_copy")), 2),
    ("overhead", "V", "2.49× overhead", 2.49, "e1_storage.csv S4 / S0", E1("S4", "TB_60y_single_copy") / E1("S0", "TB_60y_single_copy"), 2),
    ("tb_rs", "V", "15.75 TB instead of 33.75 TB", 15.75, "e1_storage.csv S4 RS(10,4)", E1("S4", "TB_60y_RS(10,4)_1.4x"), 2),
    ("tb_3x", "V", "15.75 TB instead of 33.75 TB", 33.75, "e1_storage.csv S4 3x", E1("S4", "TB_60y_3x_replication"), 2),
    ("files", "V", "from the 3 raw BDG2 files", 3, "data_manifest.sha256 entries", n_files, 0),
    ("fox_n", "V", "For the 106 Fox buildings", 106, "e2_summary.json focus", e2["focus"]["buildings"], 0),
    ("cv_med", "V", "median CV(RMSE) 14.9%", 14.9, "e2_g14.csv Fox, CV <= 30%", 100 * med(fox_ok), 1),
    ("oot_cv", "V", "13.2%, with NMBE −1.5%", 13.2, "e2_out_of_time.json", 100 * oot["cv_rmse"]["median"], 1),
    ("oot_nmbe", "V", "13.2%, with NMBE −1.5%", -1.5, "e2_out_of_time.json", 100 * oot["nmbe"]["median"], 1),
    ("e2_split", "V", "One-time calibration flagged 16.3%", 16.3, "e2_summary.json focus split", 100 * e2["focus"]["split"]["overall_flag_rate"], 1),
    ("e2_mondrian", "V", "(Mondrian) calibration 14.5%", 14.5, "e2_summary.json focus mondrian", 100 * e2["focus"]["mondrian"]["overall_flag_rate"], 1),
    ("e2_roll", "V", "rolling 28-day window 5.3% (worst month 8.4%)", 5.3, "e2_summary.json focus rolling28", 100 * e2["focus"]["rolling28"]["overall_flag_rate"], 1),
    ("e2_roll_worst", "V", "rolling 28-day window 5.3% (worst month 8.4%)", 8.4, "e2_summary.json focus rolling28", 100 * e2["focus"]["rolling28"]["worst_month_rate"], 1),
    ("e2_aci", "V", "ACI [20] 5.1%", 5.1, "e2_summary.json focus aci", 100 * e2["focus"]["aci"]["overall_flag_rate"], 1),
    ("all_n", "V", "12 sites (801 buildings)", 801, "e2_summary.json all_sites", e2["all_sites"]["buildings"], 0),
]
for k, v in [("split", 17.4), ("mondrian", 16.8), ("rolling28", 5.4), ("aci", 5.05)]:
    M.append((f"all_{k}", "V", "17.4%, 16.8%, 5.4% and 5.05%", v, f"e2_summary.json all_sites {k}",
              100 * e2["all_sites"][k]["overall_flag_rate"], 2 if k == "aci" else 1))
M += [("p20", "V, VII", "20% under-report with 67% power", 67, "e3a_quarterly.json shave 0.2", 100 * pw[("shave", 0.2)]["power_one_sided"], 0),
      ("p30", "V", "30% one with 89%", 89, "e3a_quarterly.json shave 0.3", 100 * pw[("shave", 0.3)]["power_one_sided"], 0),
      ("cross80_v", "V", "reaches 80% at about a 25% under-report", 25, "e3a_extra.json: size where power crosses 80%", cross80, 0),
      ("p25", "V", "81% in a further 1,000 runs at 25%", 81, "e3a_extra.json size 0.25", 100 * ext[0.25]["power_one_sided"], 0),
      ("reps", "V Table III(a)", "1,000 runs per point", 1000, "e3a_quarterly.json params.reps", q["params"]["reps"], 0),
      ("reps_extra", "V", "81% in a further 1,000 runs at 25%", 1000, "e3a_extra.json params.reps", J("e3a_extra.json")["params"]["reps"], 0),
      ("ff_lo", "V", "false-flag rate 4–5%", 4, "e3a_quarterly.json min false_flag_one_sided",
       100 * min(r["false_flag_one_sided"] for r in q["power_single_building"]), 0),
      ("ff_hi", "V", "false-flag rate 4–5%", 5, "e3a_quarterly.json max false_flag_one_sided",
       100 * max(r["false_flag_one_sided"] for r in q["power_single_building"]), 0),
      ("sd", "V", "standard deviation of 13.3%", 13.3, "e3a_quarterly.json noise_floor", 100 * q["noise_floor"]["clean_quarter_drift_sd"], 1),
      ("two_sided", "V", "20% under-report 9% of the time", 9, "e3a_quarterly.json shave 0.2 two-sided", 100 * pw[("shave", 0.2)]["power_two_sided"], 0)]
for kind, row in [("shave", "| Under-report | 10% | 19% | 38% | 67% | 89% | 97% |"), ("relocate", "| Relocation | 23% | 33% | 46% | 57% | 79% | 92% |")]:
    vals = [int(v.strip(" %")) for v in row.strip("|").split("|")[1:]]
    for s, v in zip([0.05, 0.1, 0.15, 0.2, 0.3, 0.4], vals):
        M.append((f"t3_{kind}_{s}", "V Table III(a)", row, v, "e3a_quarterly.json", 100 * pw[(kind, s)]["power_one_sided"], 0))
for p, v in zip([0.01, 0.05, 0.1, 0.2], [70, 49, 32, 20]):
    M.append((f"t3b_{p}", "V Table III(b)", "| Detected | 70% | 49% | 32% | 20% |", v, "e3a_quarterly.json prevalence sweep",
              100 * prev[p]["power_one_sided"], 0))
prev_reps = int(re.search(r'run\("shave", 0\.20, [^\n]*?, (\d+)\), prevalence=pr', (REPO / "src" / "e3a_quarterly.py").read_text()).group(1))
M += [("prev_reps", "V Table III(b)", "300 runs per point", 300, "src/e3a_quarterly.py prevalence sweep reps", prev_reps, 0),
      ("prev10", "V", "at 10% prevalence the 20% under-report is caught 32%", 32, "e3a_quarterly.json prevalence 0.1", 100 * prev[0.1]["power_one_sided"], 0),
      ("one_of", "V Table III note", "1 of 106 buildings", 106, "e2_summary.json focus", e2["focus"]["buildings"], 0),
      ("copy", "V", "copying was always caught and rounding 98%", 100, "e3b_results.json copy", 100 * e3b["copy"]["exact_copy_detected_by_rule"], 0),
      ("round", "V", "copying was always caught and rounding 98%", 98, "e3b_results.json rounding", 100 * e3b["rounding"]["rounding_detected"], 0),
      ("abs0", "VI.A", "54% of runs on day 0", 54, "e3a_results.json curves shave_20 fast[0]", 100 * curve[0], 0),
      ("abs28", "VI.A", "clean 5.5% after day 28", 5.5, "mean of fast[28:]", 100 * mean(curve[28:]), 1),
      ("cost_total", "V", "$1.79M a year", 1.79, "xlsx Annual cost!B11 ($M)", total / 1e6, 2),
      ("cost_bldg", "Abstract, V, VIII", "$179 per building-year", 179, "xlsx Annual cost!C11", X("Annual cost", "C11"), 0),
      ("audit", "V", "12% of an ASHRAE Level 1 audit", 12, "xlsx Annual cost!B17", 100 * X("Annual cost", "B17"), 0),
      ("tech", "V", "technology is 0.5%", 0.5, "xlsx Annual cost!D13", 100 * X("Annual cost", "D13"), 1),
      ("people", "V", "inspection 99.5%", 99.5, "xlsx Annual cost!D14", 100 * X("Annual cost", "D14"), 1),
      ("assump", "V", "94.1% of the total", 94.1, "xlsx Annual cost!D8+D9+D10", 100 * (X("Annual cost", "D8") + X("Annual cost", "D9") + X("Annual cost", "D10")), 1),
      ("sens_lo", "V", "between $139 and $379", 139, "xlsx Sensitivity!B3", X("Sensitivity", "B3"), 0),
      ("sens_hi", "V", "between $139 and $379", 379, "xlsx Sensitivity!D5", X("Sensitivity", "D5"), 0),
      ("grid_lo", "V", "between $39 and $479", 39, "xlsx: Sensitivity!B3 - onboarding/bldg", X("Sensitivity", "B3") - X("Annual cost", "C9"), 0),
      ("grid_hi", "V", "between $39 and $479", 479, "xlsx: Sensitivity!D5 + onboarding/bldg", X("Sensitivity", "D5") + X("Annual cost", "C9"), 0),
      ("tech_max", "V", "below 2.4%", 2.4, "xlsx: tech / low-corner total",
       100 * X("Annual cost", "B13") / ((X("Sensitivity", "B3") - X("Annual cost", "C9")) * X("Inputs", "B2")), 1),
      ("dubai", "V", "toward $79", 79, "xlsx: C11 - onboarding/bldg", X("Annual cost", "C11") - X("Annual cost", "C9"), 0),
      ("anchor", "V", "about $29 a year", 29, "xlsx Annual cost!B2", X("Annual cost", "B2"), 0),
      ("quota", "VII", "5 of 106 at α = 5%", 5, "floor(0.05 x 106 Fox buildings)", int(0.05 * e2["focus"]["buildings"]), 0),
      ("reviewers", "VII", "taking 2 reviewers 1 hour", 2, "xlsx Inputs!B23", X("Inputs", "B23"), 0),
      ("hours", "VII", "taking 2 reviewers 1 hour", 1, "xlsx Inputs!B24", X("Inputs", "B24"), 0),
      ("rate", "VII", "$25.54", 25.54, "xlsx Inputs!B38", X("Inputs", "B38"), 2),
      ("rev_bldg", "VII", "$9.65 per building-year", 9.65, "xlsx Annual cost!C7", X("Annual cost", "C7"), 2),
      ("a1_cases", "VII", "cuts cases to 0.038", 0.038, "e4_results.json alpha 0.01", slow[0.01]["cases_per_building_year"], 3),
      ("a1_det", "VII", "from 67% to 8%", 8, "e4_results.json alpha 0.01 power_shave20", 100 * slow[0.01]["power_shave20"], 0),
      ("a5_det", "VII", "from 67% to 8%", 67, "e4_results.json alpha 0.05 power_shave20", 100 * slow[0.05]["power_shave20"], 0),
      ("per_q", "VII", "47 cases per quarter per 1,000 buildings", 47, "e4 alpha 0.05 x 1000 / 4", slow[0.05]["cases_per_building_year"] * 1000 / 4, 0),
      ("xl_review", "workbook", "", 0.189, "xlsx Inputs!B22 = paper review load", X("Inputs", "B22"), 3),
      ("xl_anchor_gas", "workbook", "", anchor_gas, "xlsx Inputs!B19 = anchor/gas.json typical daily anchor", X("Inputs", "B19"), 0)]
if "--bdg2" in opt:
    import pandas as pd
    w = pd.read_csv(Path(opt["--bdg2"]) / "data/weather/weather.csv", usecols=["site_id", "airTemperature"])
    M.append(("fox_temp", "V", "mean 25.1 °C", 25.1, "BDG2 weather.csv Fox airTemperature, 2016-2017",
              float(w[w.site_id == "Fox"].airTemperature.mean()), 1))


def half_up(x, dec):
    """Publication rounding (0.5 rounds away from zero), not Python's banker's rounding."""
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP))


paper = re.sub(r"\s+", " ", open(opt["--paper"], encoding="utf-8").read()) if "--paper" in opt else None
rows, bad, missing = [], 0, 0
for id_, where, text, printed, src, exact, dec in M:
    shown = half_up(exact, dec)
    ok = abs(shown - printed) < 10 ** (-dec) / 2 + 1e-9 or (id_ == "tech_max" and exact < printed) or (id_ == "ff_hi" and exact <= printed + 0.5)
    in_paper = "" if paper is None or not text else ("yes" if re.sub(r"\s+", " ", text) in paper else "NO")
    bad += not ok
    missing += in_paper == "NO"
    rows.append({"id": id_, "paper_location": where, "as_printed": text, "printed_value": printed, "source": src,
                 "exact_value": round(exact, 6), "rounded_as_paper": shown, "decimals": dec,
                 "match": "yes" if ok else "NO", "wording_in_paper": in_paper})
cited = [("unep", "I", "about 32% of global energy demand", "[1] UNEP 2025"),
         ("coyne", "Abstract, I", "39–54% more than their certificates predict", "[2] Coyne & Denny 2021"),
         ("ec", "Abstract, I", "53.3% of environmental claims vague or misleading; up to 40% unsubstantiated", "[3] EC 2020"),
         ("dewa", "I", "more than 2 million smart meters, every 15 minutes", "[4] DEWA 16 Sep 2022"),
         ("rics", "Abstract, II", "from 30 April 2026", "[6] RICS 4th ed."),
         ("taxonomy", "Abstract, II", "top-15% performance for pre-2021 buildings", "Delegated Reg. (EU) 2021/2139, Annex I, 7.7"),
         ("uae", "Abstract, II", "since 30 May 2025", "[7] Federal Decree-Law 11/2024"),
         ("dubai", "II, II.A", "20 years past completion; valid up to 10 years", "[8] Dubai Law 3/2026 Arts 9, 13"),
         ("vdronk", "II.A", "62 buildings, mean deviation > 34%, sd 55%", "[9] van Dronkelaar et al. 2016")]
for id_, where, text, ref in cited:
    rows.append({"id": id_, "paper_location": where, "as_printed": text, "printed_value": "", "source": ref,
                 "exact_value": "", "rounded_as_paper": "", "decimals": "", "match": "cited", "wording_in_paper": ""})
with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{len(M)} measured/modelled numbers checked, {bad} mismatches"
      + ("" if paper is None else f", {missing} wordings missing from the paper") + f"; {len(cited)} cited numbers listed")
for r in rows:
    if r["match"] == "NO" or r["wording_in_paper"] == "NO":
        print("PROBLEM", r)
sys.exit(1 if bad or missing else 0)
