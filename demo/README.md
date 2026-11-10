# 03 · Demo

**[Launch the live DIYAR website](https://akedia-tokenize.github.io/Diyar-IBCOL2026/)**

The website is a guided exploration of historical, provenance-graded sustainability evidence. It is a research prototype, **not a live energy utility integration**.

| Visit | What to examine |
| --- | --- |
| **Home / Owner** | The claim, its supporting source records, and their provenance grades |
| **Lender** | A decision context and the residual trust assumptions |
| **Verify** | Independent checks on the actual published reference bytes |
| **Replay** | The same historical reporting period as known at different record-time cutoffs |
| **Explorer / Provenance** | Meter readings, evidence dependencies and proofs |
| **Results** | Experiment summaries and their limitations |

**What is simulated:** signer keys and demo issuer/installer trust pins. A correctly signed false measurement remains physically false: cryptography alone does not certify calibration or building location. The site also contains an optional Sepolia operator/checker workflow; local-EVM tests are not a mainnet deployment.

**Live website source stays in [`docs/`](../docs/)** because this is the configured GitHub Pages publishing folder. Important entry points: [index.html](../docs/index.html), [browser code](../docs/js/), [reference evidence](../docs/data/) and [anchor tools](../docs/anchor/).

For local preview, from the repository root:

```bash
python3 -m http.server 8000 --directory docs
```

Open `http://localhost:8000`. See [visual design](../architecture/ui-direction.md) and [developer notes](../architecture/developer-notes.md).