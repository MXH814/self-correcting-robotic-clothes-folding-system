import copy
import json
from pathlib import Path
import unittest

from research_tools.shared_context import canonical_bytes, content_hash, freeze_context, shared_reference


class SharedConfigurationIdentity(unittest.TestCase):
    def source(self):
        path=Path(__file__).resolve().parents[1]/'docs/research/zhangmingbo/full-recovery-chain-20261108/continuation-context.json'
        return json.loads(path.read_text(encoding='utf-8'))

    def freeze(self,source):
        return freeze_context(source,'software-profile','TCLC_018')

    def test_per_trial_identity_does_not_change_shared_configuration(self):
        a=self.source();b=copy.deepcopy(a)
        b['trial_id']='another-real-trial'
        b['target']['initial_point_cloud_sha256']='a'*64
        b['context_status']='another administrative status'
        self.assertEqual(shared_reference(self.freeze(a)),shared_reference(self.freeze(b)))
        self.assertNotIn(a['trial_id'].encode(),canonical_bytes(self.freeze(a)))
        self.assertNotIn(a['target']['initial_point_cloud_sha256'].encode(),canonical_bytes(self.freeze(a)))

    def test_camera_change_cannot_alias_same_context(self):
        a=self.source();b=copy.deepcopy(a);b['camera']['resolution_wh']=[400,300]
        self.assertNotEqual(content_hash(self.freeze(a)),content_hash(self.freeze(b)))

    def test_controller_budget_or_target_changes_cannot_alias(self):
        for mutate in [lambda c:c['budget'].update(retry_count=1),
                       lambda c:c['controller'].update(macro_motion_sample_scale_m=.04),
                       lambda c:c['target'].update(minimum_ratio=.9)]:
            a=self.source();b=copy.deepcopy(a);mutate(b)
            with self.subTest(change=mutate):
                self.assertNotEqual(shared_reference(self.freeze(a)),shared_reference(self.freeze(b)))

    def test_unreviewed_extra_fields_and_missing_initial_binding_rejected(self):
        a=self.source();a['new_sensor']='undeclared'
        with self.assertRaises(ValueError):self.freeze(a)
        a=self.source();del a['target']['initial_point_cloud_sha256']
        with self.assertRaises(ValueError):self.freeze(a)

    def test_development_proxy_cannot_be_relabeled_srs(self):
        a=self.source();a['target']['quality_is_srs_acceptance']=True
        with self.assertRaises(ValueError):self.freeze(a)
