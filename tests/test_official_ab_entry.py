"""Regression fixtures for continuous consumption and action gating."""
from collections import Counter
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/simulation'))
from official_ab_evidence import OfficialABEvidence
from pre_execution_support import SynchronousDispatchLedger


class ContinuousEntryTests(unittest.TestCase):
    def evidence(self,kind):
        evidence=OfficialABEvidence.__new__(OfficialABEvidence)
        evidence.seen_frames=set()
        evidence.halted=False
        evidence.controller_events=[dict(kind='NORMAL_ACTION_BEGIN',sequence=0,clock={'sim_time_s':0.},
            arm='left',operation='lift',expected_hold=True)]
        evidence.phase_counts=Counter()
        evidence.report_counts=Counter()
        evidence.pending=None
        evidence.scenario='fault-b'
        evidence.record={}
        evidence.chain=SimpleNamespace(trial_id='fixture',trace=SimpleNamespace(actions=[]))
        evidence.ledger=SynchronousDispatchLedger('fixture',recovery_enabled=True)
        evidence.adapter=SimpleNamespace(flow=SimpleNamespace(state='RUNNING'),observe=Mock(return_value=(
            {'phase':'HOLD'},dict(status='ANOMALY',score=2.,threshold=1.),dict(kind=kind,request_id='r'))))
        evidence.event=Mock()
        return evidence

    def continuation(self,geometry_status='HELD',rgb_status='ANOMALY',reason='OBSERVATION_OOD'):
        evidence=self.evidence('NO_RECOVERY')
        evidence.adapter.flow.generation=1
        evidence.adapter.flow.attempts=1
        evidence.adapter.flow.journal=Mock()
        evidence.current_expected_hold=True
        evidence.continuation_monitor=SimpleNamespace(update=Mock(return_value={'status':geometry_status}))
        evidence.patch=SimpleNamespace(capture=Mock(return_value={}))
        evidence.runtime_only=Mock(return_value=({'phase':'HOLD'},
            dict(status=rgb_status,reason=reason,score=2.,threshold=1.)))
        return evidence

    def test_verified_continuation_keeps_raw_ood_and_fresh_geometry_separate(self):
        evidence=self.continuation()
        evidence.consume(dict(rendering_frame=1,rendering_time_s=1.,observation_id='o'))
        evidence.adapter.observe.assert_not_called()
        self.assertIsNone(evidence.pending)
        self.assertEqual(evidence.report_counts['ANOMALY'],1)
        decision=evidence.adapter.flow.journal.call_args.args[0]
        self.assertEqual(decision['kind'],'CONTINUE_VERIFIED_HOLD')
        self.assertEqual(decision['raw_observation_status'],'ANOMALY')

    def test_verified_continuation_stops_when_hold_or_rgb_evidence_is_missing(self):
        for geometry,status,reason in [('LOST','NORMAL','WITHIN_NORMAL_REFERENCE'),
                                       ('HELD','UNKNOWN','MODEL_OR_CALIBRATION_UNAVAILABLE')]:
            evidence=self.continuation(geometry,status,reason)
            evidence.halt=Mock(side_effect=RuntimeError('fixture halt'))
            with self.assertRaisesRegex(RuntimeError,'fixture halt'):
                evidence.consume(dict(rendering_frame=1,rendering_time_s=1.,observation_id='o'))
            evidence.halt.assert_called_once()

    def test_planned_release_uses_current_intent_even_when_camera_still_shows_hold(self):
        evidence=self.continuation()
        evidence.current_expected_hold=False
        evidence.consume(dict(rendering_frame=1,rendering_time_s=1.,observation_id='o'))
        evidence.runtime_only.assert_not_called()
        self.assertFalse(evidence.adapter.observe.call_args.kwargs['expected_holding'])

    def test_alert_blocks_before_next_dispatch_and_consumes_frame_once(self):
        evidence=self.evidence('REQUEST_RECOVERY_PREFLIGHT')
        obs=dict(rendering_frame=1,rendering_time_s=1.,observation_id='o')
        evidence.consume(obs)
        evidence.consume(obs)
        self.assertFalse(evidence.ledger.normal_dispatch_allowed)
        self.assertEqual(evidence.pending['request_id'],'r')
        self.assertEqual(evidence.adapter.observe.call_count,1)

    def test_measurement_window_updates_detector_without_new_workflow_request(self):
        evidence=self.evidence('REQUEST_RECOVERY_PREFLIGHT')
        evidence.adapter.flow.state='RECOVERY_REQUESTED'
        evidence.runtime_only=Mock(return_value=({'phase':'HOLD'},dict(status='ANOMALY',score=2.,threshold=1.)))
        evidence.consume(dict(rendering_frame=2,rendering_time_s=1.,observation_id='o',joint_read_end={'sim_step':3}))
        evidence.runtime_only.assert_called_once()
        evidence.adapter.observe.assert_not_called()
        self.assertIsNone(evidence.pending)

    def test_dense_rest_measurements_preserve_model_sampling_cadence(self):
        evidence=self.evidence('REQUEST_RECOVERY_PREFLIGHT')
        evidence.adapter.flow.state='RECOVERY_REQUESTED'
        evidence.runtime_only=Mock()
        evidence.consume(dict(rendering_frame=2,rendering_time_s=1.,observation_id='o',joint_read_end={'sim_step':4}))
        evidence.runtime_only.assert_not_called()


if __name__=='__main__':
    unittest.main()
