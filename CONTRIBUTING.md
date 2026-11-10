# Contributing to DIYAR

DIYAR is a research prototype with integrity-sensitive historical evidence. Contributions are welcome for review, but please preserve its scientific provenance.

- **Separate code from publication artifacts.** Make Python or Solidity changes under `reference/`; publish reviewed browser assets under `docs/`.
- **Do not hand-edit signed data or stored proofs.** Regenerate artifacts from source inputs, preserve old runs, and report changes to hashes, keys or claimed measurements.
- **Keep implementation status precise.** Distinguish built/tested components, offline experiments, local-EVM demos, testnet deployments and unbuilt designs.
- **Reproduce before claiming success.** Follow [the reproducibility guide](project/reproduce.md), describe your environment and include the relevant tests and outputs.
- **Protect privacy and licensing.** This repository is public; do not commit real credentials, personal building records, confidential documents or unauthorized datasets.
- **Avoid sweeping cleanup commits.** Results, checksum manifests and logs are part of the research record, not expendable cache.

For repository architecture and ownership, see [project/repository-map.md](project/repository-map.md). There is currently no declared repository-wide license; do not assume an unlicensed component is reusable under the same terms as a separately licensed contract.
