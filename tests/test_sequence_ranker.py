import copy
from pathlib import Path
import tempfile
import unittest
try:
    import torch
except ImportError:
    torch = None

from research_tools.sequence_ranker import build_model,configuration,tensors,train,predict,validate_training_rows
from research_tools.recovery_candidates import encode_macro


def features(i=0):
    proposal=dict(schema='recovery-macro-proposal/1',kind='release-retreat-regrasp-lift',
                  coordinate_frame='world',position_unit='m',arm='left',candidate_id='fixture-candidate',
                  source_reference='software fixture',trial_id='t'+str(i),
                  available_at=dict(sim_step=1,sim_time_s=.1,wall_monotonic_ns=1),
                  retreat_world_m=[0,0,.2],pick_world_m=[0,0,0],lift_world_m=[0,0,.3],
                  orientation_wxyz=[1,0,0,0],open_wait_steps=45,close_wait_steps=12)
    return dict(trial_id='t'+str(i),profile_id='software-fixture-profile',input_scope='recovery_macro_decision',
                continuation_context_reference='software-fixture-controller-goal-budget',
                encoding_reference='software-fixture-encoding/1',
                current_observation=[float(i),.3],candidate_target=encode_macro(proposal),
                recovery_macro_candidate_spec=proposal,as_of=proposal['available_at'],
                past_observations=[0.,0.,float(i),.1],observation_history_mask=[False,True],
                executed_history=[0.,.2],action_history_mask=[False,True],
                local_success=None,autonomous_success=None)


def rows():
    result=[]
    for i in range(5):
        result.append(dict(schema='reviewed-recovery-sample/1',decision_scope='recovery_macro',
                           trial_id='t'+str(i),lineage_group='fixture-family-'+str(i),
                           decision_id='software-fixture-decision',candidate_id='fixture-candidate',
                           split='development' if i==4 else 'train',continuation_success=bool(i%2),
                           label_review_reference='software fixture only; no real review',
                           candidate_spec_reference='software fixture',candidate_available_before_decision=True,
                           target_definition='fixed-controller-continuation/v1',
                           continuation_context_reference='software-fixture-controller-goal-budget',features=features(i)))
        result[-1]['encoding_reference']='software-fixture-encoding/1'
    return result


@unittest.skipIf(torch is None, 'Optional PyTorch CPU dependency is unavailable')
class SequenceRankerSoftware(unittest.TestCase):
    def test_padding_cannot_affect_scores(self):
        a=features();b=copy.deepcopy(a)
        b['past_observations'][:2]=[1e20,-1e20];b['executed_history'][0]=1e20
        batch=tensors([a,b]);torch.manual_seed(17)
        model=build_model(configuration(batch,hidden=4));model.eval()
        with torch.no_grad():
            scores=model(batch)
        self.assertEqual(scores[0].item(),scores[1].item())

    def test_dispatch_rows_cannot_be_training_labels(self):
        with self.assertRaises(ValueError):
            validate_training_rows([features()])

    def test_lineage_leakage_and_cross_trial_labels_rejected(self):
        for mutate in [lambda r:r[-1].update(lineage_group=r[0]['lineage_group']),
                       lambda r:r[-1]['features'].update(trial_id='t0'),
                       lambda r:r[0].update(continuation_success=None),
                       lambda r:r[0].update(candidate_available_before_decision=False)]:
            r=rows();mutate(r)
            with self.assertRaises(ValueError):
                validate_training_rows(r)

    def test_training_and_weights_only_checkpoint_roundtrip(self):
        r=rows()
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'fixture.pt'
            result=train(r,p,epochs=3,hidden=4)
            prediction=predict(p,[r[-1]['features']])
            self.assertEqual(prediction['scores'],result['development_logits'])
            self.assertEqual(prediction['score_semantics'],'rank_only')
            self.assertFalse(prediction['online_authorized'])

    def test_checkpoint_rejects_different_camera_context_or_encoding(self):
        r=rows()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.pt';train(r,path,epochs=1,hidden=4)
            for key in ('continuation_context_reference','encoding_reference'):
                f=copy.deepcopy(r[-1]['features']);f[key]='another-configuration'
                with self.assertRaises(ValueError):
                    predict(path,[f])
