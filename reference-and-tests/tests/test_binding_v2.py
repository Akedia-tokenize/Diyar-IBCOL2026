"""P0-02 adversarial tests. All signing is genuine ECDSA P-256.

An absent slhdsa import is stubbed ONLY to import the crypto module. These
unit tests never use SLH; historical regression independently runs REAL OpenSSL.
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

from diyar import binding, intake, replay
from diyar.crypto import ECKey
from diyar.records import record_hash
from diyar.smt import SMT, verify

ROOT = Path(__file__).resolve().parents[1]
DAY = "2017-01-12"
B = "Fox_education_Wendell"
OTHER = "Fox_office_Joy"
FIELD = f"{B}/elec/{DAY}"


class MeterInstallationV2Tests(unittest.TestCase):
    def setUp(self):
        self.installer = ECKey()
        self.other_installer = ECKey()
        self.meter = ECKey()
        self.alien_meter = ECKey()
        self.pins = {"licenced-installer": {"k001": self.installer.pk_bytes}}
        self.fields = {
            "certificate_id": "certificate-001", "device_id": "meter-001",
            "public_key": self.meter.pk_bytes.hex(), "building_id": B,
            "channel": "electricity", "unit": "kWh", "location": "signed installation, main incomer",
            "valid_from": "2017-01-01", "valid_to": "2017-12-31",
            "installer_id": "licenced-installer", "installer_key_id": "k001"}
        self.install = self.make_install()
        self.state = {self.install["field"]: self.install}
        self.r = self.make_readings()

    def make_install(self, *, signed_by=None, **overrides):
        args = dict(self.fields)
        args.update(overrides)
        k = signed_by or self.installer
        args["signature"] = binding.sign_binding(k, **args)
        args["trusted_installers"] = self.pins
        args["tx_time"] = "2016-12-31T12:00"
        return binding.ingest_binding(**args)

    def make_readings(self, device_id="meter-001", key=None, field=FIELD, day=DAY):
        key = key or self.meter
        return intake.Meter(device_id, key).emit(field, [f"{day}T{h:02d}:00" for h in range(24)],
                                                  [50.0+h/10 for h in range(24)])

    def ingest(self, *, state=None, field=FIELD, device_id="meter-001", key=None,
               readings=None, valid_from=DAY, valid_to=DAY, tx_time="2017-01-12T23:30", pins=None):
        key = key or self.meter
        return intake.ingest_meter_day(field, self.r if readings is None else readings,
                                       device_id, key.pk_bytes, valid_from=valid_from,
                                       valid_to=valid_to, tx_time=tx_time,
                                       binding_state=self.state if state is None else state,
                                       trusted_installers=self.pins if pins is None else pins)

    def assertRejected(self, *args, **kwargs):
        with self.assertRaises(binding.BindingError):
            self.ingest(*args, **kwargs)

    def test_01_true_binding_accepts_24_signed_hours(self):
        v = self.ingest()
        self.assertEqual(v["grade"], "A1")
        self.assertEqual(v["unit"], "kWh")
        self.assertEqual(v["evidence"]["binding_cert_id"], "certificate-001")
        self.assertTrue(binding.validate_meter_record(self.state, v, trusted_installers=self.pins))

    def test_02_cert_issued_by_trusted_installer_is_B_not_A1(self):
        self.assertEqual(self.install["grade"], "B")
        self.assertTrue(binding.verify_binding_record(self.install["field"], self.install, self.pins))

    def test_03_no_cert_fails_closed(self):
        self.assertRejected(state={})

    def test_04_self_published_installer_key_is_not_trust(self):
        self.assertRejected(pins={})
        self.assertRejected(pins={"licenced-installer": {"k001": self.other_installer.pk_bytes}})

    def test_05_wrong_meter_device_id_cannot_borrow_cert(self):
        self.assertRejected(device_id="meter-000")

    def test_06_wrong_key_cannot_borrow_cert(self):
        self.assertRejected(key=self.alien_meter)

    def test_07_wrong_building_cannot_borrow_cert(self):
        alien_field = f"{OTHER}/elec/{DAY}"
        readings = self.make_readings(field=alien_field)
        self.assertRejected(field=alien_field, readings=readings)

    def test_08_unrelated_installed_meter_cannot_raise_grade(self):
        alien_cert = self.make_install(certificate_id="alien-001", device_id="alien-device",
                                       public_key=self.alien_meter.pk_bytes.hex(), building_id=B)
        st = {alien_cert["field"]: alien_cert}
        self.assertRejected(state=st)

    def test_09_two_active_meters_same_building_channel_conflict(self):
        alien = self.make_install(certificate_id="alien-002", device_id="alien-device",
                                  public_key=self.alien_meter.pk_bytes.hex(), building_id=B)
        st = dict(self.state)
        st[alien["field"]] = alien
        self.assertRejected(state=st)

    def test_10_same_device_bound_to_second_building_conflict(self):
        other = self.make_install(certificate_id="other-001", building_id=OTHER)
        st = dict(self.state)
        st[other["field"]] = other
        self.assertRejected(state=st)

    def test_11_tamper_building_in_cert_breaks_signature(self):
        st = copy.deepcopy(self.state)
        st[self.install["field"]]["value"]["building_id"] = OTHER
        self.assertRejected(state=st)

    def test_12_tamper_cert_device_pk_breaks_signature(self):
        st = copy.deepcopy(self.state)
        st[self.install["field"]]["value"]["public_key"] = self.alien_meter.pk_bytes.hex()
        self.assertRejected(state=st)

    def test_13_tamper_cert_valid_from_breaks_signature(self):
        st = copy.deepcopy(self.state)
        st[self.install["field"]]["value"]["valid_from"] = "2016-01-01"
        self.assertRejected(state=st)

    def test_14_tamper_cert_unit_breaks_signature(self):
        st = copy.deepcopy(self.state)
        st[self.install["field"]]["value"]["unit"] = "Wh"
        self.assertRejected(state=st)

    def test_15_wrong_channel_or_unit_refused(self):
        wrong = self.make_install(channel="gas", unit="kWh")
        self.assertRejected(state={wrong["field"]: wrong})
        wrong = self.make_install(channel="electricity", unit="Wh")
        self.assertRejected(state={wrong["field"]: wrong})

    def test_16_expired_cert_does_not_authorize_2017_readings(self):
        expired = self.make_install(valid_to="2017-01-11")
        self.assertRejected(state={expired["field"]: expired})

    def test_17_future_cert_does_not_authorize_2017_readings(self):
        future = self.make_install(valid_from="2017-01-13")
        self.assertRejected(state={future["field"]: future})

    def test_18_retrospectively_uploaded_install_cannot_authenticate_older_intake(self):
        st = copy.deepcopy(self.state)
        st[self.install["field"]]["tx_time"] = "2017-01-13T00:00"
        self.assertRejected(state=st)

    def test_19_valid_revocation_blocks_at_effective_date(self):
        fields = dict(certificate_id="certificate-001", revoked_from="2017-01-12",
                      installer_id="licenced-installer", installer_key_id="k001")
        sig = binding.sign_revocation(self.installer, **fields)
        rev = binding.ingest_revocation(**fields, signature=sig,
                                        trusted_installers=self.pins, tx_time="2017-01-11T08:00")
        st = dict(self.state)
        st[rev["field"]] = rev
        self.assertRejected(state=st)
        cf, _ = binding.binding_for(st, f"{B}/elec/2017-01-11", "meter-001", self.meter.pk_bytes,
                                    unit="kWh", trusted_installers=self.pins,
                                    known_at="2017-01-11T23:59")
        self.assertEqual(cf, self.install["field"])

    def test_20_tampered_revocation_fails_closed(self):
        fields = dict(certificate_id="certificate-001", revoked_from="2017-01-12",
                      installer_id="licenced-installer", installer_key_id="k001")
        sig = binding.sign_revocation(self.installer, **fields)
        rev = binding.ingest_revocation(**fields, signature=sig,
                                        trusted_installers=self.pins, tx_time="2017-01-11T08:00")
        rev["value"]["revoked_from"] = "2017-01-20"
        st = dict(self.state)
        st[rev["field"]] = rev
        self.assertRejected(state=st)

    def test_21_fake_revocation_issuer_rejected(self):
        fields = dict(certificate_id="certificate-001", revoked_from="2017-01-12",
                      installer_id="licenced-installer", installer_key_id="k001")
        sig = binding.sign_revocation(self.other_installer, **fields)
        with self.assertRaises(binding.BindingError):
            binding.ingest_revocation(**fields, signature=sig,
                                      trusted_installers=self.pins, tx_time="2017-01-11T08:00")

    def test_22_intake_does_not_accept_empty_or_fully_corrupt_day(self):
        self.assertRejected(readings=[])
        self.assertRejected(readings=[dict(h=self.r[0]["h"],v=10000.0,sig=self.r[0]["sig"])])

    def test_23_meter_hour_out_of_period_fails(self):
        wrong = self.make_readings(day="2017-01-13", field=FIELD)
        self.assertRejected(readings=wrong)

    def test_24_duplicate_hour_fails(self):
        wrong = self.r.copy()+[self.r[0]]
        self.assertRejected(readings=wrong)

    def test_25_meter_value_tamper_invalidates_evidence(self):
        rec = self.ingest()
        rec["value"][3]["v"] += 1
        self.assertFalse(binding.validate_meter_record(self.state,rec,trusted_installers=self.pins))

    def test_26_meter_record_unit_tamper_is_rejected(self):
        rec = self.ingest()
        rec["unit"] = "Wh"
        self.assertFalse(binding.validate_meter_record(self.state,rec,trusted_installers=self.pins))

    def test_27_meter_record_cert_id_tamper_is_rejected(self):
        rec = self.ingest()
        rec["evidence"]["binding_cert_id"] = "alien-001"
        self.assertFalse(binding.validate_meter_record(self.state,rec,trusted_installers=self.pins))

    def test_28_meter_record_field_relabel_is_rejected(self):
        rec = self.ingest()
        rec["field"] = f"{OTHER}/elec/{DAY}"
        self.assertFalse(binding.validate_meter_record(self.state,rec,trusted_installers=self.pins))

    def test_29_snapshot_of_v2_evidence_can_be_rechecked_without_operator_key(self):
        rec=self.ingest()
        art={"keys":{"devices":{"meter-001":self.meter.pk_bytes.hex()},"issuers":{}}}
        state=dict(self.state)
        state[rec["field"]]=rec
        self.assertEqual(replay.verify_evidence(art,state,trusted_installers=self.pins),[])
        self.assertIn(rec["field"], replay.verify_evidence(art,state))

    def test_30_signed_merkle_root_commits_certificate_and_reading(self):
        rec = self.ingest()
        t=SMT()
        t.update(self.install["field"],record_hash(self.install))
        t.update(rec["field"],record_hash(rec))
        self.assertTrue(verify(t.root,self.install["field"],record_hash(self.install),t.prove(self.install["field"])))
        bad=copy.deepcopy(self.install)
        bad["value"]["building_id"]=OTHER
        self.assertFalse(verify(t.root,self.install["field"],record_hash(bad),t.prove(self.install["field"])))

    def test_31_historical_archive_requires_explicit_legacy_opt_in(self):
        art=replay.load(ROOT/"results"/"prototype")
        st=art["store"].as_of("2017-03-31T23:59")
        b=art["params"]["buildings"][1]
        self.assertRaises(binding.BindingError,replay.report,st,b,"2017-01",art["params"]["site"])
        result=replay.report(st,b,"2017-01",art["params"]["site"],legacy_archival=True)
        self.assertEqual(result["actual_kwh"]["grade"],"B")

    def test_32_real_published_meter_series_with_synthetic_installer_certificate(self):
        # The 2017 values were NOT really installer-certified. This exercise
        # tests interoperability and preserves their meter-signed numeric data.
        art=replay.load(ROOT/"results"/"prototype")
        st=copy.deepcopy(art["store"].as_of("2017-03-31T23:59"))
        b=art["params"]["buildings"][1]
        old=replay.report(st,b,"2017-01",art["params"]["site"],legacy_archival=True)
        meter_dev="meter-001"
        key=bytes.fromhex(art["keys"]["devices"][meter_dev])
        kwargs=dict(self.fields)
        kwargs.update(device_id=meter_dev,public_key=key.hex(),building_id=b,
                      certificate_id="synthetic-backfill-certificate")
        c=binding.ingest_binding(**kwargs, signature=binding.sign_binding(self.installer,**kwargs),
                                 trusted_installers=self.pins,tx_time="2016-12-31T12:00")
        st[c["field"]]=c
        for f,r in st.items():
            if f.startswith(f"{b}/elec/2017-01-"):
                r["adapter"]="diyar-ref/0.2/dlms-suite1-sim-bound-v2"
                r["unit"]="kWh"
                r["evidence"]["binding_cert_id"]=kwargs["certificate_id"]
                r["evidence"]["binding_sig_format"]=binding.BIND_V2
                self.assertTrue(binding.validate_meter_record(st,r,trusted_installers=self.pins,
                           published_devices=art["keys"]["devices"]))
        new=replay.report(st,b,"2017-01",art["params"]["site"],trusted_installers=self.pins)
        self.assertEqual(new["actual_kwh"],old["actual_kwh"])
        self.assertEqual(new["actual_kwh"]["grade"],"B")
        self.assertIn(c["field"],new["binding"]["evidence"])

    def test_33_conflicting_meter_in_historical_report_blocks_financial_metric(self):
        art=replay.load(ROOT/"results"/"prototype")
        st=copy.deepcopy(art["store"].as_of("2017-03-31T23:59"))
        b=art["params"]["buildings"][1]
        with self.assertRaises(binding.BindingError):
            replay.report(st,b,"2017-01",art["params"]["site"],trusted_installers=self.pins)

    def test_34_index_field_relabel_cannot_pass_verifier(self):
        rec = self.ingest()
        fake_index = f"{OTHER}/elec/{DAY}"
        st = dict(self.state)
        st[fake_index] = rec  # signed field remains B/elec/day, key is another building
        art = {"keys":{"devices":{"meter-001":self.meter.pk_bytes.hex()},"issuers":{}}}
        self.assertFalse(binding.validate_meter_record(st,rec,trusted_installers=self.pins,
                                                        expected_field=fake_index))
        self.assertIn(fake_index,replay.verify_evidence(art,st,trusted_installers=self.pins))
        with self.assertRaises(binding.BindingError):
            replay.report(st,OTHER,"2017-01","Fox",trusted_installers=self.pins)

    def test_35_unknown_meter_adapter_fails_closed(self):
        rec = self.ingest()
        rec["adapter"] = "diyar-ref/0.3/unreviewed-meter-format"
        st = dict(self.state)
        st[rec["field"]]=rec
        art={"keys":{"devices":{"meter-001":self.meter.pk_bytes.hex()},"issuers":{}}}
        self.assertIn(rec["field"], replay.verify_evidence(art,st,trusted_installers=self.pins))

    def test_36_unknown_certificate_adapter_fails_closed(self):
        st = copy.deepcopy(self.state)
        st[self.install["field"]]["adapter"] = "diyar-ref/0.3/unreviewed-installation-format"
        art={"keys":{"devices":{},"issuers":{}}}
        self.assertIn(self.install["field"], replay.verify_evidence(art,st,trusted_installers=self.pins))

    def test_37_certificate_id_immutable_in_bitemporal_store(self):
        from diyar.records import Store
        store=Store()
        store.add(self.install)
        reissue=copy.deepcopy(self.install)
        reissue["tx_time"]="2017-01-16T00:00"
        with self.assertRaises(ValueError):
            store.add(reissue)

    def test_38_retroactive_revoke_invalidates_new_report_not_old_asof(self):
        fields=dict(certificate_id="certificate-001",revoked_from=DAY,
                    installer_id="licenced-installer", installer_key_id="k001")
        sig=binding.sign_revocation(self.installer,**fields)
        rev=binding.ingest_revocation(**fields,signature=sig,
                       trusted_installers=self.pins,tx_time="2017-02-15T00:00")
        rec=self.ingest()
        st_then=dict(self.state)
        st_then[rec["field"]]=rec
        st_now=dict(st_then)
        st_now[rev["field"]]=rev
        self.assertTrue(binding.validate_meter_record(st_then,rec,trusted_installers=self.pins))
        self.assertFalse(binding.validate_meter_record(st_now,rec,trusted_installers=self.pins))

    def test_39_distinct_nonoverlapping_meter_replacements_accepted(self):
        new_key=ECKey()
        newer=self.make_install(certificate_id="certificate-002",device_id="meter-002",
                  public_key=new_key.pk_bytes.hex(),valid_from="2017-01-13",valid_to=None)
        old=self.make_install(valid_to="2017-01-12")
        st={old["field"]:old,newer["field"]:newer}
        self.assertIsNotNone(self.ingest(state=st))
        field=f"{B}/elec/2017-01-13"
        readings=self.make_readings(device_id="meter-002",key=new_key,field=field,day="2017-01-13")
        new=intake.ingest_meter_day(field,readings,"meter-002",new_key.pk_bytes,
                       valid_from="2017-01-13",valid_to="2017-01-13",
                       tx_time="2017-01-13T23:30",binding_state=st,trusted_installers=self.pins)
        self.assertEqual(new["evidence"]["binding_cert_id"],"certificate-002")

    def test_40_unauthorized_cert_signature_cannot_be_recorded(self):
        with self.assertRaises(binding.BindingError):
            self.make_install(signed_by=self.other_installer)

    def test_41_revocation_id_immutable_in_bitemporal_store(self):
        from diyar.records import Store
        fields=dict(certificate_id="certificate-001",revoked_from=DAY,
                    installer_id="licenced-installer",installer_key_id="k001")
        rev=binding.ingest_revocation(**fields,signature=binding.sign_revocation(self.installer,**fields),
                trusted_installers=self.pins,tx_time="2017-01-10T00:00")
        s=Store();s.add(rev)
        later=copy.deepcopy(rev);later["tx_time"]="2017-01-13T00:00"
        with self.assertRaises(ValueError):
            s.add(later)


if __name__ == "__main__":
    unittest.main(verbosity=2)
