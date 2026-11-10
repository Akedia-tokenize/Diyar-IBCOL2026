"""E1 — Signature and storage overhead, measured on BDG2.

Answers the adjudicator's point that per-reading SLH-DSA signatures would dwarf the
88 GB/year raw-data figure. We:
  1. count the real number of metered channels per building in BDG2;
  2. encode one real building-year end to end (record -> device ECDSA signature ->
     daily Merkle root) and measure the bytes actually produced;
  3. take SLH-DSA signature sizes from a real sign/verify run (slh_sizes.json);
  4. compute storage per building-year and for the 10,000-building / 60-year reference
     scenario under five signing designs.

Usage: python3 e1_storage.py <bdg2_root> <slh_sizes.json> <out_dir>
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

BDG2, SLH_JSON, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)

METERS = ["electricity", "chilledwater", "steam", "hotwater", "gas", "water", "irrigation", "solar"]
READ_PER_DAY_15MIN = 96
DAYS = 365
BUILDINGS = 10_000
YEARS = 60

# --- canonical record: what one graded reading costs on disk -------------------------
# field_id(16) | valid_time(8) | transaction_time(8) | value(8) | grade(1) | schema_ver(2)
REC = struct.Struct(">16sqqdBH")
GRADE_A1 = 1


def field_id(building: str, meter: str) -> bytes:
    return hashlib.sha256(f"{building}/{meter}".encode()).digest()[:16]


def leaf(rec: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + rec).digest()          # domain-separated leaf


def node(a: bytes, b: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + a + b).digest()        # domain-separated node


def merkle_root(leaves: list[bytes]) -> bytes:
    level = leaves
    while len(level) > 1:
        if len(level) % 2:
            level = level + [hashlib.sha256(b"\x02").digest()]  # explicit padding, not duplication
        level = [node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


# --- 1. real channel counts --------------------------------------------------------------
frames = {}
for m in METERS:
    df = pd.read_csv(BDG2 / f"data/meters/cleaned/{m}_cleaned.csv", parse_dates=["timestamp"])
    frames[m] = df.set_index("timestamp")

channels = pd.Series(0, index=sorted(set().union(*[f.columns for f in frames.values()])))
for m, f in frames.items():
    has = f.notna().any()
    channels.loc[has[has].index] += 1
channels = channels[channels > 0]
ch_stats = {
    "buildings": int(len(channels)),
    "mean": round(float(channels.mean()), 3),
    "median": float(channels.median()),
    "p90": float(channels.quantile(0.9)),
    "max": int(channels.max()),
    "distribution": {int(k): int(v) for k, v in channels.value_counts().sort_index().items()},
}

# --- 2. one real building-year, encoded and signed end to end --------------------------
ref_b = channels.sort_values(ascending=False).index[0]        # building with most channels
year = slice("2016-01-01", "2016-12-31 23:59")
device_key = ec.generate_private_key(ec.SECP256R1())
records, sigs_raw, sigs_der = [], [], []
day_leaves: dict[str, list[bytes]] = {}
tx_time = int(pd.Timestamp("2017-01-01").timestamp())
for m, f in frames.items():
    if ref_b not in f.columns:
        continue
    s = f.loc[year, ref_b].dropna()
    fid = field_id(ref_b, m)
    for ts, v in s.items():
        rec = REC.pack(fid, int(ts.timestamp()), tx_time, float(v), GRADE_A1, 1)
        der = device_key.sign(rec, ec.ECDSA(hashes.SHA256()))
        r, s_ = decode_dss_signature(der)
        records.append(rec)
        sigs_der.append(len(der))
        sigs_raw.append(r.to_bytes(32, "big") + s_.to_bytes(32, "big"))
        day_leaves.setdefault(ts.strftime("%Y-%m-%d"), []).append(leaf(rec))

roots = {d: merkle_root(l) for d, l in sorted(day_leaves.items())}
measured = {
    "building": ref_b,
    "channels": int(channels[ref_b]),
    "readings_hourly_2016": len(records),
    "record_bytes": REC.size,
    "ecdsa_raw_bytes": len(sigs_raw[0]),
    "ecdsa_der_bytes_mean": round(float(np.mean(sigs_der)), 2),
    "raw_store_bytes": sum(len(r) for r in records),
    "signed_store_bytes": sum(len(r) for r in records) + sum(len(x) for x in sigs_raw),
    "daily_roots": len(roots),
    "example_root": next(iter(roots.values())).hex(),
}

# --- 3. SLH-DSA sizes from a real sign/verify run ---------------------------------------
slh = json.loads(SLH_JSON.read_text())
assert all(v["verified"] for v in slh.values()), "an SLH-DSA round-trip failed"
SLH_128S = slh["sha2_128s"]["signature_bytes"]
SLH_256S = slh["sha2_256s"]["signature_bytes"]

# --- 4. scenarios, per building-year at 15-minute resolution -------------------------
REC_B, ECDSA_B = REC.size, len(sigs_raw[0])


def per_building_year(c: float) -> dict[str, float]:
    n = READ_PER_DAY_15MIN * DAYS * c                          # readings per building-year
    raw = n * REC_B
    dev = n * ECDSA_B
    return {
        "S0 raw readings only": raw,
        "S1 raw + device ECDSA per reading": raw + dev,
        "S2 S1 + SLH-DSA-128s per reading": raw + dev + n * SLH_128S,
        "S3 S1 + SLH-DSA-256s per building per day": raw + dev + DAYS * SLH_256S,
        "S4 S1 + SLH-DSA-256s on one global daily root": raw + dev + DAYS * SLH_256S / BUILDINGS,
        "S5 raw + device ECDSA per channel-day + global 256s root":
            raw + DAYS * c * ECDSA_B + DAYS * SLH_256S / BUILDINGS,
    }


rows = []
for basis, c in [("BDG2 mean channels", ch_stats["mean"]), ("whitepaper assumption (5 channels)", 5)]:
    for name, b in per_building_year(c).items():
        fleet_year = b * BUILDINGS
        single60 = fleet_year * YEARS
        rows.append({
            "basis": basis, "channels": c, "scenario": name,
            "MB_per_building_year": b / 1e6,
            "GB_fleet_year": fleet_year / 1e9,
            "TB_60y_single_copy": single60 / 1e12,
            "TB_60y_3x_replication": 3 * single60 / 1e12,
            "TB_60y_RS(10,4)_1.4x": 1.4 * single60 / 1e12,
        })
table = pd.DataFrame(rows)
table.to_csv(OUT / "e1_storage.csv", index=False)

json.dump({"channels": ch_stats, "measured_building_year": measured,
           "slh_dsa": slh, "assumptions": {
               "resolution": "15 minutes (96/day); BDG2 itself is hourly",
               "record_format": "field_id16 | valid_time8 | tx_time8 | value8 | grade1 | schema_ver2",
               "device_signature": "ECDSA P-256, stored raw r||s",
               "buildings": BUILDINGS, "years": YEARS}},
          open(OUT / "e1_summary.json", "w"), indent=2)

pd.set_option("display.width", 200)
print(json.dumps(ch_stats, indent=1))
print(json.dumps(measured, indent=1))
print(table.round(2).to_string(index=False))
