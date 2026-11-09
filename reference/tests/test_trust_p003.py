"""P0-03 targeted trust propagation regression and adversarial tests."""
import copy
import importlib.util
import sys
import types
import unittest
from pathlib import Path
if importlib.util.find_spec('slhdsa') is None:
    sys.modules['slhdsa'] = types.ModuleType('slhdsa')  # import shim, never asserts SLH validity
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diyar import trust, replay, binding, intake
from diyar.baseline import SPEC, model_version
from diyar.records import make_record, Store
from diyar.crypto import ECKey

MODEL = {'beta': [1.0] * 175, 'spec': SPEC}
ROOT = Path(__file__).resolve().parents[1]


def rec(f, grade='B'):
    return make_record(f, [1], grade=grade, adapter='test', valid_from='2016-01-01',
                       valid_to='2016-12-31', tx_time='2016-12-31T12:00')

class P003Tests(unittest.TestCase):
    def test_01_unverified_csv_is_C_not_A2(self):
        b = trust.baseline_record('X/baseline', MODEL, valid_from='2017-01-01', tx_time='2016-12-31T12:00',
                                  source_payloads={'meter':[5], 'wx':[20]})
        self.assertEqual(b['grade'], 'C')
        self.assertEqual(trust.baseline_grade({'X/baseline':b}, 'X/baseline')[0], 'C')
        self.assertEqual(b['evidence']['source_status'], 'unverified-external-training')
        self.assertEqual(len(b['evidence']['external_training_sha256']),64)

    def test_02_data_change_changes_hash(self):
        one = trust.baseline_record('X/baseline', MODEL, valid_from='2017-01-01',tx_time='T',source_payloads=[1,2])
        two = trust.baseline_record('X/baseline', MODEL, valid_from='2017-01-01',tx_time='T',source_payloads=[1,3])
        self.assertNotEqual(one['evidence']['external_training_sha256'],two['evidence']['external_training_sha256'])

    def test_03_empty_provenance_cannot_claim_A2(self):
        b = trust.baseline_record('X/baseline', MODEL, valid_from='2017-01-01', tx_time='T')
        b['grade'] = 'A2'
        with self.assertRaises(trust.TrustError): trust.baseline_grade({'X/baseline':b}, 'X/baseline')

    def test_04_missing_manifest_returns_C_for_legacy_in_strict_mode(self):
        b = rec('X/baseline','A2')
        self.assertEqual(trust.baseline_grade({'X/baseline':b},'X/baseline'),('C','legacy-or-absent-training-provenance'))

    def test_05_legacy_mode_preserves_historical_grade(self):
        b = rec('X/baseline','A2')
        self.assertEqual(trust.baseline_grade({'X/baseline':b},'X/baseline', legacy_archival=True)[0],'A2')

    def test_06_real_referenced_grades_propagate_weakest(self):
        a, c = rec('training/meter','A1'), rec('training/binding','B')
        b = trust.baseline_record('X/baseline', MODEL, valid_from='2017-01-01', tx_time='T',source_records=[a,c])
        self.assertEqual(b['grade'],'B')
        self.assertEqual(trust.baseline_grade({a['field']:a,c['field']:c,b['field']:b}, b['field'])[0],'B')

    def test_07_missing_reference_rejected(self):
        a = rec('training/meter','A1')
        b = trust.baseline_record('X/baseline', MODEL, valid_from='2017-01-01',tx_time='T',source_records=[a])
        with self.assertRaises(trust.TrustError): trust.baseline_grade({b['field']:b},b['field'])

    def test_08_mutated_reference_rejected(self):
        a = rec('training/meter','A1')
        b = trust.baseline_record('X/baseline', MODEL, valid_from='2017-01-01',tx_time='T',source_records=[a])
        bad = copy.deepcopy(a);bad['value']=[999]
        with self.assertRaises(trust.TrustError): trust.baseline_grade({a['field']:bad,b['field']:b},b['field'])

    def test_09_unsupported_derived_grade_as_input_rejected(self):
        a=rec('training/meter','derived')
        with self.assertRaises(trust.TrustError): trust.baseline_record('X/baseline',MODEL,valid_from='2017-01-01',tx_time='T',source_records=[a])

    def test_10_forged_grade_on_record_rejected(self):
        a=rec('training/meter','B')
        b=trust.baseline_record('X/baseline',MODEL,valid_from='2017-01-01',tx_time='T',source_records=[a])
        b['grade']='A2'
        with self.assertRaises(trust.TrustError):trust.baseline_grade({a['field']:a,b['field']:b},b['field'])

    def test_11_changed_model_rejected(self):
        a=rec('training/meter','B')
        b=trust.baseline_record('X/baseline',MODEL,valid_from='2017-01-01',tx_time='T',source_records=[a])
        b['value']['beta'][0] = 9
        with self.assertRaises(trust.TrustError):trust.baseline_grade({a['field']:a,b['field']:b},b['field'])

    def test_12_duplicate_dependency_rejected(self):
        a=rec('training/meter','B')
        with self.assertRaises(trust.TrustError): trust.baseline_record('X/baseline',MODEL,valid_from='2017-01-01',tx_time='T',source_records=[a,a])

    def test_13_grade_order_no_upgrade(self):
        for g in ('A1','A2','A2-','B','B-','C+','C'):
            r=rec('training/a',g)
            b=trust.baseline_record('X/baseline',MODEL,valid_from='2017-01-01',tx_time='T',source_records=[r])
            self.assertEqual(b['grade'],g)

    def test_14_wrong_dependency_label_rejected(self):
        a=rec('training/meter','B')
        b=trust.baseline_record('X/baseline',MODEL,valid_from='2017-01-01',tx_time='T',source_records=[a])
        b['derived_from']=['different']
        with self.assertRaises(trust.TrustError):trust.baseline_grade({a['field']:a,b['field']:b},b['field'])

    def test_15_archived_replay_hash_unchanged(self):
        art=replay.load(ROOT / 'results/prototype')
        state=art['store'].as_of('2017-02-04T23:59')
        site=art['params']['site']
        published=__import__('json').loads((ROOT/'results/prototype/published_reports_jan.json').read_text())
        for building in art['params']['buildings']:
            report=replay.report(state,building,'2017-01',site,legacy_archival=True)
            self.assertEqual(report['output_hash'],published[building]['output_hash'])


class ReportPropagationTests(unittest.TestCase):
    def setUp(self):
        self.b = 'Fox_education_Wendell'
        self.day = '2017-01-12'
        self.site = 'Fox'
        self.month = '2017-01'
        self.ins = ECKey()
        self.meter = ECKey()
        self.pins = {'installer': {'v1': self.ins.pk_bytes}}
        self.install_args = dict(certificate_id='c1', device_id='meter-1', public_key=self.meter.pk_bytes.hex(),
                                 building_id=self.b,channel='electricity',unit='kWh',location='main-incomer',
                                 valid_from='2017-01-01',valid_to='2017-12-31',
                                 installer_id='installer',installer_key_id='v1')
        cert=binding.ingest_binding(**self.install_args,
                                   signature=binding.sign_binding(self.ins,**self.install_args),
                                   trusted_installers=self.pins,tx_time='2016-12-31T12:00')
        field=f'{self.b}/elec/{self.day}'
        readings=intake.Meter('meter-1',self.meter).emit(field,
                   [f'{self.day}T{i:02d}:00' for i in range(24)], [12.0]*24)
        meter_rec=intake.ingest_meter_day(field,readings,'meter-1',self.meter.pk_bytes,
                   valid_from=self.day,valid_to=self.day,tx_time='2017-01-12T23:30',
                   binding_state={cert['field']:cert},trusted_installers=self.pins)
        wx=make_record(f'{self.site}/temp/{self.day}', [20.0]*24,grade='A2',adapter='test',
                       valid_from=self.day,valid_to=self.day,tx_time='2017-01-12T23:30')
        self.baseline=trust.baseline_record(f'{self.b}/baseline',MODEL,valid_from='2017-01-01',
                            tx_time='2016-12-31T12:00',source_payloads={'unverified_2016_csv':'sha256'})
        self.state={r['field']:r for r in (cert,meter_rec,wx,self.baseline)}

    def test_16_report_baseline_and_performance_inherit_C(self):
        out=replay.report(self.state,self.b,self.month,self.site,trusted_installers=self.pins)
        self.assertEqual(out['actual_kwh']['grade'],'B')
        self.assertEqual(out['baseline_kwh']['grade'],'C')
        self.assertEqual(out['baseline_kwh']['training_provenance'],'unverified-external-training')
        self.assertEqual(out['performance_vs_baseline']['grade'], None) # insufficient monthly hours
        self.assertEqual(out['coverage_weather']['grade'],'A2')
        self.assertEqual(out['residual_assumptions']['baseline_kwh'],'everything')

    def test_17_weather_coverage_grade_follows_source(self):
        self.state[f'{self.site}/temp/{self.day}']['grade']='C+'
        out=replay.report(self.state,self.b,self.month,self.site,trusted_installers=self.pins)
        self.assertEqual(out['coverage_weather']['grade'],'C+')
        self.assertEqual(out['baseline_kwh']['grade'],'C')

    def test_18_legacy_A2_baseline_capped_in_strict_V2_report(self):
        self.state[f'{self.b}/baseline']['grade']='A2'
        with self.assertRaises(trust.TrustError):
            replay.report(self.state,self.b,self.month,self.site,trusted_installers=self.pins)

    def test_19_rejected_unrelated_binding_not_upgraded(self):
        for f in tuple(self.state):
            if f.startswith('certificates/'):
                self.state[f]['value']['building_id']='other-building'
        with self.assertRaises(binding.BindingError):
            replay.report(self.state,self.b,self.month,self.site,trusted_installers=self.pins)

    def test_20_no_weather_grade_claimed_A2(self):
        del self.state[f'{self.site}/temp/{self.day}']
        out=replay.report(self.state,self.b,self.month,self.site,trusted_installers=self.pins)
        self.assertEqual(out['coverage_weather']['grade'],'C')
        self.assertEqual(out['baseline_kwh']['grade'],'C')

    def test_22_gate_flags_grade_is_not_undefined_derived(self):
        gate=make_record(f'{self.b}/gate/{self.day}', {'flag':True,'score':0.2},
                         grade='derived',adapter='legacy',valid_from=self.day,
                         valid_to=self.day,tx_time='2017-01-12T23:45')
        self.state[gate['field']]=gate
        r=replay.report(self.state,self.b,self.month,self.site,trusted_installers=self.pins)
        self.assertEqual(r['gate_flags']['grade'],'C')
        self.assertEqual(r['gate_flags']['value'],1)

    def test_23_fake_A1_gate_cannot_upgrade_C_baseline(self):
        gate=make_record(f'{self.b}/gate/{self.day}',{'flag':True,'score':0.2},grade='A1',
                         adapter='unauthenticated',valid_from=self.day,valid_to=self.day,
                         tx_time='2017-01-12T23:45')
        self.state[gate['field']]=gate
        r=replay.report(self.state,self.b,self.month,self.site,trusted_installers=self.pins)
        self.assertEqual(r['gate_flags']['grade'],'C')

    def test_21_sufficient_monthly_performance_inherits_training_C(self):
        # 28 complete days => coverage 672/744 > 90%, so performance is populated.
        for d in range(1,29):
            day=f'2017-01-{d:02d}'
            if day==self.day:
                continue
            field=f'{self.b}/elec/{day}'
            readings=intake.Meter('meter-1',self.meter).emit(field,
                      [f'{day}T{i:02d}:00' for i in range(24)], [12.0]*24)
            meter_rec=intake.ingest_meter_day(field,readings,'meter-1',self.meter.pk_bytes,
                      valid_from=day,valid_to=day,tx_time=f'{day}T23:30',
                      binding_state=self.state,trusted_installers=self.pins)
            wx=make_record(f'{self.site}/temp/{day}',[20.0]*24,grade='A2',adapter='test',
                           valid_from=day,valid_to=day,tx_time=f'{day}T23:30')
            self.state[field]=meter_rec
            self.state[wx['field']]=wx
        result=replay.report(self.state,self.b,self.month,self.site,trusted_installers=self.pins)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['actual_kwh']['grade'],'B')
        self.assertEqual(result['baseline_kwh']['grade'],'C')
        self.assertEqual(result['performance_vs_baseline']['grade'],'C')
        self.assertIsNotNone(result['performance_vs_baseline']['value'])

if __name__ == '__main__':unittest.main(verbosity=2)
