"""Cross-platform rounding must not relax recorded identities or decisions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/simulation'))
from verify_official_ab import verify_geometry_report


class GeometryAuditTests(unittest.TestCase):
    def setUp(self):
        self.report=dict(distance_m=.07489332044102114,cloth_height_m=.31,
            trial_id='trial',generation=1,observed_sim_s=11.5,status='HELD',
            window_start_sim_s=11.3,sample_count=5)

    def test_platform_rounding_in_derived_geometry_is_accepted(self):
        actual=dict(self.report,distance_m=.07489332044102112)
        verify_geometry_report(actual,self.report)

    def test_material_geometry_changes_and_nonfinite_values_are_rejected(self):
        for key in ('distance_m','cloth_height_m'):
            for value in (self.report[key]+1e-10,float('nan'),float('inf')):
                with self.subTest(key=key,value=value),self.assertRaises(AssertionError):
                    verify_geometry_report(dict(self.report,**{key:value}),self.report)

    def test_identity_time_state_and_window_remain_exact(self):
        changes=dict(trial_id='other',generation=2,observed_sim_s=11.5+1e-13,
            status='LOST',window_start_sim_s=11.3+1e-13,sample_count=6)
        for key,value in changes.items():
            with self.subTest(key=key),self.assertRaises(AssertionError):
                verify_geometry_report(dict(self.report,**{key:value}),self.report)

    def test_missing_or_extra_keys_are_rejected(self):
        with self.assertRaises(AssertionError):
            verify_geometry_report(dict(self.report,unexpected=True),self.report)
        actual=dict(self.report)
        del actual['status']
        with self.assertRaises(AssertionError):
            verify_geometry_report(actual,self.report)
