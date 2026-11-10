# DIYAR

**Every number carries its evidence.**

DIYAR is a provenance-graded evidence layer for sustainability claims in buildings, developed by Team Akedia for **IBCOL 2026**. It links reported values to source records, records their residual trust assumptions, and supports independent verification and historical replay.

[**Explore the website**](https://akedia-tokenize.github.io/Diyar-IBCOL2026/) · [**Read the whitepaper (v2.7)**](paper/DIYAR%20whitepaper%20v2.7.pdf) · [**Reproduce the research**](reference/README.md)

> **Scope:** Research and reference implementation, not a live utility or accredited certification service. The published tests use reference data and simulated signing keys. A valid signature does not establish that a meter is physically installed where claimed.

## Start here

| You want to… | Open |
| --- | --- |
| Experience the interactive evidence explorer, verifier and replay | [Live website](https://akedia-tokenize.github.io/Diyar-IBCOL2026/) |
| Evaluate the science, architecture, assumptions and limitations | [Whitepaper v2.7 and annexes A–H](paper/DIYAR%20whitepaper%20v2.7.pdf) |
| Reproduce the Python reference run and E1–E4 experiments | [Reference implementation](reference/README.md) |
| Review what is implemented versus evaluated versus proposed | [Implementation status](project/implementation-status.md) |
| Understand why files are separated and where to make changes | [Repository map](project/repository-map.md) |
| Run the verifier, experiment reruns or local site | [Reproducibility guide](project/reproduce.md) |

## Repository map

```text
.
├── docs/                GitHub Pages site, browser-verifier assets, demo evidence
│   ├── index.html       Website entry point
│   ├── js/              Frontend, local verification, replay, visualization
│   ├── data/            Published reference evidence consumed by the site
│   └── anchor/          Browser anchor demonstration and operator tooling
├── paper/               Published IBCOL 2026 whitepaper PDF, v2.7
├── project/             Architecture, status, UX and maintenance documentation
├── reference/           Python implementation, experiments, proofs and tests
│   ├── diyar/           Evidence, cryptography, grading, gate and replay modules
│   ├── src/             E1–E4 experiment and reconciliation scripts
│   ├── tests/           Verification and regression tests
│   ├── anchor/          Solidity source and local EVM test harness
│   ├── results/         Current outputs plus explicitly preserved older runs
│   └── logs_2026-11-06/ Historical reproducibility/audit logs
├── scripts/             Repository-maintenance checks
└── .github/workflows/   Lightweight integrity and syntax CI
```

**Important:** `docs/` is the deployed GitHub Pages source, not the general writing folder. `project/` holds explanatory documentation. `reference/results/`, dated logs and historical prototypes are evidence artifacts, not temporary clutter. Do not move or regenerate them without updating their provenance records.

## What is implemented

The repository includes signed intake and installation bindings, provenance grading, bitemporal records, sparse-Merkle inclusion/non-membership proofs, a fast statistical watch gate, signed daily commitments, browser-side independent checks, and a Solidity anchor contract exercised on a **local EVM**.

The quarterly slow gate and E1–E4 experiments were evaluated offline; the consortium chain, distributed archival custody, zero-knowledge predicate proofs and inspector-content model remain design work. [See status detail](project/implementation-status.md).

The reference documentation reports 91 signed days from the three-building Fox/BDG2 run and 8/8 replay and 8/8 negative checks. Those are results reported by the project's own experiments, **not an independent certification by GitHub or by a third party**.

## Reproduce

To explore locally (from this repository's root):

```bash
python3 -m http.server 8000 --directory docs
# Open http://localhost:8000
```

To reproduce the Python measurements, download and verify the BDG2 inputs, then follow [the exact commands](project/reproduce.md). The site can show a local-EVM demonstration; an optional Sepolia check may contact public RPC endpoints, so the entire site is not strictly network-free.

## Versions, data and licensing

- **Paper:** v2.7, 10 Nov 2026, [PDF](paper/DIYAR%20whitepaper%20v2.7.pdf).
- **Reference implementation:** v2.1, with a reference run regenerated from raw BDG2 on 6 Nov 2026.
- **Website:** Aurora-style static UI with v5.2 CSS refinement layers; these names describe assets, not an official release tag.
- **Data:** Building Data Genome Project 2 (Miller et al., *Scientific Data*, 2020). The website includes published demo evidence; source dataset download instructions and checksums are in `reference/`.
- **Licensing:** The Solidity contract's own README identifies its license. Font license notices are in `docs/fonts/`. No repository-wide open-source license is asserted here.

See [release index](project/release-index.md), [contribution guidance](CONTRIBUTING.md) and [development notes](project/developer-notes.md).
