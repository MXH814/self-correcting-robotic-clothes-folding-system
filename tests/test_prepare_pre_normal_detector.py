"""Software contract checks for render-time intent and shared sensor identity."""
import copy
import unittest
from research_tools.prepare_pre_normal_detector import controller_phase_at, detector_context_reference


def event(t,kind,**values):
    return {'clock':{'sim_time_s':t},'kind':kind,**values}


class RenderIntentTests(unittest.TestCase):
    def test_separate_sleeves_use_only_past_controller_arm_intent(self):
        events=[event(1,'NORMAL_ACTION_BEGIN',arm='left',operation='lift',expected_hold=True),
                event(2,'NORMAL_ACTION_BEGIN',arm='right',operation='transfer',expected_hold=True)]
        self.assertEqual(controller_phase_at(events,2,separate_sleeves=True)[0],'LEFT_SLEEVE_HOLD')
        self.assertEqual(controller_phase_at(events,2.1,separate_sleeves=True)[0],'RIGHT_SLEEVE_HOLD')
        self.assertEqual(controller_phase_at(events,2.1)[0],'HOLD')
    def test_future_and_equal_time_commands_do_not_relabel_prior_image(self):
        events=[event(1,'NORMAL_ACTION_BEGIN',arm='left',operation='lift',expected_hold=True),
                event(2,'NORMAL_HAND_COMMAND',left='open',right='None',planned_release=True)]
        self.assertEqual(controller_phase_at(events,1)[0],'OTHER')
        self.assertEqual(controller_phase_at(events,1.1)[0],'HOLD')
        self.assertEqual(controller_phase_at(events,2)[0],'HOLD')
        self.assertEqual(controller_phase_at(events,2.1)[0],'RELEASE')

    def test_lift_and_transfer_share_hold_until_release(self):
        events=[event(1,'NORMAL_ACTION_BEGIN',arm='right',operation='lift',expected_hold=True),
                event(2,'NORMAL_ACTION_END',arm='right',operation='lift'),
                event(3,'NORMAL_ACTION_BEGIN',arm='right',operation='transfer',expected_hold=True)]
        self.assertEqual(controller_phase_at(events,2.5)[0],'HOLD')
        self.assertEqual(controller_phase_at(events,3.1)[0],'HOLD')

    def test_injection_and_outcome_events_cannot_set_phase(self):
        events=[event(1,'FAULT_INJECTED',phase='HOLD',expected_hold=True),
                event(2,'FINAL_OUTCOME',phase='HOLD',upstream_region_proxy={'upstream_success':True})]
        self.assertEqual(controller_phase_at(events,3),('OTHER',None))

    def test_closing_without_lift_and_unknown_moves_are_other(self):
        events=[event(1,'NORMAL_HAND_COMMAND',left='close',right='close'),
                event(2,'NORMAL_ACTION_BEGIN',arm='left',operation='scripted-move',expected_hold=False)]
        self.assertEqual(controller_phase_at(events,1.1)[0],'OTHER')
        self.assertEqual(controller_phase_at(events,2.1)[0],'OTHER')


class ContextBindingTests(unittest.TestCase):
    def setUp(self):
        self.context={'schema':'full-fold-continuation-context/1','trial_id':'first',
            'camera':{'resolution_wh':[640,480],'position_world_m':[0,3.6,3.2]},
            'controller':{'upstream_sha256':{'controller.py':'a'*64},
                'wrapper_sha256':{'fold_recovery_chain.py':'b'*64,'garment_observation_trace.py':'c'*64,'run_fold_local.py':'d'*64}},
            'execution_profile':{'physics_dt_s':1/60,'observation_interval_physics_steps':3},
            'target':{'initial_point_cloud_sha256':'e'*64}}

    def test_trial_geometry_and_entry_wiring_do_not_alias_sensor_identity(self):
        other=copy.deepcopy(self.context)
        other['trial_id']='second'
        other['target']['initial_point_cloud_sha256']='f'*64
        other['controller']['wrapper_sha256']['run_fold_local.py']='0'*64
        self.assertEqual(detector_context_reference(self.context),detector_context_reference(other))

    def test_sleeve_phase_mapping_has_distinct_version_binding(self):
        self.assertNotEqual(detector_context_reference(self.context),
                            detector_context_reference(self.context,separate_sleeves=True))

    def test_actual_camera_controller_or_capture_change_invalidates_identity(self):
        for category in ('camera','controller','capture'):
            with self.subTest(category=category):
                other=copy.deepcopy(self.context)
                if category=='camera':other['camera']['position_world_m'][1]=3.5
                if category=='controller':other['controller']['upstream_sha256']['controller.py']='0'*64
                if category=='capture':other['controller']['wrapper_sha256']['garment_observation_trace.py']='0'*64
                self.assertNotEqual(detector_context_reference(self.context),detector_context_reference(other))


if __name__=='__main__': unittest.main()
