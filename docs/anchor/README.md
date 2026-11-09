# DiyarAnchor: the public anchor of DIYAR's daily chain

DIYAR signs one sparse-Merkle root per day and chains the days:
`entry = SHA-256(0x20 || day || smtRoot || prev)`, with 32 zero bytes before the first day.
`DiyarAnchor.sol` holds that chain on Ethereum:

- it recomputes every entry itself, with the same rule as `diyar/ledger.py`;
- a new entry must cite the current head, so a fork reverts (Catena-style non-equivocation, enforced by contract logic);
- days must strictly increase, and only the deploying account (the single operator of phases 0 and 1) can write;
- each day's root is kept in contract state (`rootOf(day)`), not only in event logs, so one call checks a past day even where old receipts are pruned.

## Files

| File | What it is |
|---|---|
| `DiyarAnchor.sol` | the contract (MIT) |
| `DiyarAnchor.json` | solc 0.8.26 output: ABI, init code, runtime code, immutable positions, fingerprint |
| `compile.cjs` | compiles the source with the pinned solc and writes `DiyarAnchor.json` |
| `test.mjs` | 17 tests on an in-process EVM against `../data/ledger.json`; writes `gas.json` |
| `test-log.txt`, `gas.json` | the last test run and the measured gas |
| `encode.mjs`, `make_deploy.py`, `deploy-anchor.template.html` | build the operator tool from the ledger (`deploy-inputs.json`, `remix-arguments.txt`) |
| `e2e.mjs`, `mockchain.mjs` | end-to-end test: tool, wallet, nodes, 33 checks including tampered answers |
| `deploy.html` | operator tool: deploys the contract and anchors the 91 days from MetaMask |

## Reproduce the tests

```
cd anchor
npm ci
node compile.cjs
node test.mjs ../data/ledger.json
```

End-to-end test of the operator tool and the Verify page (offline: a mocked wallet and mocked
Sepolia nodes, both backed by the same in-process EVM; needs Playwright with Chromium):

```
node encode.mjs ../data/ledger.json
python -m http.server 8000 --directory ..      # in another terminal
node e2e.mjs http://127.0.0.1:8000 ./e2e-out
```

Measured on the local EVM (Cancun): deployment 427,275 gas; a typical daily anchor 58,929 gas;
all 91 days in one `anchorBatch` call 2,586,922 gas.

## Run it in the browser

The site's Verify page runs this contract on a local EVM inside the page (`js/anchor-local.js` in a worker, with
`js/vendor/ethereumjs-evm.js`, built from the pinned packages in `_dev/evm-bundle/`): it deploys the init code from
`DiyarAnchor.json`, anchors the 91 days of `data/ledger.json`, reads head, count and `rootOf` back, and tries a fork,
a rewritten day and an outside writer, each of which must revert. Gas is computed as a node would charge it and
equals the numbers above. Nothing leaves the page; this shows the contract's rules, not a public anchor.

## Deploy (operator only)

Serve the site folder over http (for example `python -m http.server`), open `anchor/deploy.html`
in a browser with MetaMask on Sepolia, and confirm the two transactions. The page refuses to send
on any chain other than Sepolia. It prints the deployment record; save it as `data/anchor.json`.

## Check

The site's Verify page reads `data/anchor.json` as a pointer only and asks a public Sepolia node for
the contract code, both transactions, the 91 `Anchored` events and the contract state, then compares
each value with `data/ledger.json` and with the compiled fingerprint in this folder.

## Limits

Sepolia ether has no value, so the testnet copy has no economic security. An anchor proves that a root
existed no later than its block time: the 2017 roots here were anchored in November 2026 to show the
mechanism, not their age. The design anchors once a day on Ethereum mainnet.
