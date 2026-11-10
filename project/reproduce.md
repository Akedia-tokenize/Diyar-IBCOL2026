# Reproducing DIYAR

Commands below assume a clone of this repository. They are instructions, **not a claim that these tests were rerun by the repository-organization change**.

## 1. Inspect the browser prototype

From the repository root:

```bash
python3 -m http.server 8000 --directory docs
```

Then open `http://localhost:8000`, use **Verify** and **Replay**, and inspect the published source data under `docs/data/`. The Verify page includes local checks; optional Sepolia verification contacts a public RPC node.

## 2. Prepare the Python environment

```bash
cd reference
python3 -m venv .venv
source .venv/bin/activate
python -m pip install numpy pandas cryptography slh-dsa==0.2.5
sh scripts/get_bdg2.sh data/bdg2
```

The project documents a test environment of Python 3.13.18, NumPy 2.5.3, pandas 3.0.5, cryptography 50.0.1 and slh-dsa 0.2.5. The raw BDG2 files are not bundled; the download script verifies SHA-256 hashes against the supplied manifest.

## 3. Replay and negative tests on the committed reference run

From `reference/`:

```bash
P=results/v2_run
python3 -I tests/test_replay.py "$P" --issuer-pins "$P/issuer_pins_DEMO_NOT_TRUSTED.json" --installer-pins "$P/installer_pins_DEMO_NOT_TRUSTED.json"
python3 -I tests/test_negative_v2.py "$P" --installer-pins "$P/installer_pins_DEMO_NOT_TRUSTED.json"
python3 -I tests/test_vectors.py
```

The pin files have deliberately alarming names: **they are not independent trust anchors**. A relying party must verify the relevant keys separately.

## 4. Recreate the reference data and research experiments

```bash
# Run from reference/
python3 -I run_pipeline.py data/bdg2 results/reproduced-v2

# Re-run E2–E4 in a separate output folder using a portable wrapper:
bash scripts/reproduce_e2_e4.sh data/bdg2 results/reproduced-e2-e4
```

The archived `logs_2026-11-06/rerun_e2_e4/run_all.sh` documents the **original historical execution** and contains machine-specific absolute paths. It is intentionally preserved unchanged. Use the portable script above for a new run.

For E1, E4, other experiments and paper-number reconciliation, use the exact published commands in [reference/README.md](../reference/README.md). The source paper used for current reconciliation is `reference/paper/DIYAR-whitepaper-v2.7.md`.

## 5. Contract local-EVM tests

```bash
cd reference/anchor
npm ci
node compile.cjs
node test.mjs ../results/v2_run/ledger.json
```

This tests the **local EVM** behavior, not the security of an Ethereum mainnet deployment. The reference documents 17 anchor tests.

## 6. Source integrity and repository layout

```bash
# From repository root
python3 scripts/check_repo_layout.py
python3 -m compileall -q reference/diyar reference/src reference/tests reference/run_pipeline.py
# Historical full-package manifest (inside reference/)
cd reference && sha256sum -c SHA256SUMS.txt
```

The lightweight repository check validates file presence, the two PDF copies, and local linked web assets. It is **not** a cryptographic or statistical audit.

The archived checksum manifest may need an explicit update if any file it covers is deliberately changed. Do not silently rehash historical evidence after a science-relevant edit.
