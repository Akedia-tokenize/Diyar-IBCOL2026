"""P0-03: conservative, auditable provenance for learned baselines.

A baseline fitted to uncommitted CSV data cannot acquire the grade of a
hypothetical signed meter or a hypothetical authoritative weather feed.
Its training-input hash proves reproducibility with those exact inputs, NOT
source authentication. A stronger grade requires individually referenced,
committed input records, evaluated at report time.
"""
from __future__ import annotations

from .crypto import H, canonical
from .records import GRADES, make_record, weakest

TRUST_PROTOCOL = "DIYAR-BASELINE-TRUST-V1"
UNVERIFIED_GRADE = "C"


class TrustError(ValueError):
    pass


def _grade(g):
    if g not in GRADES:
        raise TrustError(f"not a source trust grade: {g!r}")
    return g


def baseline_record(field_id, model, *, valid_from, tx_time, source_records=None,
                    source_payloads=None):
    """Create a baseline with explicit, non-upgradable provenance.

    source_records is a nonempty list of committed record snapshots, NOT grade
    claims supplied by callers. Their field IDs and record hashes become a
    committed manifest. A model trained outside the signed record ledger is
    conservatively C, even if its CSV bytes are reproducible.
    """
    from .baseline import model_version
    refs = []
    if source_records:
        for rec in source_records:
            if not isinstance(rec, dict) or not isinstance(rec.get("field"), str):
                raise TrustError("source_records must contain actual record snapshots")
            refs.append({"field": rec["field"], "record_hash": H(b"\x10", canonical(rec)).hex(),
                         "grade_at_fit": _grade(rec.get("grade"))})
        if len({r["field"] for r in refs}) != len(refs):
            raise TrustError("duplicate source record")
    source_digest = H(canonical(source_payloads)).hex() if source_payloads is not None else None
    grade = weakest([r["grade_at_fit"] for r in refs]) if refs else UNVERIFIED_GRADE
    evidence = {"trust_protocol": TRUST_PROTOCOL, "model_ver": model_version(model),
                "source_refs": refs, "external_training_sha256": source_digest,
                "source_status": "committed-record-snapshots" if refs else "unverified-external-training",
                "grade_rule": "weakest authenticated training input, no upgrades"}
    return make_record(field_id, model, grade=grade,
                       adapter="diyar-ref/0.3/temporal-engine-provenance-v1",
                       valid_from=valid_from, valid_to=None, tx_time=tx_time,
                       evidence=evidence, derived_from=[x["field"] for x in refs])


def baseline_grade(state, field_id, *, legacy_archival=False):
    """Re-evaluate training provenance from committed inputs (never trust a label).

    Archived reports use the explicit historical branch elsewhere; for new
    reports an absent/legacy provenance manifest can provide at most grade C.
    """
    rec = state.get(field_id)
    if not isinstance(rec, dict):
        raise TrustError("missing baseline")
    if legacy_archival:
        return _grade(rec["grade"]), "legacy-archive-not-regraded"
    ev = rec.get("evidence", {})
    if not isinstance(ev, dict) or ev.get("trust_protocol") != TRUST_PROTOCOL:
        return UNVERIFIED_GRADE, "legacy-or-absent-training-provenance"
    refs = ev.get("source_refs")
    if not isinstance(refs, list) or ev.get("grade_rule") != "weakest authenticated training input, no upgrades":
        raise TrustError("malformed baseline trust manifest")
    if ev.get("model_ver") != __model_version(rec["value"]):
        raise TrustError("baseline model version differs from trust manifest")
    if len({r.get("field") for r in refs if isinstance(r, dict)}) != len(refs):
        raise TrustError("ambiguous/duplicate training dependencies")
    if rec.get("derived_from") != [r.get("field") for r in refs]:
        raise TrustError("baseline dependency list disagrees with manifest")
    if not refs:
        if rec.get("grade") != UNVERIFIED_GRADE or ev.get("source_status") != "unverified-external-training":
            raise TrustError("unverified training may not be upgraded above C")
        return UNVERIFIED_GRADE, "unverified-external-training"
    grades = []
    from .records import record_hash
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("field"), str):
            raise TrustError("invalid source reference")
        src = state.get(ref["field"])
        if src is None or record_hash(src).hex() != ref.get("record_hash"):
            raise TrustError("training source missing or changed")
        grade = _grade(src.get("grade"))
        if grade != ref.get("grade_at_fit"):
            raise TrustError("training source grade changed")
        if src["field"] == field_id:
            raise TrustError("self-referential training data")
        grades.append(grade)
    derived = weakest(grades)
    if rec.get("grade") != derived or ev.get("source_status") != "committed-record-snapshots":
        raise TrustError("baseline grade improperly upgraded or downgraded")
    return derived, "source-record-hashes-match"


def __model_version(model):
    from .baseline import model_version
    return model_version(model)


def source_grade(state, field, *, default=None):
    rec = state.get(field)
    if rec is None:
        if default is None:
            raise TrustError(f"mandatory source record not present: {field}")
        return _grade(default)
    return _grade(rec.get("grade"))
