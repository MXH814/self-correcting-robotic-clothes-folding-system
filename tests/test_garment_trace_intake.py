import copy
import unittest
import numpy as np

from research_tools.garment_trace_intake import encode_trace, encode_target


def fixture():
    def clock(step):
        return dict(sim_step=step, sim_time_s=step/20, wall_monotonic_ns=step*50000000)
    observations = []
    for i in range(7):
        observations.append(dict(observation_id='o'+str(i), phase='offline-injection-name', frame_index=i,
                                 rendering_time_s=i/20, camera_read_begin=clock(i),
                                 camera_read_end=clock(i), joint_read_end=clock(i),
                                 joint_state={arm:dict(position_rad=[float(i)], velocity_rad_s=[0.])
                                              for arm in ('left','right')}))
    actions = []
    for i in range(6):
        actions.append(dict(command_id='c'+str(i), arm='left', runtime_indices=[0], channels=['j'],
                            position_representation='absolute', targets={'joint_positions':[float(i)+.1]},
                            observation_id='o'+str(i), feedback_observation_id='o'+str(i+1),
                            issue=clock(i), api_returned=clock(i)))
    trace=dict(schema='garment-observation-trace-v1', trial_id='trial-a', condition='offline-label',
               target_units={'joint_positions':'rad'}, joint_names_runtime_order={'left':['j'],'right':['j']},
               observations=observations, actions=actions, frame_archive={'shape':[7,8,8,3]})
    rgb=np.tile(np.arange(8*8*3,dtype=np.uint8).reshape(1,8,8,3),(7,1,1,1))
    return trace,rgb


class CausalGarmentInputs(unittest.TestCase):
    def test_current_command_is_not_history(self):
        t,rgb=fixture()
        rows,_=encode_trace(t,rgb)
        self.assertEqual(rows[0]['past_command_ids'],[])
        self.assertEqual(rows[3]['past_command_ids'],['c0','c1','c2'])
        self.assertFalse(rows[3]['online_authorized'])

    def test_old_unit_metadata_needs_explicit_source(self):
        t,rgb=fixture();del t['target_units']
        with self.assertRaises(ValueError):
            encode_trace(t,rgb)
        _,audit=encode_trace(t,rgb,position_unit_source='documented SDK radians at commit abc')
        self.assertIn('commit abc',audit['position_unit_declaration'])

    def test_pending_command_excluded_even_if_already_issued(self):
        t,rgb=fixture()
        t['actions'][1]['feedback_observation_id']='o5'
        rows,_=encode_trace(t,rgb)
        self.assertNotIn('c1',rows[3]['past_command_ids'])
        self.assertIn('c1',rows[5]['past_command_ids'])

    def test_future_observations_actions_do_not_change_early_features(self):
        t,rgb=fixture()
        rows,_=encode_trace(t,rgb)
        t2=copy.deepcopy(t)
        for o in t2['observations'][4:]:
            o['joint_state']['left']['position_rad']=[900.]
        for a in t2['actions'][4:]:
            a['targets']['joint_positions']=[-700.]
        rgb2=rgb.copy();rgb2[4:]=255-rgb2[4:]
        other,_=encode_trace(t2,rgb2)
        self.assertEqual(rows[2],other[2])

    def test_hidden_labels_and_injection_names_are_not_features(self):
        t,rgb=fixture()
        rows,_=encode_trace(t,rgb)
        t['condition']='another-injected-class'
        t['future_success']=True
        for o in t['observations']:
            o['phase']='future-success-leak'
            o['privileged_contact']=[999.]
        other,_=encode_trace(t,rgb)
        self.assertEqual(rows,other)

    def test_right_arm_is_distinct_with_same_joint_name(self):
        t,rgb=fixture()
        a=copy.deepcopy(t['actions'][0]);a['arm']='right'
        vector=encode_target(a,t['observations'][0],t['joint_names_runtime_order'])
        self.assertEqual(vector[:2],[0.,1.])

    def test_shared_feedback_is_not_isolated_effect(self):
        t,rgb=fixture()
        t['actions'][0]['feedback_observation_id']='o2'
        rows,_=encode_trace(t,rgb)
        self.assertEqual(rows[2]['past_command_ids'],['c0','c1'])
        self.assertIn('shared',rows[2]['feedback_scope'])

    def test_bad_identity_time_and_mapping_rejected(self):
        for mutate in [
            lambda t:t['observations'][1].update(observation_id='o0'),
            lambda t:t['actions'][0].update(feedback_observation_id='other-trial/o2'),
            lambda t:t['actions'][0].update(feedback_observation_id='o0'),
            lambda t:t['actions'][0].update(channels=['wrong']),
            lambda t:t['actions'][0].update(runtime_indices=[True]),
            lambda t:t['actions'][0]['targets'].update(joint_positions=[float('nan')]),
            lambda t:t['observations'][0].update(rendering_time_s=4.),
        ]:
            t,rgb=fixture();mutate(t)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):
                encode_trace(t,rgb)


if __name__=='__main__':
    unittest.main()
