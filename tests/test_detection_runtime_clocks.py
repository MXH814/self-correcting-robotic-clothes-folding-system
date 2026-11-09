"""Live timestamps remain directly measured across inference."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import numpy as np
from research_tools.detection_runtime import DetectionRuntime


class RuntimeClockTests(unittest.TestCase):
    def runtime(self):
        runtime=DetectionRuntime.__new__(DetectionRuntime)
        runtime.context_reference='fixture'
        runtime.error=None
        runtime.encoder=SimpleNamespace(encode=Mock(return_value=np.zeros((1,512))))
        runtime.detector=SimpleNamespace(max_age_wall_s=1., reset=Mock(),detect=Mock(
            return_value=dict(status='NORMAL',reason='WITHIN_NORMAL_REFERENCE',decision_wall_s=100.10000000001)))
        return runtime

    def observation(self):
        return dict(trial_id='t',lineage_group='t',observation_id='o',frame_id='f',
            sim_time_s=1.,read_sim_time_s=1.,phase='HOLD',context_reference='fixture',encoder_reference='e')

    def test_decision_uses_actual_clock_instead_of_rounded_estimate(self):
        runtime=self.runtime()
        with patch('research_tools.detection_runtime.time.monotonic',side_effect=[100.,100.05,100.1]):
            report=runtime.observe(np.zeros((2,2,3),dtype=np.uint8),self.observation(),generation=0,
                captured_wall_s=99.9,now_wall_s=100.)
        self.assertEqual(report['decision_wall_s'],100.1)
        self.assertEqual(report['status'],'NORMAL')

    def test_actual_completion_past_deadline_remains_unknown(self):
        runtime=self.runtime()
        with patch('research_tools.detection_runtime.time.monotonic',side_effect=[100.,100.05,101.2]):
            report=runtime.observe(np.zeros((2,2,3),dtype=np.uint8),self.observation(),generation=0,
                captured_wall_s=99.9,now_wall_s=100.)
        self.assertEqual(report['reason'],'DETECTION_RUNTIME_EXPIRED')
        runtime.detector.reset.assert_called_once()


if __name__=='__main__': unittest.main()
