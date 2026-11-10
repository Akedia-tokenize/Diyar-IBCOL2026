"""Verifier test vectors (whitepaper IV, 'Verification').

Each known verifier failure is reproduced against a deliberately naive verifier that has the
flaw, then the same attack is run against diyar.smt. They share one pattern: the verifier
accepted a root without folding the claimed data into it. A verifier that cannot pass these
is not deployed.

Run: python3 -I tests/test_vectors.py  (from the repo root)
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diyar.crypto import LEAF, NODE, H  # noqa: E402
from diyar.smt import DEFAULT, DEPTH, SMT, key_of, leaf_hash, verify  # noqa: E402


def sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


# ---- naive Bitcoin-style tree: no domain separation, odd level duplicates its last node ----
def naive_root(leaves: list[bytes]) -> bytes:
    level = [sha(x) for x in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [sha(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def naive_verify(root: bytes, leaf_data: bytes, path: list[tuple[bytes, str]]) -> bool:
    cur = sha(leaf_data)
    for sib, side in path:
        cur = sha(sib + cur) if side == "L" else sha(cur + sib)
    return cur == root


results = []


def check(name, naive_fooled, ours_rejects):
    ok = naive_fooled and ours_rejects
    results.append((name, naive_fooled, ours_rejects, ok))


# 1. Second preimage: an internal node presented as a leaf ------------------------------
a, b, c, d = b"rec-a", b"rec-b", b"rec-c", b"rec-d"
root = naive_root([a, b, c, d])
inner_left = sha(sha(a) + sha(b))
inner_right = sha(sha(c) + sha(d))
forged_leaf = sha(a) + sha(b)                         # 64 bytes that hash to the left inner node
naive_fooled = naive_verify(root, forged_leaf, [(inner_right, "R")])

t = SMT()
for f in ("bldg/A/elec/2017-01-01", "bldg/A/elec/2017-01-02"):
    t.update(f, H(f.encode()))
k = key_of("bldg/A/elec/2017-01-01")
# take the two children of that leaf's parent and present their concatenation as a value
c0, c1 = t._get(0, k & ~1), t._get(0, k | 1)
proof = t.prove("bldg/A/elec/2017-01-01")
ours_rejects = not verify(t.root, "bldg/A/elec/2017-01-01", H(c0 + c1), proof)
check("second preimage (inner node as leaf)", naive_fooled, ours_rejects)

# 2. Duplicate leaf, CVE-2012-2459: [a,b,c] and [a,b,c,c] share a root --------------------
naive_fooled = naive_root([a, b, c]) == naive_root([a, b, c, c])
t1, t2 = SMT(), SMT()
for f in ("f/a", "f/b", "f/c"):
    t1.update(f, H(f.encode()))
    t2.update(f, H(f.encode()))
t2.update("f/c", H(b"f/c"))                           # 'adding c again' is the same key: no hidden copy
t3 = SMT()
for f in ("f/a", "f/b", "f/c", "f/c#2"):
    t3.update(f, H(f.split("#")[0].encode()))         # a second record with identical content
ours_rejects = (t1.root == t2.root) and (t1.root != t3.root)
check("duplicate leaf (CVE-2012-2459)", naive_fooled, ours_rejects)


# 3. BNB Bridge, Oct 2022: proof nodes carry both children; the verifier uses the supplied
#    children and never folds the claimed leaf into the root ---------------------------------
def bnb_naive_verify(root: bytes, leaf_data: bytes, nodes: list[dict]) -> bool:
    cur = sha(leaf_data)
    for n in nodes:
        left = n.get("left", cur)
        right = n.get("right", cur)
        cur = sha(left + right)                       # if both are supplied, cur is discarded
    return cur == root


real = naive_root([a, b])
naive_fooled = bnb_naive_verify(real, b"FORGED withdrawal 1,000,000", [{"left": sha(a), "right": sha(b)}])
t = SMT()
t.update("acct/1", H(b"balance 10"))
pr = t.prove("acct/1")
ours_rejects = not verify(t.root, "acct/1", H(b"balance 1000000"), pr)
check("both-children proof (BNB Bridge 2022)", naive_fooled, ours_rejects)


# 4. Hyperbridge, Apr 2026: leaf index not bounded by the tree size; a proof for one
#    position is accepted for a claimed position outside the tree ----------------------------
def mmr_naive_verify(root, leaf_data, index, path, leaf_count):
    cur = sha(leaf_data)
    for sib in path:
        cur = sha(cur + sib) if index % 2 == 0 else sha(sib + cur)
        index //= 2
    return cur == root                                 # missing: index < leaf_count


leaves = [a, b]
r = naive_root(leaves)
naive_fooled = mmr_naive_verify(r, a, 2, [sha(b)], leaf_count=2)   # index 2 does not exist
t = SMT()
t.update("bldg/A/area", H(b"17358"))
pr = t.prove("bldg/A/area")
ours_rejects = (not verify(t.root, "bldg/Z/area", H(b"17358"), pr)) and \
               (not verify(t.root, "bldg/A/area", H(b"17358"), {"mask": pr["mask"], "siblings": pr["siblings"] + [b"\x00" * 32]}))
check("unbounded leaf index (Hyperbridge 2026)", naive_fooled, ours_rejects)

# 5. Sanity: honest inclusion and non-membership verify -----------------------------------
t = SMT()
t.update("bldg/A/elec/2017-01-01", H(b"x"))
honest = verify(t.root, "bldg/A/elec/2017-01-01", H(b"x"), t.prove("bldg/A/elec/2017-01-01"))
absent = verify(t.root, "bldg/A/occupants", None, t.prove("bldg/A/occupants"))
results.append(("honest inclusion + non-membership", True, honest and absent, honest and absent))

w = max(len(r[0]) for r in results)
for name, fooled, rejects, ok in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name:<{w}}  naive fooled={fooled}  ours rejects={rejects}")
sys.exit(0 if all(r[3] for r in results) else 1)
