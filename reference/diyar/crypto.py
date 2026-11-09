"""Hashing, canonical encoding and the two signature schemes.

Domain separation (first byte of every hashed message) prevents a value of one kind from
being presented as another: 0x00 leaf, 0x01 internal node, 0x02 empty leaf, 0x10 record,
0x20 daily root, 0x30 replay output.
"""
import hashlib
import json

import slhdsa
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

LEAF, NODE, EMPTY, RECORD, ROOT, OUTPUT = b"\x00", b"\x01", b"\x02", b"\x10", b"\x20", b"\x30"


def H(*parts: bytes) -> bytes:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.digest()


def canonical(obj) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, floats as repr; NaN/Infinity refused.
    Same input -> same bytes within this implementation. A cross-language profile (RFC 8785 JCS)
    is the planned wire format; see README 'Known limits'."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


# --- ECDSA P-256 (devices, issuers, operator) ------------------------------------------
class ECKey:
    def __init__(self, sk=None):
        self.sk = sk or ec.generate_private_key(ec.SECP256R1())
        self.pk_bytes = self.sk.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint)

    def sign(self, msg: bytes) -> bytes:
        r, s = decode_dss_signature(self.sk.sign(msg, ec.ECDSA(hashes.SHA256())))
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")        # raw r||s, 64 bytes


def ec_verify(pk_bytes: bytes, msg: bytes, sig: bytes) -> bool:
    if len(sig) != 64:
        return False
    pk = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pk_bytes)
    der = encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big"))
    try:
        pk.verify(der, msg, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


# --- SLH-DSA (FIPS 205), long-horizon signature on the daily root -----------------------
class SLHKey:
    def __init__(self, param: str = "sha2_256s"):
        self.param = param
        self.kp = slhdsa.KeyPair.gen(getattr(slhdsa, param))
        self.pk_bytes = self.kp.pub.digest()

    def sign(self, msg: bytes) -> bytes:
        return self.kp.sign_pure(msg)


def slh_verify(param: str, pk_bytes: bytes, msg: bytes, sig: bytes) -> bool:
    pub = slhdsa.PublicKey.from_digest(pk_bytes, getattr(slhdsa, param))
    try:
        return bool(pub.verify_pure(msg, sig))
    except Exception:
        return False
