"""Native packaging/verification/revision handoff around synthetic inference."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
import unittest

import test_pipeline as fixtures
import op_cycle


class BuilderCycleTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    decide = fixtures.PipelineTests.decide
    pending = fixtures.PipelineTests.pending

    def invoke(self, cog_dir, task, request_path, *args, **kwargs):
        if task == 'prepare-revision':
            return self.native(cog_dir, task, request_path, *args, **kwargs)
        bundle = json.loads(Path(request_path).read_text())
        if Path(cog_dir).name == 'cog-author' and bundle.get('operation') in ('author', 'revise'):
            self.requests.append(('cog-author', bundle))
            payload = self.bad if bundle['operation'] == 'author' else self.authored
            return self.suite.bridge('cog-author', 'finish', {'bundle': bundle, 'result': payload,
                'provenance': {'source': 'synthetic-cycle-test-not-live-inference'}})
        return fixtures.PipelineTests.invoke(self, cog_dir, task, request_path, *args, **kwargs)

    def start(self, attempts=3, cost=12, policy=None):
        self.bad = copy.deepcopy(self.authored)
        test = next(row for row in self.bad['files'] if row['path'] == 'tests/test_cog.py')
        test['content'] += '\nclass RepairRequired(unittest.TestCase):\n    def test_repair_required(self):\n        self.fail("Synthetic first candidate needs repair")\n'
        request = json.loads((fixtures.ROOT / 'examples/request.json').read_text())
        request.update(execution_policy=policy or {'mode':'trusted-local','timeout_seconds':7},max_attempts=attempts, max_cost_units=cost,
                       build_origin={'proposal_sha256': 'a'*64, 'missing_cog_id': 'missing-'+'b'*64})
        path = Path(self.temp.name) / 'cycle-request.json'; path.write_text(json.dumps(request))
        with patch.object(fixtures.op_runner, 'invoke_cog', side_effect=self.invoke):
            return op_cycle.start(fixtures.ROOT, path, cycles_dir=self.temp.name)

    def resume(self, output, decision=None):
        with patch.object(fixtures.op_runner, 'invoke_cog', side_effect=self.invoke):
            return op_cycle.resume(fixtures.ROOT, output['cycle_dir'], decision)

    def test_failed_candidate_is_repaired_without_redesign_and_retains_both_reviews(self):
        code, first = self.start(); self.assertEqual(code, 3, first)
        code, candidate = self.resume(first, self.decide(first)); self.assertEqual(code, 3, candidate)
        self.assertEqual(candidate['step'], 'review'); self.assertEqual(candidate['attempts'], 2)
        author_requests = [b for name, b in self.requests if name == 'cog-author']
        self.assertEqual([r['operation'] for r in author_requests], ['design', 'author', 'revise'])
        self.assertEqual(author_requests[1]['contract'], author_requests[2]['contract'])
        self.assertEqual(author_requests[2]['revision']['allowed_change_scope']['paths'], ['src/task_logic.py', 'tests/test_cog.py'])
        state = json.loads(Path(candidate['cycle']).read_text())
        tracks = [json.loads((Path(p['run_dir']) / 'track.json').read_text()) for p in state['phases']]
        reviews = [next(r for r in track['steps'] if r['id'] == 'review') for track in tracks]
        self.assertEqual(json.loads(Path(reviews[0]['envelope']).read_text())['payload']['classification'], 'revise')
        self.assertEqual(json.loads(Path(reviews[1]['envelope']).read_text())['payload']['classification'], 'pass')
        self.assertNotEqual(Path(state['phases'][0]['run_dir']), Path(state['phases'][1]['run_dir']))
        for track in tracks:
            verified = next(row for row in track['steps'] if row['id'] == 'verify')
            self.assertEqual(json.loads(Path(verified['request']).read_text())['execution_policy']['timeout_seconds'], 7)
            materialized = next(row for row in track['steps'] if row['id'] == 'materialize')
            self.assertTrue(Path(json.loads(Path(materialized['envelope']).read_text())['payload']['path']).is_dir())
        self.assertEqual(author_requests[2]['revision']['accepted_contract_sha256'], self.pending(first)['artifact']['digests']['contract'])
        artifact = self.pending(candidate)['artifact']
        self.assertEqual(artifact['detail']['build_origin'], {'proposal_sha256': 'a'*64, 'missing_cog_id': 'missing-'+'b'*64})
        code, accepted = self.resume(candidate, self.decide(candidate)); self.assertEqual(code, 0, accepted)
        self.assertEqual(accepted['outputs']['acceptance'], 'accept')
        self.assertEqual(accepted['cost_units_reserved'], 7)

    def test_exhausted_attempt_budget_keeps_failed_candidate_and_review(self):
        code, contract = self.start(attempts=1)
        code, stopped = self.resume(contract, self.decide(contract))
        self.assertEqual(code, 1, stopped); self.assertEqual(stopped['status'], 'budget-exhausted')
        self.assertEqual(stopped['attempts'], 1)
        self.assertTrue((Path(stopped['run_dir']) / 'candidate/cog-code-fixture').is_dir())
        self.assertEqual([b['operation'] for name, b in self.requests if name == 'cog-author'], ['design', 'author'])

    def test_cost_exhaustion_retains_no_extra_author_invocation(self):
        code, contract = self.start(cost=1)
        code, stopped = self.resume(contract, self.decide(contract))
        self.assertEqual(stopped['status'], 'budget-exhausted')
        self.assertEqual(stopped['cost_units_reserved'], 1)
        self.assertEqual([b['operation'] for name,b in self.requests if name=='cog-author'], ['design'])

    def test_all_transition_specs_forward_policy(self):
        phases = fixtures.op_spec.cycle_phases(fixtures.op_spec.load(fixtures.ROOT/'op.yaml').doc)
        for outcome, phase in phases.items():
            verify = next(s for s in phase['steps'] if s['id']=='verify')
            self.assertEqual(verify['input']['execution_policy'], {'$from':'inputs.execution_policy'}, outcome)
