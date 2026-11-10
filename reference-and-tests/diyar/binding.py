"""P0-02: signed, installer-trusted, time-scoped device-to-building bindings.

A source's meter signature authenticates a reading for one device key, NOT the
physical location of that device. The location assertion comes from a separate
accredited installer's signed certificate (grade B; residual installer trust).

The trusted_installers map MUST be pinned by an independent relying party,
never simply read from operator-published artefacts. All checks fail closed.
"""
from __future__ import annotations

from datetime import date, datetime

from .crypto import canonical, ec_verify
from .records import make_record

BIND_V2 = "METER-BIND-V2"
BIND_DOMAIN = b"DIYAR/METER-BIND/V2\x00"
REVOKE_V2 = "METER-BIND-REVOKE-V2"
REVOKE_DOMAIN = b"DIYAR/METER-BIND-REVOKE/V2\x00"


class BindingError(ValueError):
    """A binding cannot be relied upon for a building-level financial claim."""


def _id(value, label):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise BindingError(f"{label}: nonempty printable text required")
    return value


def _iso_day(s, label="date", *, optional=False):
    if s is None and optional:
        return None
    if not isinstance(s, str) or len(s) != 10:
        raise BindingError(f"{label}: YYYY-MM-DD required")
    try:
        d = date.fromisoformat(s)
    except ValueError as e:
        raise BindingError(f"{label}: invalid date") from e
    if d.isoformat() != s:
        raise BindingError(f"{label}: noncanonical date")
    return d


def _key(pk):
    if not isinstance(pk, str) or len(pk) != 66:
        raise BindingError("public_key: compressed P-256 public key required")
    try:
        raw = bytes.fromhex(pk)
    except ValueError as e:
        raise BindingError("public_key: malformed hex") from e
    if raw[0] not in (2, 3):
        raise BindingError("public_key: invalid compressed point encoding")
    return raw


def trusted_key(trusted_installers, issuer_id, key_id):
    """Resolve independently configured issuer pin (not a self-published key)."""
    try:
        key = trusted_installers[issuer_id][key_id]
        if isinstance(key, str):
            key = bytes.fromhex(key)
        return key if isinstance(key, bytes) and len(key) == 33 and key[0] in (2, 3) else None
    except (TypeError, ValueError, KeyError, AttributeError):
        return None


def binding_claim(certificate_id, device_id, public_key, building_id, *,
                  channel, unit, location, valid_from, valid_to,
                  installer_id, installer_key_id, schema_ver="1.0"):
    for label, val in (("certificate_id", certificate_id), ("device_id", device_id),
                       ("building_id", building_id), ("channel", channel),
                       ("unit", unit), ("location", location),
                       ("installer_id", installer_id), ("installer_key_id", installer_key_id)):
        _id(val, label)
    _key(public_key)
    if schema_ver != "1.0":
        raise BindingError("unsupported binding schema")
    start, end = _iso_day(valid_from, "valid_from"), _iso_day(valid_to, "valid_to", optional=True)
    if end is not None and start > end:
        raise BindingError("valid_to precedes valid_from")
    return {
        "sig_format": BIND_V2, "claim_schema": schema_ver,
        "audience": "DIYAR/meter-installation",
        "certificate_id": certificate_id, "device_id": device_id,
        "public_key": public_key, "building_id": building_id,
        "channel": channel, "unit": unit, "location": location,
        "valid_from": valid_from, "valid_to": valid_to,
        "installer_id": installer_id, "installer_key_id": installer_key_id,
        "status": "active",
    }


def sign_binding(installer_key, **kwargs):
    return installer_key.sign(BIND_DOMAIN + canonical(binding_claim(**kwargs))).hex()


def ingest_binding(certificate_id, device_id, public_key, building_id, *,
                   channel, unit, location, valid_from, valid_to,
                   installer_id, installer_key_id, signature, trusted_installers,
                   tx_time, schema_ver="1.0"):
    """Grade B is contingent on independently pinned issuer and a verified cert.

    ``certificates/<ID>`` is immutable and unique, enabling old and new device
    bindings to coexist without destroying historical as-of replay.
    """
    claim = binding_claim(certificate_id, device_id, public_key, building_id,
                          channel=channel, unit=unit, location=location,
                          valid_from=valid_from, valid_to=valid_to,
                          installer_id=installer_id, installer_key_id=installer_key_id,
                          schema_ver=schema_ver)
    pk = trusted_key(trusted_installers, installer_id, installer_key_id)
    if not pk or not _verify_sig(pk, BIND_DOMAIN + canonical(claim), signature):
        raise BindingError("installation is not signed by a pinned independent installer")
    return make_record(f"certificates/{certificate_id}", claim, grade="B",
                       adapter="diyar-ref/0.2/installation-v2", valid_from=valid_from,
                       valid_to=valid_to, tx_time=tx_time, schema_ver=schema_ver,
                       evidence={"installer_id": installer_id, "installer_key_id": installer_key_id,
                                 "signature": signature, "sig_format": BIND_V2},
                       derived_from=[])


def _verify_sig(pk, msg, sig):
    try:
        if not isinstance(sig, str):
            return False
        return ec_verify(pk, msg, bytes.fromhex(sig)) is True
    except (ValueError, TypeError, AttributeError):
        return False


def verify_binding_record(field, rec, trusted_installers):
    try:
        if (not isinstance(rec, dict) or rec.get("grade") != "B" or
            rec.get("adapter") != "diyar-ref/0.2/installation-v2"):
            return False
        v = rec["value"]
        if not isinstance(v, dict):
            return False
        claim = binding_claim(v["certificate_id"], v["device_id"], v["public_key"], v["building_id"],
                              channel=v["channel"], unit=v["unit"], location=v["location"],
                              valid_from=v["valid_from"], valid_to=v["valid_to"],
                              installer_id=v["installer_id"], installer_key_id=v["installer_key_id"],
                              schema_ver=v["claim_schema"])
        if (claim != v or field != f"certificates/{v['certificate_id']}" or
            rec.get("valid_from") != v["valid_from"] or rec.get("valid_to") != v["valid_to"] or
            rec.get("schema_ver") != v["claim_schema"]):
            return False
        e = rec["evidence"]
        if (e.get("sig_format") != BIND_V2 or e.get("installer_id") != v["installer_id"] or
            e.get("installer_key_id") != v["installer_key_id"]):
            return False
        pk = trusted_key(trusted_installers, v["installer_id"], v["installer_key_id"])
        return pk is not None and _verify_sig(pk, BIND_DOMAIN + canonical(claim), e["signature"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def revocation_claim(certificate_id, revoked_from, installer_id, installer_key_id, schema_ver="1.0"):
    for k, v in (("certificate_id", certificate_id), ("installer_id", installer_id),
                 ("installer_key_id", installer_key_id)):
        _id(v, k)
    _iso_day(revoked_from, "revoked_from")
    if schema_ver != "1.0":
        raise BindingError("unsupported revocation schema")
    return {"sig_format": REVOKE_V2, "claim_schema": schema_ver,
            "audience": "DIYAR/meter-installation-revocation", "certificate_id": certificate_id,
            "revoked_from": revoked_from, "installer_id": installer_id,
            "installer_key_id": installer_key_id, "status": "revoked"}


def sign_revocation(installer_key, **kwargs):
    return installer_key.sign(REVOKE_DOMAIN + canonical(revocation_claim(**kwargs))).hex()


def ingest_revocation(certificate_id, revoked_from, *, installer_id, installer_key_id,
                      signature, trusted_installers, tx_time, schema_ver="1.0"):
    claim = revocation_claim(certificate_id, revoked_from, installer_id, installer_key_id, schema_ver)
    pk = trusted_key(trusted_installers, installer_id, installer_key_id)
    if not pk or not _verify_sig(pk, REVOKE_DOMAIN + canonical(claim), signature):
        raise BindingError("untrusted or unsigned revocation")
    return make_record(f"revocations/{certificate_id}", claim, grade="B",
                       adapter="diyar-ref/0.2/revocation-v2", valid_from=revoked_from,
                       valid_to=None, tx_time=tx_time, schema_ver=schema_ver,
                       evidence={"signature": signature, "installer_id": installer_id,
                                 "installer_key_id": installer_key_id, "sig_format": REVOKE_V2})


def verify_revocation_record(field, rec, trusted_installers):
    try:
        v = rec["value"]
        if not isinstance(v, dict):
            return False
        claim = revocation_claim(v["certificate_id"], v["revoked_from"],
                                 v["installer_id"], v["installer_key_id"], v["claim_schema"])
        e = rec["evidence"]
        pk = trusted_key(trusted_installers, v["installer_id"], v["installer_key_id"])
        return (rec.get("grade") == "B" and rec.get("adapter") == "diyar-ref/0.2/revocation-v2" and
                v == claim and field == f"revocations/{v['certificate_id']}" and
                rec.get("valid_from") == v["revoked_from"] and rec.get("valid_to") is None and
                rec.get("schema_ver") == v["claim_schema"] and e.get("sig_format") == REVOKE_V2 and
                e.get("installer_id") == v["installer_id"] and
                e.get("installer_key_id") == v["installer_key_id"] and
                pk is not None and _verify_sig(pk, REVOKE_DOMAIN + canonical(claim), e["signature"]))
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def meter_field(field, day=None):
    if not isinstance(field, str) or field.count("/elec/") != 1:
        raise BindingError("meter field must be building-id/elec/YYYY-MM-DD")
    building, actual_day = field.split("/elec/")
    _id(building, "building_id")
    _iso_day(actual_day, "measurement day")
    if day is not None and actual_day != day:
        raise BindingError("measurement day differs from signed record date")
    return building, actual_day


def _hour(h, expected_day):
    if not isinstance(h, str) or len(h) != 16:
        raise BindingError("hour must be YYYY-MM-DDTHH:00")
    try:
        d = datetime.strptime(h, "%Y-%m-%dT%H:%M")
    except ValueError as e:
        raise BindingError("invalid reading timestamp") from e
    if d.strftime("%Y-%m-%dT%H:%M") != h or h[:10] != expected_day or h[14:] != "00":
        raise BindingError("reading hour invalid or outside signed day")


def binding_for(state, field, device_id, device_pk, *, unit, trusted_installers,
                required_cert_id=None, known_at=None):
    """Resolve an EXACT non-conflicting certificate valid for this meter's day.

    Checks all installer-attested active certs for device AND building/channel;
    rejects any conflicting claim and an effective signed revocation. The caller
    must supply a bitemporal as-of state from the claimed reporting cutoff.
    """
    building, day = meter_field(field)
    if not trusted_installers:
        raise BindingError("no independently pinned installer registry")
    _id(device_id, "device_id")
    key_hex = device_pk.hex() if isinstance(device_pk, bytes) else device_pk
    _key(key_hex)
    active = []
    for cert_field, cert in state.items():
        if not cert_field.startswith("certificates/"):
            continue
        if not verify_binding_record(cert_field, cert, trusted_installers):
            raise BindingError("certificate with invalid trusted signature or metadata")
        claim = cert["value"]
        # A certificate first learned AFTER the measurement was committed must
        # not retroactively authenticate that prior intake.
        if known_at is not None and cert.get("tx_time", "") > known_at:
            continue
        if day < claim["valid_from"] or (claim["valid_to"] is not None and day > claim["valid_to"]):
            continue
        rev = state.get(f"revocations/{claim['certificate_id']}")
        if rev is not None:
            # Use the supplied reporting as-of snapshot for revocations, NOT
            # the original measurement's transaction time. A revocation learned
            # later can retrospectively disqualify an earlier measurement from a
            # current report, while the prior signed as-of report still replays.
            if not verify_revocation_record(f"revocations/{claim['certificate_id']}", rev, trusted_installers):
                raise BindingError("invalid signed revocation")
            if rev["value"]["installer_id"] != claim["installer_id"]:
                raise BindingError("revocation issuer differs from installation authority")
            if day >= rev["value"]["revoked_from"]:
                continue
        if claim["device_id"] == device_id or (claim["building_id"] == building and claim["channel"] == "electricity"):
            active.append((cert_field, claim))
    if len(active) != 1:
        raise BindingError(f"zero or conflicting active installation certificates ({len(active)})")
    cf, cert = active[0]
    if (cert["device_id"] != device_id or cert["public_key"].lower() != key_hex.lower() or
        cert["building_id"] != building or cert["channel"] != "electricity" or
        cert["unit"] != unit or
        (required_cert_id is not None and cert["certificate_id"] != required_cert_id)):
        raise BindingError("device, key, building, channel, unit or certificate ID mismatch")
    return cf, cert


def validate_meter_record(state, rec, *, trusted_installers, published_devices=None,
                          expected_field=None):
    """Verify that every reading is signature-bound to precisely the installed meter.

    No untrusted A1 record can be used in a financial report. Source signatures
    still cover (device_id, field, hour, reading). Unit comes from signed cert.
    """
    from .intake import reading_msg
    try:
        if (not isinstance(rec, dict) or rec.get("grade") != "A1" or
            rec.get("adapter") != "diyar-ref/0.2/dlms-suite1-sim-bound-v2" or
            rec.get("valid_from") != rec.get("valid_to")):
            return False
        field, day = rec["field"], rec["valid_from"]
        if expected_field is not None and field != expected_field:
            return False
        meter_field(field, day)
        ev = rec["evidence"]
        dev, cert_id = ev["device_id"], ev["binding_cert_id"]
        if ev.get("binding_sig_format") != BIND_V2:
            return False
        key = published_devices.get(dev) if published_devices is not None else None
        if isinstance(key, str):
            key = bytes.fromhex(key)
        if key is None:
            # Resolve the device key from the ONLY pinned installer's certificate.
            values = [r["value"]["public_key"] for f, r in state.items()
                      if f.startswith("certificates/") and isinstance(r.get("value"), dict)
                      and r["value"].get("certificate_id") == cert_id]
            if len(values) != 1:
                return False
            key = bytes.fromhex(values[0])
        binding_for(state, field, dev, key, unit=rec["unit"],
                    trusted_installers=trusted_installers, required_cert_id=cert_id,
                    known_at=rec.get("tx_time"))
        readings = rec["value"]
        if not isinstance(readings, list) or not readings:
            return False
        seen = set()
        for r in readings:
            _hour(r["h"], day)
            if r["h"] in seen:
                return False
            seen.add(r["h"])
            if not _verify_sig(key, reading_msg(dev, field, r["h"], r["v"]), r["sig"]):
                return False
        return True
    except (BindingError, KeyError, TypeError, ValueError, AttributeError):
        return False
