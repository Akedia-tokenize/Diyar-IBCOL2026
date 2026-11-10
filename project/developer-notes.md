# Developer notes

## Keep the published site stable

The static site is deployed directly from `docs/` through GitHub Pages. `docs/index.html` imports the following CSS files **in order**:

1. `style.css`
2. `ui-v2.css`
3. `theme-v5.css`
4. `polish-v5-2.css`
5. `fixes-v5-2a.css`

These versioned layers are part of the current running design. Consolidating them is a separate tested refactor, **not** a safe cosmetic rename. The browser entry point is `docs/js/app.js` and local evidence assets are served from `docs/data/`.

## Evidence is not a mock UI decoration

- Never change a cryptographic result directly in a JSON file to make the interface display PASS.
- The website verifies source records and reference-run data; all observed vs simulated values must be accurately labeled.
- A broken or missing check must show a failure, not a success placeholder.
- Work on the source implementation and test fixtures first, then update the site publication.

## Code and data changes

- Python core logic: `reference/diyar/`.
- Research experiments and numerical reconciliation: `reference/src/`.
- Regression checks: `reference/tests/`.
- Solidity reference implementation and local-EVM tests: `reference/anchor/`.
- Static site: `docs/`.
- Protected historical artifacts: `reference/results/`, `reference/logs_2026-11-06/` and `reference/SHA256SUMS.txt`.

The two PDF copies are intentional; publishing a new paper requires updating the canonical PDF and the website-accessible copy. Do not change only one.

## Maintenance workflow

1. Start with [repository map](repository-map.md) and [version index](release-index.md).
2. Put proposed changes on a branch and describe which claims or file paths are affected.
3. Run the lightweight repository checks and appropriate project-specific tests.
4. Keep old results under their original names and write new results to a new destination.
5. Update documentation and numerical reconciliation with the corresponding source version.
6. Verify the GitHub Pages site, its linked assets, and browser-side checks before announcing a release.
