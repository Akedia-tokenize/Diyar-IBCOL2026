# DIYAR

**Every number carries its evidence.**  
A provenance-graded evidence layer for sustainability claims in the built environment. **Team Akedia · IBCOL 2026**.

[**Open the live demo**](https://akedia-tokenize.github.io/Diyar-IBCOL2026/) · [**Read the whitepaper (v2.7)**](paper/DIYAR%20whitepaper%20v2.7.pdf)

## Five sections of the project

| Section | What belongs here |
| --- | --- |
| **01 · [Paper](paper/)** | Six-page whitepaper v2.7 (10 Nov 2026) and annexes A–H. |
| **02 · [Architecture](architecture/)** | Evidence grades, architecture, implementation status, assumptions and limits. |
| **03 · [Demo](demo/)** | Guided tour of the deployed website: Owner, Lender, Verify, Replay and Explorer. |
| **04 · [Reference & Tests](reference-and-tests/)** | Python reference code, Solidity contract, replay tests, experiment scripts, historical logs and reproducibility tools. |
| **05 · [Results](results/)** | Selected E1–E4 outcomes, charts, detection boundaries and cost-model links. |

## IBCOL reviewer quickstart

1. Read [the paper](paper/DIYAR%20whitepaper%20v2.7.pdf) and the [verification model](architecture/verification-model.md).
2. Open [the demo](demo/) and try **Verify**, **Replay** and the **tamper demonstrations**.
3. Inspect [the results](results/) and [reproduce them](architecture/reproduce.md) using the source and test package.

The reference demonstration uses historical **Building Data Genome Project 2** measurements from three Fox-site buildings (1 January to 31 March 2017), simulated signer keys and demonstration-only trust pins. This is **not a live utility connection or accredited building assessment**. A valid signature verifies record integrity, not meter location or physical truth. The anchor is built/tested with a local EVM; a mainnet deployment is not claimed.

**Implementation status:** [Implemented / evaluated offline / designed](architecture/implementation-status.md) · [Version index](architecture/release-index.md).

## Repository layout

```text
paper/                 Paper v2.7 and annexes
architecture/          Architectural and technical documentation
demo/                  Demo navigation for reviewers
reference-and-tests/   Reference source, test harness and research records
results/               Curated, byte-identical research highlights
docs/                  GitHub Pages deployment files (technical exception)
.github/               Automated repository checks
```

**Why does `docs/` remain?** GitHub Pages serves the real demo source from that folder. Moving it would break the deployed site. The human-facing **Demo** section links directly to that original site and source instead of copying it. Full scientific results remain under `reference-and-tests/results/` to preserve the runnable package; the most important summaries and charts are also indexed in **Results**, with their bytes checked against the originals.

[Repository map](architecture/repository-map.md) · [Reproducibility guide](architecture/reproduce.md)

Source data credit: Building Data Genome Project 2, Miller et al., *Scientific Data* (2020). Third-party font license notices remain in `docs/fonts/`; the repository does not assert a project-wide open-source license.