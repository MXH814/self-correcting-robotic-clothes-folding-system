import unittest
import numpy as np
from research_tools.recovery_dataset import readiness,region_result
from tests.test_sequence_ranker import rows


class DatasetAdmission(unittest.TestCase):
    def test_proxy_recount_and_reference_control(self):
        final=np.array([[.2,.2,0],[.8,.8,0],[.3,.6,0]])
        initial=np.array([[.2,.2,0],[2,2,0],[3,3,0]])
        self.assertTrue(region_result(final,[0,1,0,1],.88)['passed'])
        self.assertFalse(region_result(initial,[0,1,0,1],.88)['passed'])

    def test_invalid_proxy_geometry_rejected(self):
        for points,bounds,threshold in [
            (np.zeros((0,3)),[0,1,0,1],.88),
            (np.array([[np.nan,0,0]]),[0,1,0,1],.88),
            (np.zeros((1,3)),[1,0,0,1],.88),
            (np.zeros((1,3)),[0,1,0,1],True),
        ]:
            with self.assertRaises(ValueError):region_result(points,bounds,threshold)
    def test_one_positive_unassigned_sample_is_not_training_ready(self):
        r=rows()[1];r['split']='unassigned'
        report=readiness([r])
        self.assertEqual(report['positive_proxy_samples'],1)
        self.assertFalse(report['software_training_admission_ready'])
        self.assertEqual(len(report['blockers']),3)

    def test_functional_coverage_is_not_research_sufficiency(self):
        report=readiness(rows())
        self.assertTrue(report['software_training_admission_ready'])
        self.assertFalse(report['research_sufficiency_established'])

    def test_positive_only_training_remains_blocked(self):
        data=rows()
        for row in data:row['continuation_success']=True
        self.assertFalse(readiness(data)['software_training_admission_ready'])

    def test_cross_trial_label_and_context_mismatch_rejected(self):
        for mutate in [lambda r:r[-1]['features'].update(trial_id='t0'),
                       lambda r:r[-1]['features'].update(continuation_context_reference='other-camera'),
                       lambda r:r[-1].update(lineage_group=r[0]['lineage_group'])]:
            data=rows();mutate(data)
            with self.assertRaises(ValueError):readiness(data)
