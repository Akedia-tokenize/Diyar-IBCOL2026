"""Intake adapters. Each field is graded at arrival by the PATH it came through, not by how
plausible its value looks (whitepaper III.A). Implemented paths:

  signed meter         -> A1   each hourly reading signed by the device key; the device is
                               bound to a building by an installation record (grade B)
  authoritative feed   -> A2   value signed by the issuing authority (registry, weather service)
  owner upload         -> C+   document hash; custody ran through the beneficiary
  manual entry         -> C    nothing checkable

A reading whose signature fails is rejected, not downgraded: it is not evidence of anything.
"""
from datetime import date

from .crypto import H, canonical, ec_verify
from .records import make_record

ADAPTER_VER = "diyar-ref/0.1"


def reading_msg(device_id: str, field_id: str, hour: str, value: float) -> bytes:
    return canonical({"d": device_id, "f": field_id, "h": hour, "v": value})


class Meter:
    """A simulated smart meter: holds its own key and signs every reading it produces."""

    def __init__(self, device_id, key):
        self.device_id, self.key = device_id, key

    def emit(self, field_id, hours, values):
        return [{"h": h, "v": v, "sig": self.key.sign(reading_msg(self.device_id, field_id, h, v)).hex()}
                for h, v in zip(hours, values)]


def ingest_meter_day(field_id, readings, device_id, device_pk, *, valid_from, valid_to, tx_time,
                     binding_state, trusted_installers):
    """Intake V2: no A1 building measurement without an exact signed installation.

    The installer registry is an independent trust input. The published device
    list or the caller-supplied device_pk alone is NEVER an authorization.
    Empty or unsigned submissions are refused rather than graded A1.
    """
    from .binding import BindingError, BIND_V2, binding_for, validate_meter_record
    if valid_from != valid_to:
        raise BindingError("meter-day valid_from and valid_to must be the exact same day")
    cert_field, cert = binding_for(binding_state, field_id, device_id, device_pk,
                                   unit="kWh", trusted_installers=trusted_installers,
                                   known_at=tx_time)
    if not isinstance(readings, list) or not readings:
        raise BindingError("empty meter day is not authenticated evidence")
    kept, rejected = [], 0
    for r in readings:
        try:
            ok = ec_verify(device_pk, reading_msg(device_id, field_id, r["h"], r["v"]),
                           bytes.fromhex(r["sig"]))
        except (ValueError, TypeError, KeyError, AttributeError):
            ok = False
        if ok:
            kept.append(r)
        else:
            rejected += 1
    if not kept:
        raise BindingError("no valid signed meter readings")
    rec = make_record(field_id, kept, grade="A1",
                      adapter="diyar-ref/0.2/dlms-suite1-sim-bound-v2", unit="kWh",
                      valid_from=valid_from, valid_to=valid_to, tx_time=tx_time,
                      evidence={"device_id": device_id, "binding_cert_id": cert["certificate_id"],
                                "binding_sig_format": BIND_V2, "rejected_readings": rejected},
                      derived_from=[cert_field])
    if not validate_meter_record(binding_state, rec, trusted_installers=trusted_installers,
                                 expected_field=field_id):
        raise BindingError("meter evidence fails exact certificate binding")
    return rec


# Versioned feed claim signature. The domain separator is deliberately not valid JSON,
# preventing a signature from being replayed across DIYAR message families.
# Historic V1 signatures covered only {f,v}; do not use them for NEW intake.
FEED_V2 = "AUTH-FEED-V2"
FEED_V2_DOMAIN = b"DIYAR/AUTH-FEED/V2\x00"


def _day(value, *, optional=False):
    """Require canonical YYYY-MM-DD; do not silently normalize different strings."""
    if optional and value is None:
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("validity must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as err:
        raise ValueError("invalid validity date") from err
    if parsed.isoformat() != value:
        raise ValueError("validity must use canonical YYYY-MM-DD")
    return parsed


def authoritative_msg_v2(issuer_id, field_id, value, *, issuer_key_id, unit, valid_from, valid_to,
                         schema_ver="1.0"):
    """V2 issuer-signed semantic claim. tx_time is an operator observation time.

    The issuer controls field, value, exact unit, truth-validity range and issuer ID.
    tx_time cannot be signed at source issuance; it is committed by the ledger.
    A caller-supplied issuer_pk is NOT proof that a key is authorized for issuer_id.
    Deployments must pin this mapping in a trusted key registry.
    """
    for label, v in (("issuer_id", issuer_id), ("issuer_key_id", issuer_key_id), ("field_id", field_id), ("unit", unit),
                     ("schema_ver", schema_ver)):
        if not isinstance(v, str) or not v.strip() or any(ord(c) < 32 for c in v):
            raise ValueError(f"{label} must be a nonempty text identifier")
    if schema_ver != "1.0":
        raise ValueError("unsupported signed claim schema version")
    start, end = _day(valid_from), _day(valid_to, optional=True)
    if end is not None and start > end:
        raise ValueError("valid_to precedes valid_from")
    return FEED_V2_DOMAIN + canonical({
        "sig_format": FEED_V2, "issuer_id": issuer_id, "issuer_key_id": issuer_key_id,
        "audience": "DIYAR/provenance", "claim_schema": schema_ver,
        "field_id": field_id, "value": value, "unit": unit,
        "valid_from": valid_from, "valid_to": valid_to,
    })


def issue_signed(issuer_key, field_id, value, *, issuer_id, issuer_key_id, unit,
                 valid_from, valid_to, schema_ver="1.0"):
    """Sign a complete V2 claim; signature alone does not establish issuer authorization."""
    return issuer_key.sign(authoritative_msg_v2(
        issuer_id, field_id, value, issuer_key_id=issuer_key_id,
        unit=unit, valid_from=valid_from, valid_to=valid_to,
        schema_ver=schema_ver)).hex()


def verify_authoritative_v2(issuer_pk, sig_hex, issuer_id, field_id, value, *, issuer_key_id, unit,
                            valid_from, valid_to, schema_ver="1.0"):
    """Fail closed on malformed fields, signature encoding, or invalid key material."""
    try:
        msg = authoritative_msg_v2(issuer_id, field_id, value, issuer_key_id=issuer_key_id, unit=unit,
                                   valid_from=valid_from, valid_to=valid_to, schema_ver=schema_ver)
        return ec_verify(issuer_pk, msg, bytes.fromhex(sig_hex)) is True
    except (ValueError, TypeError, AttributeError):
        return False


def pinned_issuer_key(trusted_issuers, issuer_id, issuer_key_id):
    """Resolve a pinned key from trusted external configuration, never from the claim."""
    try:
        key = trusted_issuers[issuer_id][issuer_key_id]
        if isinstance(key, str):
            key = bytes.fromhex(key)
        return key if isinstance(key, bytes) and len(key) == 33 else None
    except (TypeError, KeyError, ValueError, AttributeError):
        return None


def ingest_authoritative(field_id, value, sig_hex, issuer_id, issuer_pk, *, issuer_key_id,
                         trusted_issuers, unit, valid_from, valid_to, tx_time, schema_ver="1.0"):
    """V2 ONLY. Requires an independently configured (issuer, key_id) -> key pin.

    Providing an arbitrary issuer public key does not establish an authority.
    In a real deployment trusted_issuers must be separately governed and authenticated.
    """
    expected_key = pinned_issuer_key(trusted_issuers, issuer_id, issuer_key_id)
    if expected_key is None or expected_key != issuer_pk:
        return None
    if not verify_authoritative_v2(expected_key, sig_hex, issuer_id, field_id, value,
                                   issuer_key_id=issuer_key_id, unit=unit,
                                   valid_from=valid_from, valid_to=valid_to, schema_ver=schema_ver):
        return None
    return make_record(field_id, value, grade="A2", adapter=f"{ADAPTER_VER}/feed-v2", unit=unit,
                       valid_from=valid_from, valid_to=valid_to, tx_time=tx_time, schema_ver=schema_ver,
                       evidence={"issuer": issuer_id, "issuer_key_id": issuer_key_id,
                                 "sig": sig_hex, "sig_format": FEED_V2})


def ingest_upload(field_id, document: bytes, summary, *, valid_from, valid_to, tx_time):
    return make_record(field_id, summary, grade="C+", adapter=f"{ADAPTER_VER}/upload",
                       valid_from=valid_from, valid_to=valid_to, tx_time=tx_time,
                       evidence={"doc_sha256": H(document).hex(), "uploaded_by": "owner"})


def ingest_manual(field_id, value, *, unit, valid_from, valid_to, tx_time):
    return make_record(field_id, value, grade="C", adapter=f"{ADAPTER_VER}/manual", unit=unit,
                       valid_from=valid_from, valid_to=valid_to, tx_time=tx_time,
                       evidence={"entered_by": "owner"})
