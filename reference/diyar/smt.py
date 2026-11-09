"""Sparse Merkle tree keyed by registered field identifier (depth 256).

Why sparse and keyed (whitepaper IV): one field can be disclosed without the record,
a required field that is absent has a non-membership proof, and the schema can grow
without re-keying.

Leaf  = H(0x00 || key || value_hash)        (value_hash = hash of the committed record)
Node  = H(0x01 || left || right)
Empty = default hash per height, starting from H(0x02)

The verifier ALWAYS recomputes the root from the claimed data along the path fixed by the
key. Every known verifier failure in the test vectors shares the opposite pattern: a root
was accepted without the claimed data being folded into it.
"""
from .crypto import EMPTY, LEAF, NODE, H

DEPTH = 256
DEFAULT = [H(EMPTY)]
for _ in range(DEPTH):
    DEFAULT.append(H(NODE, DEFAULT[-1], DEFAULT[-1]))


def key_of(field_id: str) -> int:
    return int.from_bytes(H(field_id.encode()), "big")


def leaf_hash(key: int, value_hash: bytes) -> bytes:
    return H(LEAF, key.to_bytes(32, "big"), value_hash)


class SMT:
    def __init__(self):
        self.nodes: dict[tuple[int, int], bytes] = {}

    def _get(self, h: int, prefix: int) -> bytes:
        return self.nodes.get((h, prefix), DEFAULT[h])

    def _set(self, h: int, prefix: int, v: bytes):
        if v == DEFAULT[h]:
            self.nodes.pop((h, prefix), None)
        else:
            self.nodes[(h, prefix)] = v

    def update(self, field_id: str, value_hash: bytes | None):
        """Set (or, with None, remove) the value committed under a field id."""
        k = key_of(field_id)
        cur = leaf_hash(k, value_hash) if value_hash is not None else DEFAULT[0]
        self._set(0, k, cur)
        p = k
        for h in range(DEPTH):
            sib = self._get(h, p ^ 1)
            cur = H(NODE, cur, sib) if p & 1 == 0 else H(NODE, sib, cur)
            p >>= 1
            self._set(h + 1, p, cur)

    @property
    def root(self) -> bytes:
        return self._get(DEPTH, 0)

    def prove(self, field_id: str) -> dict:
        """Compressed proof: a 256-bit mask of non-default siblings + those siblings."""
        k = key_of(field_id)
        mask, sibs = 0, []
        for h in range(DEPTH):
            s = self._get(h, (k >> h) ^ 1)
            if s != DEFAULT[h]:
                mask |= 1 << h
                sibs.append(s)
        return {"mask": mask, "siblings": sibs}


def _is_hash(x) -> bool:
    return isinstance(x, (bytes, bytearray)) and len(x) == 32


def verify(root: bytes, field_id: str, value_hash: bytes | None, proof: dict) -> bool:
    """Inclusion (value_hash given) or non-membership (value_hash None) against a root.

    Malformed input of any shape returns False and never raises (audit 2 Nov, P1-17): the mask
    must fit in 256 bits, carry exactly one sibling per set bit, and every hash must be 32 bytes.
    """
    try:
        mask, sibs = proof["mask"], proof["siblings"]
        if not isinstance(field_id, str) or not _is_hash(root):
            return False
        if value_hash is not None and not _is_hash(value_hash):
            return False
        if isinstance(mask, bool) or not isinstance(mask, int) or mask < 0 or mask >> DEPTH:
            return False
        if not isinstance(sibs, (list, tuple)) or len(sibs) != bin(mask).count("1"):
            return False
        if not all(_is_hash(s) for s in sibs):
            return False
        k = key_of(field_id)
        cur = leaf_hash(k, bytes(value_hash)) if value_hash is not None else DEFAULT[0]
        it = iter(sibs)
        p = k
        for h in range(DEPTH):
            s = bytes(next(it)) if (mask >> h) & 1 else DEFAULT[h]
            cur = H(NODE, cur, s) if p & 1 == 0 else H(NODE, s, cur)
            p >>= 1
        return cur == bytes(root)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def proof_size(proof: dict) -> int:
    return 32 + 32 * len(proof["siblings"])  # 256-bit mask + siblings
