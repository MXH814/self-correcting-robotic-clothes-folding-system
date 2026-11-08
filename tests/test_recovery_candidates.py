import unittest
from research_tools.recovery_candidates import encode_macro,recovery_features


class MacroProposals(unittest.TestCase):
    def candidate(self):
        return dict(schema='recovery-macro-proposal/1',kind='release-retreat-regrasp-lift',
                    coordinate_frame='world',position_unit='m',arm='left',candidate_id='candidate-1',
                    source_reference='software fixture planned before execution',trial_id='t',
                    available_at=dict(sim_step=1,sim_time_s=.1,wall_monotonic_ns=1),
                    retreat_world_m=[0,0,.2],pick_world_m=[0,0,0],lift_world_m=[0,0,.3],
                    orientation_wxyz=[1,0,0,0],open_wait_steps=45,close_wait_steps=12)

    def context(self):
        return dict(schema='garment-dispatch-input/1',trial_id='t',online_authorized=False,
                    as_of=dict(sim_step=2,sim_time_s=.2,wall_monotonic_ns=2))

    def test_macro_encodes_plan_and_keeps_offline(self):
        result=recovery_features(self.context(),self.candidate())
        self.assertEqual(len(result['candidate_target']),17)
        self.assertFalse(result['online_authorized'])

    def test_future_and_cross_trial_proposals_rejected(self):
        for mutate in [lambda c:c['available_at'].update(sim_step=3),lambda c:c.update(trial_id='another')]:
            c=self.candidate();mutate(c)
            with self.assertRaises(ValueError):
                recovery_features(self.context(),c)

    def test_units_and_quaternion_checked(self):
        for mutate in [lambda c:c.update(position_unit='mm'),lambda c:c.update(orientation_wxyz=[2,0,0,0])]:
            c=self.candidate();mutate(c)
            with self.assertRaises(ValueError):
                encode_macro(c)
