"""DIYAR-ref: a reference implementation of the DIYAR evidence layer (IBCOL 2026).

Layers: intake (grading) -> validation gate -> commitment (sparse Merkle tree, signed daily
root) -> bitemporal store -> independent replay. Every component is adopted, not invented;
this package exists so that the whitepaper's claims can be executed and checked.
"""
