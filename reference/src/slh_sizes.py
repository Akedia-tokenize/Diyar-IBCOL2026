"""Measure real SLH-DSA (FIPS 205) signature and key sizes, and check sign/verify round-trips.

Uses the pure-Python `slh-dsa` package, so sizes are exact but timings are NOT representative
of a C implementation and are not reported.
"""
import json
import sys

import slhdsa

PARAMS = ["sha2_128s", "sha2_128f", "sha2_256s", "sha2_256f"]
msg = b"DIYAR daily root " + bytes(32)
out = {}
for name in PARAMS:
    p = getattr(slhdsa, name)
    kp = slhdsa.KeyPair.gen(p)
    sig = kp.sign_pure(msg)
    ok = kp.verify_pure(msg, sig)
    out[name] = {
        "signature_bytes": len(sig),
        "public_key_bytes": len(kp.pub.digest()),
        "verified": bool(ok),
    }
    print(name, out[name], flush=True)

json.dump(out, open(sys.argv[1], "w"), indent=2)
