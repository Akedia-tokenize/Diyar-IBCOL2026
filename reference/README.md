# DIYAR-ref v2.1

Reference implementation and experiments for **DIYAR: A Provenance-Graded Evidence Layer for Sustainability Claims in the Built Environment** (IBCOL 2026, Team Akedia, IBCOL26IR-540820).

Everything here runs on public data. Every measured number in the whitepaper is produced by a script in this repository from the stated inputs; cost figures come from `DIYAR_cost_model.xlsx`. `src/reconcile.py` checks each printed number against its producer and against the paper text (`paper/DIYAR-whitepaper-v2.5.md`); the result is `reconciliation.csv`. `VERIFY_2026-11-06.md` records the independent re-runs.

## Install

```
pip install numpy pandas cryptography slh-dsa==0.2.5     # the PyPI name is slh-dsa; the module is slhdsa
```

Runs reported here: Python 3.13.18, numpy 2.5.3, pandas 3.0.5, cryptography 50.0.1, slh-dsa 0.2.5. The anchor contract tests in `anchor/` need Node.js 18 or later (`npm ci` installs the pinned solc 0.8.26 and @ethereumjs/vm 8.1.1).

## Data

[Building Data Genome Project 2](https://github.com/buds-lab/building-data-genome-project-2) (Miller et al., *Scientific Data*, 2020): hourly meter data for 1,636 non-residential buildings at 19 sites, 2016–2017. The primary test site is **Fox**, the hottest site in BDG2 (mean 25.1 °C, 95th percentile 39.4 °C, 32% of hours above 30 °C); it is cooler and drier than Dubai. No public building-level interval data for the Gulf was found.

`sh scripts/get_bdg2.sh data/bdg2` downloads the 3 files used here (`data/metadata/metadata.csv`, `data/weather/weather.csv`, `data/meters/cleaned/electricity_cleaned.csv`) and checks them against `data_manifest.sha256` (the same SHA-256 as the repository's LFS object ids).

## Prototype (`diyar/`, `run_pipeline.py`)

| Module | Whitepaper section | What it does |
|---|---|---|
| `intake.py` | III.A, IV | Grades each field by arrival path: device-signed meter readings (A1), signed authoritative claims (A2) whose signature covers field, value, unit, validity and issuer, checked against independently pinned issuer keys; owner uploads (C+); manual entry (C). Bad signatures are rejected. |
| `binding.py` | III.A, VI.A | Signed installation certificates bind each meter key to one building, channel and unit for a validity window, signed by a pinned installer key; revocations are signed too. A missing, revoked, conflicting or relabelled certificate fails closed. Grade B. |
| `trust.py` | III.A | Grade of each derived figure from the grades of its committed inputs; baselines trained on data not committed as signed records are graded C. |
| `records.py` | III.B | Bitemporal records (valid time + record time), append-only store, chronology enforced (no duplicate or out-of-order record times, also under `python -O`). |
| `baseline.py` | III.B | CalTRACK-style hourly baseline; accepted only under ASHRAE Guideline 14; committed before the period it judges. |
| `gate.py` | III.B, III.C | Rules, then a rolling 28-day split-conformal gate. Emits a flag and reasons; never decides. |
| `smt.py` | IV | Depth-256 sparse Merkle tree keyed by field id: inclusion, non-membership, selective disclosure. |
| `ledger.py` | IV | Daily state root chained and signed with ECDSA P-256 and SLH-DSA-256s (one post-quantum signature per day for the whole system). |
| `replay.py` | III.B, IV | Independent replay from published files only. |

```
python3 -I run_pipeline.py data/bdg2 results/v2_run          # 3 Fox buildings, Q1 2017 (about 5 min)
P=results/v2_run
python3 -I tests/test_replay.py $P --issuer-pins $P/issuer_pins_DEMO_NOT_TRUSTED.json \
    --installer-pins $P/installer_pins_DEMO_NOT_TRUSTED.json   # 8 replay checks
python3 -I tests/test_negative_v2.py $P --installer-pins $P/installer_pins_DEMO_NOT_TRUSTED.json   # 8 negative checks
python3 -I tests/test_vectors.py                             # verifier test vectors
for t in authoritative_v2 binding_v2 trust_p003 store_chronology_p004; do
    python3 -I tests/test_$t.py; python3 -I -O tests/test_$t.py; done   # 108 targeted tests, twice
python3 -I src/reconcile.py results DIYAR_cost_model.xlsx reconciliation.csv \
    --paper paper/DIYAR-whitepaper-v2.6.md --bdg2 data/bdg2   # 112 printed numbers vs producers
(cd anchor && npm ci && node compile.cjs && node test.mjs ../results/v2_run/ledger.json)   # anchor contract: 17 tests
```

The pin files are created by the same run and are **demo pins, not trust anchors**: a relying party must pin issuer and installer keys independently.

The run includes a 6-hour meter outage on 15 January, January reports published from the 4 February root, and a device-signed backfill on 20 February. Replay as of 4 February reproduces the published report hashes exactly; replay as of now differs only for the backfilled building.

`tests/test_vectors.py` reproduces 4 known verifier failures against naive verifiers (second preimage, duplicate leaf CVE-2012-2459, both-children proof as in BNB Bridge 2022, unbounded leaf index as in Hyperbridge 2026) and shows `diyar.smt` rejects each.

**Archive.** `results/prototype/` is the run of 2 November 2026 (v1.1), kept unchanged; the current code verifies it with `tests/test_replay.py results/prototype --allow-archived-v1` and `tests/test_negative.py results/prototype`. Its January numbers equal the reference run's; only the baseline and performance grades differ (C now). `results/prototype_v1_2026-10-27/` is the first run.

## Experiments (`src/`)

| Script | Question | Output |
|---|---|---|
| `slh_sizes.py`, `e1_storage.py`, `e1_figure.py` | E1: what do signatures cost in storage over 60 years? | `e1_*` |
| `e2_baselines.py`, `e2_conformal.py`, `e2_figure.py` | E2: does the gate keep its error rate across seasons? | `e2_*` |
| `e2_out_of_time.py` (input: `e3_fox_daily.npz`) | Do the frozen 2016 baselines hold on 2017, a year they never saw? (ASHRAE 14 acceptance itself is in-sample.) | `e2_out_of_time.json` |
| `e3_prepare.py`, `e3a_gates.py`, `e3a_quarterly.py`, `e3b_statistical.py`, `e3_figure.py` | E3: which injected manipulations are caught, and from what size? | `e3*` |
| `e3a_extra.py` | E3 at 20, 22.5, 25, 27.5 and 30% (new seed): where does detection reach 80%? | `e3a_extra.json` |
| `e4_review_budget.py` (input: `e3_fox_daily.npz`) | E4: how many review cases does each α open, and what detection does it buy? Replays `e3a_quarterly.py` draw for draw (seed 20261028). Review load counts **every** flagged case: the peer-rank test flags ⌊αn⌋ buildings per test, 0.189 per building-year at α = 5%. | `e4_results.json` |
| `reconcile.py` | Does every measured or modelled number printed in the whitepaper equal its producer's output, rounded as printed, and appear in the paper text? | `reconciliation.csv` |

E2–E4 were regenerated from the 3 raw BDG2 files on 6 November 2026: all 11 result files are byte-identical to the ones in `results/` (`logs_2026-11-06/rerun_e2_e4/COMPARE.txt`).

## Implementation status

| Component | Status |
|---|---|
| Signed intake (A1 device, A2 claims with unit and validity, C+ upload, C manual), grading at arrival | Implemented (simulated keys, demo pins) |
| Meter-to-building installation certificates and revocations (B), fail-closed | Implemented (simulated installer key) |
| Grade of derived figures from committed inputs; unsigned training data graded C | Implemented |
| Record chronology (duplicates, stale record times) enforced, also under `python -O` | Implemented |
| Rules: coverage on distinct in-period hours, plausibility range, unit and signature checks | Implemented |
| Other rule modes of Table II (clock drift, counters, registry match, bill checks, feed lag, completeness of 12 bills) | Designed, not built |
| Fast gate (rolling 28-day conformal), decision committed | Implemented |
| Slow gate (quarterly peer-rank test) | Evaluated offline on 106 Fox buildings (E3, E4); not integrated in the reference pipeline |
| Copy / rounding / deletion detectors | Evaluated offline (E3b) |
| Inspector-content model | Designed, not built |
| Sparse Merkle tree, inclusion and non-membership proofs, hardened verifier | Implemented, fuzz-tested |
| Daily root chained, signed ECDSA P-256 + SLH-DSA-256s | Implemented; 91/91 days verify |
| Bitemporal store: as-of (record time) and two-axis query (valid time x record time) | Implemented |
| Ethereum anchor contract with previous-root rule; gas | Built and tested on a local EVM (`anchor/`, 17 tests), not deployed; gas measured there |
| Besu / QBFT consortium | Designed, not deployed |
| RS(10,4) custody across custodians, key shares | Designed, not built |
| Predicate proofs without disclosure (e.g. consumption below a threshold) | Designed, not built; Merkle selective disclosure of exact values is implemented |

## Changes

**v2.1 (8 Nov 2026).** `anchor/` added: `DiyarAnchor.sol` (solc 0.8.26) keeps the chain head and each day's root in state, recomputes every entry with the ledger rule, and reverts on a fork, a non-increasing day or a second writer; 17 tests on @ethereumjs/vm against `results/v2_run/ledger.json`. Measured gas: deployment 427,275, typical daily anchor 58,929, all 91 days in one batch 2,586,922. The cost model uses the measured 58,929 gas instead of the event-only 25,000 estimate: anchoring $29.31 a year (was $12.43); total $1,785,795.12, still $178.58 per building-year. `reconcile.py` updated to the v2.6 whitepaper: 112 numbers, 0 mismatches; the workbook's gas input is checked against `anchor/gas.json`.

**V2 (5–7 Nov 2026).** Signed authoritative claims carry unit, validity and issuer and are checked against pinned keys; meters are bound to buildings by signed installation certificates with revocation, failing closed; derived grades follow committed inputs, so the 2016-trained baselines and the performance figures built on them are graded C; record chronology holds under `python -O`. 108 targeted tests. Reference run from raw BDG2 on 6 Nov: 91 days, 645 fields, 647 versions, gate 201 / 1 / 8 / 60, records 1.74 MB (larger because of signed envelopes and certificates), ledger 5.46 MB; replay 8/8, negative 8/8 (`tests/test_negative_v2.py`, with N7 rewritten for certificates). `e3a_extra.py` added. `reconcile.py` updated to the v2.5 whitepaper: 111 numbers, 0 mismatches, every wording found in the paper.

**v1.1 (2 Nov 2026), after the independent audit.**
- Coverage is measured against the calendar (24 x days in the month), weather coverage is reported separately, and a report says `complete`, `partial` or `insufficient`. Before: removing one day of weather left coverage at 1.0 (387,773.71 -> 374,879.55 kWh). After: metered energy and coverage unchanged, weather coverage 0.968, status `partial`.
- The coverage rule counts distinct in-period hours. Before: 24 copies of one hour passed. After: `coverage_ok` False, `duplicate_interval`.
- The proof verifier returns False on any malformed input. Before: a mask bit without a sibling raised `StopIteration`. After: 2,000 malformed proofs, zero crashes, zero false accepts.
- Building-level energy takes the weaker of the reading (A1) and the device-to-building binding (B). Before: always A1.
- `Store.query(valid_at, known_at)` answers both time axes; canonical encoding refuses NaN/Infinity.
- E4 added; BDG2 download script and SHA-256 manifest added; correct SLH-DSA package name in Install.
- `e2_out_of_time.py`: the frozen 2016 baselines scored on 2017 (daily): median CV(RMSE) 13.2%, median NMBE -1.5% over 106 Fox buildings.

## Known limits

Keys are simulated and the pins are generated by the run itself; the anchor contract runs only on a local EVM, so no root is posted on a public chain; meter signing follows DLMS/COSEM Security Suite 1 in spirit and must be checked against the Green Book before per-channel-day signing is claimed. Canonical JSON is deterministic within this implementation but is not yet an RFC 8785 (JCS) profile; cross-language test vectors are future work. Reading signatures cover device, field, hour and value, so a replayed reading cannot take a new timestamp and an old one falls out of period (negative check N4); there is no per-device sequence counter yet, and a key that signs wrong values is not caught by signatures at all (physical binding, whitepaper VI). Reports state when a required field is absent but do not attach the non-membership proof itself; replay check 7 produces one. See the whitepaper's register of what the design does not solve.
