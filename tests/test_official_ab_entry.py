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
        evidence.chain=SimpleNamespace(trace=SimpleNamespace(actions=[]))
        evidence.ledger=SynchronousDispatchLedger('fixture',recovery_enabled=True)
        evidence.adapter=SimpleNamespace(flow=SimpleNamespace(state='RUNNING'),observe=Mock(return_value=(
            {'phase':'HOLD'},dict(status='ANOMALY',score=2.,threshold=1.),dict(kind=kind,request_id='r'))))
        evidence.event=Mock()
        return evidence

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
        evidence.consume(dict(rendering_frame=2,rendering_time_s=1.,observation_id='o'))
        evidence.runtime_only.assert_called_once()
        evidence.adapter.observe.assert_not_called()
        self.assertIsNone(evidence.pending)


if __name__=='__main__':
    unittest.main()
