"""P0-04: unconditional chronology validation, including `python -O`.

These tests deliberately do not require an SLH-DSA signing library. The
crypto import placeholder is import-only; no SLH verification occurs here.
Genuine 91-day PQ verification is performed by run_legacy_real_openssl.py.
"""
import copy
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

if importlib.util.find_spec("slhdsa") is None:
    sys.modules["slhdsa"] = types.ModuleType("slhdsa")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diyar.records import (ChronologyError, RecordValidationError,
                           Store, make_record, record_hash)


def rec(field="b/energy", value=100, *, tx="2017-02-01T00:00",
        start="2017-01-01", end="2017-01-31", grade="A1"):
    return make_record(field, value, grade=grade, adapter="test/p004",
                       valid_from=start, valid_to=end, tx_time=tx)


class StoreChronologyP004Tests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.r1 = rec()
        self.store.add(self.r1)

    def _reject_same_state(self, row, exc=RecordValidationError):
        before = copy.deepcopy(self.store.versions)
        with self.assertRaises(exc):
            self.store.add(row)
        self.assertEqual(before, self.store.versions)

    def test_01_initial_valid_record(self):
        self.assertEqual(self.store.as_of("2017-02-01T00:00")["b/energy"]["value"], 100)

    def test_02_later_transaction_accepted(self):
        self.store.add(rec(value=90, tx="2017-02-10T00:00"))
        self.assertEqual([r["value"] for r in self.store.versions["b/energy"]], [100, 90])

    def test_03_duplicate_timestamp_rejected(self):
        self._reject_same_state(rec(value=91), ChronologyError)

    def test_04_earlier_transaction_rejected(self):
        self._reject_same_state(rec(value=91, tx="2017-01-31T23:59"), ChronologyError)

    def test_05_mixed_field_same_tx_allowed(self):
        self.store.add(rec("b/temp", 8))
        self.assertEqual(len(self.store.versions), 2)

    def test_06_rejected_invalid_first_record_does_not_create_bucket(self):
        self._reject_same_state(rec("new/field", tx="2017-02-30T00:00"))
        self.assertNotIn("new/field", self.store.versions)

    def test_07_backfill_older_valid_date_later_tx_allowed(self):
        self.store.add(rec(value=90, tx="2017-02-10T00:00", start="2017-01-01", end="2017-01-15"))
        self.assertEqual(self.store.as_of("2017-02-05T00:00")["b/energy"]["value"], 100)
        self.assertEqual(self.store.as_of("2017-02-15T00:00")["b/energy"]["value"], 90)
        self.assertEqual(self.store.query("2017-01-20", "2017-02-15T00:00")["b/energy"]["value"], 100)
        self.assertEqual(self.store.query("2017-01-05", "2017-02-15T00:00")["b/energy"]["value"], 90)

    def test_08_time_zone_ambiguity_rejected(self):
        for time in ("2017-02-01T01:00+01:00", "2017-02-01T00:00Z", "2017-02-01T00:00:00"):
            with self.subTest(time=time):
                self._reject_same_state(rec(tx=time))

    def test_09_non_canonical_clock_rejected(self):
        for time in ("2017-2-01T00:00", "2017-02-01T0:00", "2017-02-01 00:00", "2017/02/01T00:00"):
            with self.subTest(time=time):
                self._reject_same_state(rec(tx=time))

    def test_10_invalid_clock_rejected(self):
        for time in ("2017-02-29T00:00", "2017-01-01T24:00", "2017-01-01T12:60", "0000-01-01T00:00"):
            with self.subTest(time=time):
                self._reject_same_state(rec(tx=time))

    def test_11_missing_or_non_string_tx_rejected(self):
        for time in (None, 1700000000, "", [], {}):
            with self.subTest(time=time):
                self._reject_same_state(rec(tx=time))

    def test_12_reversed_valid_interval_rejected(self):
        self._reject_same_state(rec(tx="2017-02-10T00:00", start="2017-01-31", end="2017-01-01"))

    def test_13_invalid_valid_day_rejected(self):
        for day in ("2017-02-29", "2017-1-01", "2017-01-01T00:00", "2017/01/01"):
            with self.subTest(day=day):
                self._reject_same_state(rec(tx="2017-02-10T00:00", start=day))
                self._reject_same_state(rec(tx="2017-02-10T00:00", end=day))

    def test_14_open_ended_valid_interval_allowed(self):
        self.store.add(rec(tx="2017-02-10T00:00", end=None))
        self.assertEqual(self.store.query("2019-01-01", "2020-01-01T00:00")["b/energy"]["tx_time"], "2017-02-10T00:00")

    def test_15_invalid_grade_refused_even_under_optimized_python(self):
        with self.assertRaises(RecordValidationError):
            rec(grade="A0")
        wrong = copy.deepcopy(self.r1)
        wrong.update(tx_time="2017-02-10T00:00", grade="A0")
        self._reject_same_state(wrong)

    def test_16_invalid_field_refused(self):
        for field in (None, 7, "", "  "):
            with self.subTest(field=field):
                self._reject_same_state(rec(field, tx="2017-02-10T00:00"))

    def test_17_certificate_id_reuse_never_allowed(self):
        s = Store()
        s.add(rec("certificates/one"))
        with self.assertRaises(RecordValidationError):
            s.add(rec("certificates/one", tx="2017-03-01T00:00"))
        self.assertEqual(len(s.versions["certificates/one"]), 1)

    def test_18_revocation_id_reuse_never_allowed(self):
        s = Store()
        s.add(rec("revocations/one"))
        with self.assertRaises(RecordValidationError):
            s.add(rec("revocations/one", tx="2017-03-01T00:00"))
        self.assertEqual(len(s.versions["revocations/one"]), 1)

    def test_19_dump_load_roundtrip_preserves_hashes(self):
        self.store.add(rec(tx="2017-02-10T00:00", value=80))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.jsonl"
            self.store.dump(path)
            loaded = Store.load(path)
            self.assertEqual(loaded.versions, self.store.versions)
            for new, old in zip(loaded.versions["b/energy"], self.store.versions["b/energy"]):
                self.assertEqual(record_hash(new), record_hash(old))

    def test_20_corrupted_file_with_duplicate_commit_time_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.jsonl"
            path.write_text(json.dumps(self.r1) + "\n" + json.dumps(rec(value=70)) + "\n")
            with self.assertRaises(ChronologyError):
                Store.load(path)

    def test_21_corrupted_file_with_invalid_date_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.jsonl"
            path.write_text(json.dumps(rec("x/y", tx="2017-02-30T00:00")) + "\n")
            with self.assertRaises(RecordValidationError):
                Store.load(path)

    def test_22_leap_day_canonical_accepted(self):
        self.store.add(rec(tx="2020-02-29T23:59", start="2020-02-29", end="2020-03-01"))
        self.assertEqual(len(self.store.versions["b/energy"]), 2)

    def test_23_safely_reject_non_dict(self):
        for value in (None, [], 3, "invalid"):
            with self.subTest(value=value):
                self._reject_same_state(value)

    def test_24_multiple_corrections_preserve_bitemporal_semantics(self):
        self.store.add(rec(value=90, tx="2017-02-10T00:00", start="2017-01-01", end="2017-01-15"))
        self.store.add(rec(value=95, tx="2017-02-20T00:00", start="2017-01-10", end="2017-01-31"))
        q = [self.store.query(v, k).get("b/energy", {}).get("value") for v, k in
             [("2017-01-05", "2017-02-05T00:00"), ("2017-01-05", "2017-02-15T00:00"),
              ("2017-01-20", "2017-02-15T00:00"), ("2017-01-20", "2017-02-25T00:00"),
              ("2017-01-05", "2017-02-25T00:00"), ("2017-01-05", "2017-01-20T00:00")]]
        self.assertEqual(q, [100, 90, 100, 95, 90, None])


if __name__ == "__main__":
    unittest.main(verbosity=2)
