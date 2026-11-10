"""P0-01 regression tests. P-256 is real; no SLH verification occurs in THIS suite.

If `slhdsa` is absent, an import-only placeholder is installed, because the shared
crypto module imports it unconditionally. PQ replay is tested separately with a
real OpenSSL verification backend, never a fake PASS.
"""
import copy
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

if importlib.util.find_spec("slhdsa") is None:
    sys.modules["slhdsa"] = types.ModuleType("slhdsa")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diyar import intake, replay  # noqa: E402
from diyar.crypto import ECKey, canonical  # noqa: E402
from diyar.records import record_hash  # noqa: E402
from diyar.smt import SMT, verify  # noqa: E402


class AuthoritativeFeedV2Tests(unittest.TestCase):
    def setUp(self):
        self.key = ECKey()
        self.evil = ECKey()
        self.pins = {"official-registry": {"authority-key-01": self.key.pk_bytes}}
        self.data = dict(
            field_id="building-17/floor_area", value=1000.0,
            issuer_id="official-registry", issuer_key_id="authority-key-01",
            unit="m2", valid_from="2017-01-01", valid_to="2017-12-31",
        )
        self.sig = intake.issue_signed(
            self.key, self.data["field_id"], self.data["value"],
            **{k: self.data[k] for k in ("issuer_id", "issuer_key_id", "unit", "valid_from", "valid_to")})
        self.ingest_args = dict(
            field_id=self.data["field_id"], value=self.data["value"], sig_hex=self.sig,
            issuer_id=self.data["issuer_id"], issuer_pk=self.key.pk_bytes,
            issuer_key_id=self.data["issuer_key_id"], trusted_issuers=self.pins,
            unit=self.data["unit"], valid_from=self.data["valid_from"],
            valid_to=self.data["valid_to"], tx_time="2017-01-02T09:00",
        )

    def signed(self, **changes):
        data = self.ingest_args.copy()
        data.update(changes)
        return intake.ingest_authoritative(**data)

    def test_01_valid_v2_record_has_explicit_version_and_A2(self):
        r = self.signed()
        self.assertIsNotNone(r)
        self.assertEqual(r["grade"], "A2")
        self.assertTrue(r["adapter"].endswith("/feed-v2"))
        self.assertEqual(r["evidence"]["sig_format"], intake.FEED_V2)
        self.assertEqual(r["evidence"]["issuer_key_id"], "authority-key-01")

    def test_02_unit_relabel_m2_to_kwh_rejected(self):
        self.assertIsNone(self.signed(unit="kWh"))
        self.assertIsNone(self.signed(unit="M2"))

    def test_03_validity_start_and_end_relabel_rejected(self):
        self.assertIsNone(self.signed(valid_from="2029-01-01"))
        self.assertIsNone(self.signed(valid_to="2030-01-01"))
        self.assertIsNone(self.signed(valid_to=None))

    def test_04_field_id_and_numeric_value_relabel_rejected(self):
        self.assertIsNone(self.signed(field_id="building-18/floor_area"))
        self.assertIsNone(self.signed(value=1000.1))

    def test_05_issuer_identity_and_key_rotation_id_are_signed(self):
        self.assertIsNone(self.signed(issuer_id="another-registry"))
        self.assertIsNone(self.signed(issuer_key_id="authority-key-02"))

    def test_06_no_issuer_pins_is_fail_closed(self):
        self.assertIsNone(self.signed(trusted_issuers=None))
        self.assertIsNone(self.signed(trusted_issuers={}))

    def test_07_fake_authority_pk_rejected_even_with_valid_ecdsa(self):
        # Attacker creates its own valid signature and claims official-registry.
        params = {k: self.data[k] for k in ("issuer_id", "issuer_key_id", "unit", "valid_from", "valid_to")}
        evil_sig = intake.issue_signed(self.evil, self.data["field_id"], self.data["value"], **params)
        self.assertIsNone(self.signed(sig_hex=evil_sig, issuer_pk=self.evil.pk_bytes))
        self.assertIsNone(self.signed(sig_hex=evil_sig, issuer_pk=self.key.pk_bytes))

    def test_08_bad_or_unknown_key_material_fails(self):
        self.assertIsNone(self.signed(issuer_pk=b"bad"))
        self.assertIsNone(self.signed(trusted_issuers={"official-registry": {"authority-key-01": self.evil.pk_bytes}}))
        self.assertIsNone(self.signed(sig_hex="zz"))
        self.assertIsNone(self.signed(sig_hex=""))

    def test_09_date_rejects_bad_formats_reverse_or_invalid(self):
        for date in ("2017-1-01", "2017-02-29", "2017/01/01", None, "2017-01-01T00:00"):
            with self.subTest(date=date):
                self.assertIsNone(self.signed(valid_from=date))
        self.assertIsNone(self.signed(valid_from="2020-01-01", valid_to="2017-12-31"))

    def test_10_nonfinite_values_and_missing_unit_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            self.assertIsNone(self.signed(value=value))
        for unit in ("", " ", None, "m2\nmalicious"):
            self.assertIsNone(self.signed(unit=unit))

    def test_11_replay_checks_metadata_not_just_value(self):
        r = self.signed()
        art = {"keys": {"issuers": {"official-registry": {"authority-key-01": self.key.pk_bytes.hex()}}, "devices": {}}}
        f = r["field"]
        self.assertEqual(replay.verify_evidence(art, {f: r}, trusted_issuers=self.pins), [])
        for label, value in (("unit", "kWh"), ("valid_from", "2018-01-01"),
                             ("valid_to", None), ("value", 1100.0)):
            bad = copy.deepcopy(r)
            bad[label] = value
            with self.subTest(label=label):
                self.assertEqual(replay.verify_evidence(art, {f: bad}, trusted_issuers=self.pins), [f])
        bad = copy.deepcopy(r)
        bad["evidence"]["issuer_key_id"] = "authority-key-02"
        self.assertEqual(replay.verify_evidence(art, {f: bad}, trusted_issuers=self.pins), [f])

    def test_20_schema_version_is_part_of_signed_meaning(self):
        old = self.signed()
        art = {"keys": {"issuers": {"official-registry": {
            "authority-key-01": self.key.pk_bytes.hex()}}, "devices": {}}}
        bad = copy.deepcopy(old)
        bad["schema_ver"] = "2.0"
        self.assertEqual(replay.verify_evidence(art, {old["field"]: bad}, trusted_issuers=self.pins), [old["field"]])
        self.assertIsNone(self.signed(schema_ver="2.0"))
        with self.assertRaises(ValueError):
            intake.issue_signed(self.key, self.data["field_id"], self.data["value"],
                  issuer_id=self.data["issuer_id"], issuer_key_id=self.data["issuer_key_id"],
                  unit=self.data["unit"], valid_from=self.data["valid_from"],
                  valid_to=self.data["valid_to"], schema_ver="2.0")

    def test_12_replay_without_pinned_registry_does_not_trust_self_published_key(self):
        r = self.signed()
        art = {"keys": {"issuers": {"official-registry": {"authority-key-01": self.key.pk_bytes.hex()}}, "devices": {}}}
        self.assertEqual(replay.verify_evidence(art, {r["field"]: r}), [r["field"]])
        wrong = {"official-registry": {"authority-key-01": self.evil.pk_bytes}}
        self.assertEqual(replay.verify_evidence(art, {r["field"]: r}, trusted_issuers=wrong), [r["field"]])

    def test_13_v1_signature_rejected_at_v2_intake(self):
        old_sig = self.key.sign(canonical({"f": self.data["field_id"], "v": self.data["value"]})).hex()
        self.assertIsNone(self.signed(sig_hex=old_sig))

    def test_14_unknown_feed_adapter_cannot_escape_a2_audit(self):
        rec = self.signed()
        rec["adapter"] = "diyar-ref/0.2/feed-v3"
        art = {"keys": {"issuers": {"official-registry": {"authority-key-01": self.key.pk_bytes.hex()}}, "devices": {}}}
        self.assertEqual(replay.verify_evidence(art, {rec["field"]: rec}, trusted_issuers=self.pins), [rec["field"]])

    def test_15_explicit_legacy_mode_only_for_anchored_archive(self):
        art = replay.load(Path(__file__).resolve().parents[1] / "results" / "prototype")
        state = art["store"].as_of("2017-03-31T23:59")
        legacy_fields = [f for f, r in state.items() if r["adapter"].endswith("/feed")]
        self.assertGreater(len(legacy_fields), 50)
        untrusted_by_default = {f for f, rec in state.items()
                                if rec["adapter"].endswith("/feed")
                                or rec["adapter"].endswith("/installation")
                                or rec["adapter"].endswith("/dlms-suite1-sim")}
        self.assertEqual(set(replay.verify_evidence(art, state)), untrusted_by_default)
        self.assertEqual(replay.verify_evidence(art, state, allow_legacy_feed=True, allow_legacy_binding=True), [])
        # A signed historical root is a SEPARATE integrity gate; old metadata is NOT source-signed.
        ok, _ = replay.check_root(art, "2017-03-31T23:59")
        self.assertTrue(ok)
        st = copy.deepcopy(state)
        st[legacy_fields[0]]["unit"] = "maliciously changed"
        self.assertEqual(replay.verify_evidence(art, st, allow_legacy_feed=True, allow_legacy_binding=True), [])
        self.assertNotEqual(replay.state_root(st).hex(), art["ledger"][-1]["smt_root"])

    def test_16_v2_record_is_committed_and_provable(self):
        rec = self.signed()
        mt = SMT()
        mt.update(rec["field"], record_hash(rec))
        self.assertTrue(verify(mt.root, rec["field"], record_hash(rec), mt.prove(rec["field"])))
        r2 = copy.deepcopy(rec)
        r2["unit"] = "kWh"
        self.assertFalse(verify(mt.root, rec["field"], record_hash(r2), mt.prove(rec["field"])))

    def test_17_transaction_time_is_operator_committed_not_issuer_signed(self):
        # The source must NOT pre-sign the unknowable time of subsequent ingestion.
        later = self.signed(tx_time="2017-02-17T10:00")
        self.assertIsNotNone(later)
        self.assertNotEqual(record_hash(later), record_hash(self.signed()))

    def test_19_key_rotation_is_scoped_by_issuer_and_key_id(self):
        successor = ECKey()
        rotating = {"official-registry": {
            "authority-key-01": self.key.pk_bytes,
            "authority-key-02": successor.pk_bytes,
        }}
        params = {k: self.data[k] for k in ("issuer_id", "unit", "valid_from", "valid_to")}
        sig = intake.issue_signed(successor, self.data["field_id"], self.data["value"],
                                  issuer_key_id="authority-key-02", **params)
        good = self.signed(sig_hex=sig, issuer_pk=successor.pk_bytes,
                           issuer_key_id="authority-key-02", trusted_issuers=rotating)
        self.assertIsNotNone(good)
        self.assertIsNone(self.signed(sig_hex=sig, issuer_pk=self.key.pk_bytes,
                                      issuer_key_id="authority-key-02", trusted_issuers=rotating))
        art = {"keys": {"issuers": {"official-registry": {
            "authority-key-01": self.key.pk_bytes.hex(),
            "authority-key-02": successor.pk_bytes.hex(),
        }}, "devices": {}}}
        self.assertEqual(replay.verify_evidence(art, {good["field"]: good}, trusted_issuers=rotating), [])
        bad = copy.deepcopy(good)
        bad["evidence"]["issuer_key_id"] = "authority-key-01"
        self.assertEqual(replay.verify_evidence(art, {bad["field"]: bad}, trusted_issuers=rotating), [bad["field"]])

    def test_18_unpinned_publication_key_replacement_fails_replay(self):
        r = self.signed()
        bad_art = {"keys": {"issuers": {"official-registry": {"authority-key-01": self.evil.pk_bytes.hex()}}, "devices": {}}}
        self.assertEqual(replay.verify_evidence(bad_art, {r["field"]: r}, trusted_issuers=self.pins), [r["field"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
