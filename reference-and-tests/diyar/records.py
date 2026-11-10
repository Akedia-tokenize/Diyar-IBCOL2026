"""Graded records and the bitemporal store.

Every committed fact is a record with two times (whitepaper III.B, 'Replay is bitemporal'):
  valid_from / valid_to : when the fact was true of the building
  tx_time               : when the system learned it
A correction never edits a record; it appends a new version of the same field with a later
tx_time. So 'what did we know on date T' and 'what is true' are both answerable, and a 2036
replay of a 2026 output can be asked either question.
"""
import json
from datetime import date, datetime
from pathlib import Path

from .crypto import RECORD, H, canonical

# Table I of the whitepaper: grade -> residual trust assumption (never empty, including A1).
GRADES = ["A1", "A2", "A2-", "B", "B-", "C+", "C"]
RESIDUAL = {
    "A1": "where the device is",
    "A2": "correctness of the authoritative source",
    "A2-": "the notary",
    "B": "competence and independence of the third party",
    "B-": "the above, plus extraction",
    "C+": "chain of custody",
    "C": "everything",
}


class RecordValidationError(ValueError):
    """Record cannot be committed under the v1.1 canonical store profile."""


class ChronologyError(RecordValidationError):
    """An update would violate the strictly increasing per-field tx_time rule."""


def _canonical_tx_time(value: str) -> str:
    """Require UTC-naive ISO minute timestamps used by the signed v1.1 archive.

    Store.as_of/query rely on lexicographic ordering. Offsets, seconds and
    mixed representations are therefore rejected until a versioned, UTC-normalized
    wire format is introduced. The canonical profile is YYYY-MM-DDTHH:MM.
    """
    if not isinstance(value, str) or len(value) != 16:
        raise RecordValidationError("tx_time must use canonical YYYY-MM-DDTHH:MM")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError as exc:
        raise RecordValidationError("invalid tx_time calendar value") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M") != value:
        raise RecordValidationError("non-canonical tx_time")
    return value


def _canonical_valid_day(value, name: str) -> None:
    """Validate an optional, date-only validity bound (YYYY-MM-DD)."""
    if value is None:
        return
    if not isinstance(value, str) or len(value) != 10:
        raise RecordValidationError(f"{name} must be YYYY-MM-DD or None")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise RecordValidationError(f"invalid {name} calendar value") from exc
    if parsed.isoformat() != value:
        raise RecordValidationError(f"non-canonical {name}")


def weakest(grades) -> str:
    return max(grades, key=GRADES.index)


def make_record(field_id, value, *, grade, adapter, valid_from, valid_to, tx_time,
                evidence=None, derived_from=None, unit=None, schema_ver="1.0"):
    if grade not in GRADES and grade != "derived":
        raise RecordValidationError(f"unknown provenance grade: {grade!r}")
    return {
        "field": field_id, "value": value, "unit": unit, "grade": grade,
        "adapter": adapter, "schema_ver": schema_ver,
        "valid_from": valid_from, "valid_to": valid_to, "tx_time": tx_time,
        "evidence": evidence or {}, "derived_from": derived_from or [],
    }


def record_hash(rec: dict) -> bytes:
    return H(RECORD, canonical(rec))


class Store:
    """Append-only bitemporal store. Nothing is ever overwritten."""

    def __init__(self):
        self.versions: dict[str, list[dict]] = {}

    def add(self, rec: dict):
        """Commit only a well-formed version with a strictly later transaction time.

        The chronology guard MUST run under `python -O` as well. Rejected
        records leave Store.versions unchanged (including its set of fields).
        The valid-time interval may move backwards during a correction: only
        transaction time is monotonic. See test_store_chronology_p004.py.
        """
        if not isinstance(rec, dict):
            raise RecordValidationError("record must be a dict")
        field = rec.get("field")
        if not isinstance(field, str) or not field.strip():
            raise RecordValidationError("field must be a non-empty string")
        tx = _canonical_tx_time(rec.get("tx_time"))
        _canonical_valid_day(rec.get("valid_from"), "valid_from")
        _canonical_valid_day(rec.get("valid_to"), "valid_to")
        start, end = rec.get("valid_from"), rec.get("valid_to")
        if start is not None and end is not None and end < start:
            raise RecordValidationError(f"invalid validity interval for {field}")
        grade = rec.get("grade")
        if grade not in GRADES and grade != "derived":
            raise RecordValidationError(f"unknown provenance grade for {field}: {grade!r}")

        vs = self.versions.get(field)
        # Signed installation certificates and revocation events are immutable
        # even when the attacker supplies a later transaction timestamp.
        if vs and (field.startswith("certificates/") or field.startswith("revocations/")):
            raise RecordValidationError(f"immutable binding field already exists: {field}")
        if vs and not vs[-1]["tx_time"] < tx:
            raise ChronologyError(f"tx_time must strictly increase for {field}")
        self.versions.setdefault(field, []).append(rec)

    def as_of(self, tx_time: str) -> dict[str, dict]:
        """The state the system knew at tx_time: latest version of each field with tx <= T."""
        out = {}
        for f, vs in self.versions.items():
            known = [v for v in vs if v["tx_time"] <= tx_time]
            if known:
                out[f] = known[-1]
        return out

    def query(self, valid_at: str, known_at: str) -> dict[str, dict]:
        """Bitemporal query on both axes: for each field, the latest version recorded by
        `known_at` (transaction time) whose validity interval contains `valid_at`.
        Intervals are closed: valid_from <= valid_at <= valid_to; valid_to None means open.
        Dates compare as ISO strings, so 'YYYY-MM-DD' and 'YYYY-MM-DDTHH:MM' both work."""
        out = {}
        for f, vs in self.versions.items():
            hit = [v for v in vs if v["tx_time"] <= known_at
                   and (v["valid_from"] is None or v["valid_from"][:len(valid_at)] <= valid_at)
                   and (v["valid_to"] is None or valid_at[:len(v["valid_to"])] <= v["valid_to"])]
            if hit:
                out[f] = hit[-1]
        return out

    def dump(self, path: Path):
        with open(path, "w") as fh:
            for vs in self.versions.values():
                for v in vs:
                    fh.write(json.dumps(v, sort_keys=True, separators=(",", ":")) + "\n")

    @classmethod
    def load(cls, path: Path) -> "Store":
        s = cls()
        rows = [json.loads(line) for line in open(path)]
        for r in sorted(rows, key=lambda r: (r["field"], r["tx_time"])):
            s.add(r)
        return s
