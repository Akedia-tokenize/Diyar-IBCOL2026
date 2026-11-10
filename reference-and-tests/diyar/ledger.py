"""Commitment chain. Each day the state root of the sparse Merkle tree is hashed with the day
and the previous entry, then signed twice: ECDSA (interoperable today) and SLH-DSA-256s
(the 60-year horizon). Only ONE post-quantum signature per day for the whole system (E1).
The entry hash is what would be anchored to a public chain.
"""
from .crypto import ROOT, H, canonical, ec_verify, slh_verify


def entry_hash(day: str, smt_root: bytes, prev: bytes) -> bytes:
    return H(ROOT, day.encode(), smt_root, prev)


class Ledger:
    def __init__(self, ec_key, slh_key):
        self.ec_key, self.slh_key = ec_key, slh_key
        self.entries = []

    def commit(self, day: str, smt_root: bytes):
        prev = bytes.fromhex(self.entries[-1]["entry"]) if self.entries else b"\x00" * 32
        e = entry_hash(day, smt_root, prev)
        self.entries.append({
            "day": day, "smt_root": smt_root.hex(), "prev": prev.hex(), "entry": e.hex(),
            "ecdsa": self.ec_key.sign(e).hex(), "slh_dsa": self.slh_key.sign(e).hex(),
        })
        return self.entries[-1]


def verify_chain(entries, ec_pk: bytes, slh_param: str, slh_pk: bytes):
    """Returns (ok, first_bad_day)."""
    prev = b"\x00" * 32
    for en in entries:
        e = entry_hash(en["day"], bytes.fromhex(en["smt_root"]), prev)
        if (e.hex() != en["entry"] or en["prev"] != prev.hex()
                or not ec_verify(ec_pk, e, bytes.fromhex(en["ecdsa"]))
                or not slh_verify(slh_param, slh_pk, e, bytes.fromhex(en["slh_dsa"]))):
            return False, en["day"]
        prev = e
    return True, None


def canonical_ledger(entries) -> bytes:
    return canonical(entries)
