# anchor/: the DIYAR anchor contract

`DiyarAnchor.sol` holds DIYAR's daily chain on Ethereum. It keeps the chain head and each day's signed
sparse-Merkle root in contract state (`rootOf(day)`), recomputes every entry with the rule of
`diyar/ledger.py`, `entry = SHA-256(0x20 || day || smtRoot || prev)`, and reverts when an entry does
not cite the current head (a fork), when a day is not later than the last one (a rewrite), or when the
sender is not the operator. This is the non-equivocation rule of whitepaper section IV.

Status: built and tested on a local EVM; not deployed on a public network.

| File | What it is |
|---|---|
| `DiyarAnchor.sol` | the contract (MIT) |
| `compile.cjs` | compiles it with the pinned solc 0.8.26 (optimizer, 200 runs, Cancun) into `DiyarAnchor.json` |
| `DiyarAnchor.json` | ABI, init code, runtime code, immutable positions and the runtime fingerprint |
| `test.mjs` | 17 tests on @ethereumjs/vm 8.1.1 against the reference run's ledger; writes `gas.json` |
| `test-log.txt`, `gas.json` | the run of 8 Nov 2026 and the measured gas |

```
cd anchor
npm ci                                         # Node.js 18 or later; pinned solc and ethereumjs
node compile.cjs                               # reproduces DiyarAnchor.json byte for byte
node test.mjs ../results/v2_run/ledger.json    # 17 tests
```

The tests deploy the contract, check that `entryHash` reproduces all 91 ledger entries, anchor single
days and all 91 days in one `anchorBatch` call, read every root back from state, and show that a fork,
a non-increasing day and a second account are rejected with the head unchanged.

Measured gas (local EVM, Cancun): deployment 427,275; first anchor 92,575; typical daily anchor 58,929;
all 91 days in one batch 2,586,922. `DIYAR_cost_model.xlsx` (Inputs!B19) uses the typical daily anchor.

The prototype site runs the same compiled contract in the visitor's browser (Verify page) and contains an
operator page for a Sepolia testnet deployment; neither changes the status above.
