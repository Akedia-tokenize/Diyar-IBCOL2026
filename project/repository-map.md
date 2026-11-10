# Repository map and file ownership

The repository is divided by **deployment purpose**, not by file extension.

## Source of truth

| Path | Purpose | Edit policy |
| --- | --- | --- |
| `paper/DIYAR whitepaper v2.7.pdf` | Publication artifact | Frozen for this version |
| `reference/paper/DIYAR-whitepaper-v2.7.md` | Machine-readable manuscript for numerical reconciliation | Update only with a new paper version and reconciliation |
| `reference/diyar/` | Core Python library | Source code, with tests |
| `reference/src/` | E1–E4 research and reconciliation scripts | Source code, with repeatable inputs |
| `reference/tests/` | Verifier regression and negative cases | Tests |
| `reference/anchor/` | Solidity contract and local EVM test harness | Contract source, compile and tests |
| `reference/DIYAR_cost_model.xlsx` | Cost-model input and computed figures | Financial model |
| `reference/results/v2_run/` | Published current reference-run evidence | Preserve; do not edit by hand |
| `reference/results/prototype/` | Preserved v1.1 historical run | Archive; do not overwrite |
| `reference/results/prototype_v1_2026-10-27/` | Preserved earliest run | Archive; do not overwrite |
| `reference/logs_2026-11-06/` | Historical re-run and test transcripts | Audit artifacts; immutable |
| `reference/SHA256SUMS.txt` | Existing checksums for the reference package | Historical manifest; keep in sync if changing listed files |
| `docs/` | GitHub Pages root and browser distribution | Deployment surface |
| `docs/data/` | Site-facing published reference artifacts | Generated/published evidence; never hand-edit |
| `docs/anchor/` | Site-facing contract and optional testnet operator tools | Browser distribution and build tools |
| `docs/reference-source.zip` | Downloadable research source package | Release asset; avoid manual editing |
| `project/` | Explanation, navigation and maintenance policy | Human-readable documentation |

## Why there are intentional duplicates

- `docs/whitepaper.pdf` and `paper/DIYAR whitepaper v2.7.pdf` are **byte-identical** in the checked repository revision. The first is a convenient website URL; the second is the canonical paper path for GitHub readers.
- `docs/anchor/` contains browser distribution and operator-tool files; `reference/anchor/` contains the scientific test harness. Similar filenames do **not** imply either folder is disposable.
- `docs/data/` is a browser-readable publication of reference-run data; `reference/results/` is the research provenance and test archive. Do not merge these folders based on filenames.

## Changes that require special care

1. If you change core cryptographic formats or evidence bytes, regenerate appropriate proofs and update tests and all dependent published artifacts in one reviewed change.
2. If you change paper numbers, re-run `reference/src/reconcile.py` and publish a versioned paper and reconciliation evidence.
3. If you change the website, preserve `docs/index.html` and its relative asset links because GitHub Pages serves this folder.
4. Preserve immutable historical datasets, logs, checksum manifests and earlier-version runs. Put new runs in separate directories.
5. Review privacy, data licensing and GitHub Pages visibility before publishing new raw data or personal information.
