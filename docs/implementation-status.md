# DIYAR implementation status

Whitepaper version 2.6, 8 November 2026. Reference run of 6 November 2026.

## What is built and run

| Part | Status |
|---|---|
| Intake grading: A1 meter readings, A2 signed claims, B installation certificates, C+ uploads, C manual entry | Built, run on the reference data |
| Rules and a rolling 28 day conformal gate that flags and never decides | Built, run |
| Sparse Merkle tree of depth 256, one root a day | Built, run |
| Daily roots signed with ECDSA P256 and SLH DSA, each citing the day before | Built, run |
| Bitemporal append only store, replayable as known on any date | Built, run |
| Verifier in the browser, 11 checks on the published bytes | Built, in the website |
| Anchor contract on Ethereum, with each day's root kept in state | Built and tested on a local EVM, 17 tests; not deployed |

## What is evaluated offline

E1 custody sizing, E2 seasonal calibration on 801 buildings, E3 detection power and E4 review cost. Their outputs are in the website and in reference/results.

## What is designed, not built

Besu QBFT consortium, Reed Solomon RS(10,4) custody across at least 4 custodians, threshold key shares, zero knowledge predicate proofs, a learned inspector model and public randomness draws.

## Reference results

| Result | Value |
|---|---|
| Signed days | 91 |
| Fields and versions | 645 and 647 |
| Records and ledger | 1.74 MB and 5.46 MB |
| Gate outcomes | 201 pass, 1 rule flag, 8 conformal flags, 60 calibrating |
| Replay checks and negative checks | 8 of 8 and 8 of 8 |
| Targeted tests | 108 |
| Numbers in the whitepaper checked against the code that produces them | 112, 0 mismatches |
| Detection of one manipulated building among honest peers | 80% at about a 25% underreport |
| Anchoring at the measured 58,929 gas a day | about $29 a year for the whole system |
| Cost | about $179 per building per year |

Signer keys are simulated and the pins are for the demo. The whitepaper is submitted to IBCOL 2026 and is not published here.
