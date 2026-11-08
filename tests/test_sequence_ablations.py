import copy
from pathlib import Path
import tempfile
import unittest
try:
    import torch
except ImportError:
    torch=None

from research_tools.sequence_ranker import tensors,ablation_configurations,build_model,parameter_count,train,predict
from tests.test_sequence_ranker import features,rows


@unittest.skipIf(torch is None,'Optional PyTorch CPU dependency is unavailable')
class TemporalCapacityControls(unittest.TestCase):
    def example(self):
        f=features()
        f['past_observations']=[.1,.2,.3,.4,.5,.6,.7,.8]
        f['observation_history_mask']=[True]*4
        f['executed_history']=[.1,.2,.3,.4]
        f['action_history_mask']=[True]*4
        return f

    def test_parameter_formula_matches_each_actual_network(self):
        for name,config in ablation_configurations(tensors([self.example()]),hidden=4).items():
            with self.subTest(variant=name):
                self.assertEqual(parameter_count(config),sum(p.numel() for p in build_model(config).parameters()))

    def test_total_three_observations_ignore_older_history_and_actions(self):
        a=self.example();b=copy.deepcopy(a)
        b['past_observations'][:4]=[99.]*4;b['executed_history']=[99.]*4
        batch=tensors([a,b]);config=ablation_configurations(batch,hidden=4)['observation-total3']
        model=build_model(config).eval()
        with torch.no_grad():scores=model(batch)
        self.assertEqual(scores[0].item(),scores[1].item())

    def test_current_control_ignores_all_past_inputs(self):
        a=self.example();b=copy.deepcopy(a)
        b['past_observations']=[99.]*8;b['executed_history']=[99.]*4
        batch=tensors([a,b]);config=ablation_configurations(batch,hidden=4)['current']
        model=build_model(config).eval()
        with torch.no_grad():scores=model(batch)
        self.assertEqual(scores[0].item(),scores[1].item())

    def test_current_capacity_control_is_nearest_integer_width(self):
        configs=ablation_configurations(tensors([self.example()]),hidden=4)
        target=parameter_count(configs['observation-action-total5']);c=configs['current-capacity-match']
        error=abs(parameter_count(c)-target)
        for w in (max(1,c['hidden']-1),c['hidden']+1):
            other=dict(c,hidden=w)
            self.assertLessEqual(error,abs(parameter_count(other)-target))

    def test_each_variant_trains_and_restores_its_own_window(self):
        data=rows()
        for row in data:
            row['features']['past_observations']=[.1,.2,.3,.4,.5,.6,.7,.8]
            row['features']['observation_history_mask']=[True]*4
            row['features']['executed_history']=[.1,.2,.3,.4]
            row['features']['action_history_mask']=[True]*4
        variants=ablation_configurations(tensors([data[0]['features']]),hidden=4)
        with tempfile.TemporaryDirectory() as directory:
            for variant in variants:
                with self.subTest(variant=variant):
                    path=Path(directory)/(variant+'.pt')
                    result=train(data,path,epochs=1,hidden=4,variant=variant)
                    restored=predict(path,[data[-1]['features']])
                    self.assertEqual(result['development_logits'],restored['scores'])
