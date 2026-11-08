import unittest
from research_tools.trial_outcomes import summarize


class TrialDescriptions(unittest.TestCase):
    def row(self,trial='one',**extra):
        return dict(trial_id=trial,method='rule',block_id='slip',**extra)

    def test_upstream_success_is_not_autonomous_label(self):
        result=summarize([self.row(upstream_success=True,autonomous_success=None)])
        self.assertEqual(result['groups'][0]['unknown_autonomous_outcomes'],1)
        self.assertEqual(result['groups'][0]['confirmed_autonomous_successes'],0)
        self.assertIsNone(result['causal_effect'])

    def test_duplicates_cannot_inflate_trial_count(self):
        with self.assertRaises(ValueError):
            summarize([self.row(),self.row()])

    def test_known_outcomes_need_actual_audit_reference(self):
        with self.assertRaises(ValueError):
            summarize([self.row(autonomous_success=True)])

    def test_unknown_and_failure_are_separate(self):
        rows=[self.row(autonomous_success=None),self.row('two',autonomous_success=False,
                                                       label_audit='audited',review_reference='review/2')]
        group=summarize(rows)['groups'][0]
        self.assertEqual(group['unknown_autonomous_outcomes'],1)
        self.assertEqual(group['confirmed_autonomous_failures'],1)
