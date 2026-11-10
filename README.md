# DIYAR

**Every number carries its evidence.**

A provenance graded evidence layer for sustainability claims in the built environment. IBCOL 2026, Team Akedia.

Every property is a story that lives; a certificate is one frame of it. DIYAR keeps the whole story checkable.

Buildings account for roughly a third of energy related CO2 emissions, so climate targets depend on claims about single buildings being true. Often they are not: certified efficient homes have been measured using 39 to 54% more energy than their certificates predict. What is missing is not data but provenance.

DIYAR grades every number by the path it arrived through, commits it under a signed daily root, and keeps every correction. Anyone can recheck the result on their own laptop.

## Open it

* **Website:** https://akedia-tokenize.github.io/Diyar-IBCOL2026/
* **Whitepaper:** [6 pages, with annexes A to H](paper/DIYAR%20whitepaper%20v2.7.pdf)
* **Reference implementation:** [reference](reference/)

## What is inside

| Folder | What it holds |
|---|---|
| docs | The website. Pick a role: building owner, lender or auditor. Every check runs in your browser. |
| reference | The reference implementation in Python, version 2.1: the pipeline, experiments E1 to E4, the cost model, and the anchor contract with its 17 tests. |
| paper | The whitepaper, 6 pages, with annexes A to H. |

## Check it yourself

1. Open the website and go to Verify.
2. Press Run independent checks. 11 checks run on the published bytes in about 5 seconds, including all 6,497 hourly meter signatures.
3. In the tamper lab, change a copy of the data and watch which check catches it.
4. Run the anchor contract in your browser: a fork, a rewritten day and an outside writer all revert.

Nothing leaves your browser.

To rerun everything from the raw data, follow [reference/README.md](reference/README.md). The replay checks pass 8 of 8, the negative checks pass 8 of 8, and the reconciliation compares the 112 numbers printed in the whitepaper with the code that produces them: 0 mismatches.

## What the reference run shows

| What we measured | Result |
|---|---|
| Signed days replayed from the published files | 91 of 91 |
| Alerts on 801 real buildings: one time calibration, then recent window calibration | 17.4%, then about 5% (target 5%) |
| One manipulated building among honest peers, tested each quarter | 80% detection at about a 25% underreport |
| Cost for 10,000 buildings, under stated assumptions | about $179 per building per year, nearly all of it people and physical inspection |

## Limits

This is a reference run, not a live system. It uses public meter data from 3 buildings of the Building Data Genome Project 2 (Fox site, 1 January to 31 March 2017), regenerated from the raw files on 6 November 2026. Signer keys are simulated and the trust pins are for the demo. The anchor contract is built and tested on a local EVM, not deployed on a public network.

We invented nothing. Every part of DIYAR is an established method; what is new is how a number is graded and how the parts hold together.

## Notes

* [Implementation status](docs/implementation-status.md)
* [Evidence grades and verification](docs/verification-model.md)
* [UI direction](docs/ui-direction.md)

## Credits

Meter and weather data: Building Data Genome Project 2, Miller et al., Scientific Data 7, 368 (2020). Fonts: Fraunces, Inter and IBM Plex Mono, under the SIL Open Font License.
