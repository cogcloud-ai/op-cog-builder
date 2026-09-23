"""Model-free seam tests. Only author/evaluator inference is replaced.

Packaging, export checks, candidate tests, case execution and Track are real.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(WORKSPACE / 'cog-workbench/src'))
import op_runner
from workbench_suite import Suite


class PipelineTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'runs').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'runs')
        self.addCleanup(self.temp.cleanup)
        self.suite = Suite()
        self.authored = json.loads((ROOT / 'tests/fixtures/authored.json').read_text())
        self.plan = json.loads((ROOT / 'tests/fixtures/plan.json').read_text())
        self.native = op_runner.invoke_cog
        self.requests = []

    def invoke(self, cog_dir, task, request_path, *args, **kwargs):
        name = Path(cog_dir).name
        bundle = json.loads(Path(request_path).read_text())
        self.requests.append((name, bundle))
        if name == 'cog-author':
            payload = self.authored
        elif name == 'cog-build-evaluator':
            if bundle['operation'] == 'plan':
                payload = self.plan
            else:
                evidence = next(e for e in bundle['evidence'] if e['id'] == 'declared-tests:length')
                passed = evidence['status'] == 'passed'
                payload = {'abstained': False, 'classification': 'pass' if passed else 'revise',
                    'reason': 'Deterministic review fixture, not live judgment.', 'test_cases': [],
                    'assessments': [{'criterion_id': 'length', 'status': 'pass' if passed else 'fail',
                        'rationale': 'Observed declared test outcome in a seam fixture.',
                        'evidence_ids': [evidence['id']], 'evidence_quote': evidence['text']}], 'findings': []}
        else:
            return self.native(cog_dir, task, request_path, *args, **kwargs)
        return self.suite.bridge(name, 'finish', {'bundle': bundle, 'result': payload,
            'provenance': {'source': 'hand-written-model-free-pipeline-fixture'}})

    def execute(self, request=None):
        path = ROOT / 'examples/request.json'
        if request is not None:
            path = Path(self.temp.name) / 'request.json'
            path.write_text(json.dumps(request))
        with patch.object(op_runner, 'invoke_cog', side_effect=self.invoke):
            return op_runner.run(ROOT, path, runs_dir=self.temp.name)

    def test_complete_candidate_and_evidence(self):
        code, result = self.execute()
        self.assertEqual(code, 0, result)
        out = result['outputs']
        self.assertEqual(out['assessment']['classification'], 'pass')
        self.assertEqual(out['acceptance'], 'not-granted')
        self.assertEqual(out['tests']['exit_code'], 0)
        track = json.loads(Path(result['track']).read_text())
        self.assertEqual([s['id'] for s in track['steps']], ['author', 'materialize', 'plan', 'verify', 'review'])
        candidate = Path(out['candidate_path'])
        for row in self.authored['files']:
            self.assertEqual((candidate / row['path']).read_text(), row['content'])
        review = next(b for n, b in self.requests if n == 'cog-build-evaluator' and b['operation'] == 'review')
        self.assertEqual(len(review['evidence']), 5)
        self.assertEqual({e['candidate_sha256'] for e in review['evidence']}, {out['source_sha256']})
        # Repeat materialization reconciles the exact receipt, never overwrites.
        build = track['steps'][1]
        rerun = self.native(WORKSPACE / 'cog-build-candidate', 'run', build['request'])
        self.assertTrue(rerun['ok'], rerun)
        self.assertEqual(rerun['payload']['path'], str(candidate))
        (candidate / 'src/task_logic.py').write_text('# changed after build\n')
        refused = self.native(WORKSPACE / 'cog-build-candidate', 'run', build['request'])
        self.assertFalse(refused['ok'], refused)
        refused = self.native(WORKSPACE / 'cog-verify-candidate', 'run', track['steps'][3]['request'])
        self.assertFalse(refused['ok'], refused)

    def test_failing_tests_reach_review_and_do_not_become_acceptance(self):
        for row in self.authored['files']:
            if row['path'] == 'src/task_logic.py':
                row['content'] = row['content'].replace("len(bundle['notes'])", "len(bundle['notes']) + 1")
        code, result = self.execute()
        self.assertEqual(code, 0, result)
        self.assertEqual(result['outputs']['assessment']['classification'], 'revise')
        self.assertNotEqual(result['outputs']['tests']['exit_code'], 0)
        self.assertEqual(result['outputs']['acceptance'], 'not-granted')

    def test_wrong_accepted_contract_stops_before_packaging(self):
        request = json.loads((ROOT / 'examples/request.json').read_text())
        request['accepted_contract_sha256'] = '0' * 64
        code, result = self.execute(request)
        self.assertEqual(code, 1, result)
        track = json.loads(Path(result['track']).read_text())
        self.assertEqual(track['failed_step'], 'materialize')
        self.assertFalse((Path(result['run_dir']) / 'candidate/cog-code-fixture').exists())
        self.assertFalse(any(n == 'cog-build-evaluator' for n, b in self.requests))

    def test_bad_author_source_is_refused(self):
        self.authored['files'] = [f for f in self.authored['files'] if f['path'] != 'src/task_logic.py']
        code, result = self.execute()
        self.assertEqual(code, 1, result)
        track = json.loads(Path(result['track']).read_text())
        self.assertEqual(track['failed_step'], 'author')

    def test_pinned_reference_comparison_records_both_envelopes(self):
        self.authored['files'].append({'path': 'tests/fixtures/shared.json',
            'content': json.dumps([{'name': 'shared', 'bundle': {'notes': 'abc'}}])})
        code, first = self.execute()
        self.assertEqual(code, 0, first)
        request = json.loads((ROOT / 'examples/request.json').read_text())
        request['reference'] = {'path': first['outputs']['candidate_path'],
            'package_sha256': first['outputs']['package_sha256'],
            'fixture_path': 'tests/fixtures/shared.json', 'criterion_id': 'length'}
        self.requests.clear()
        code, second = self.execute(request)
        self.assertEqual(code, 0, second)
        review = next(b for n, b in self.requests if n == 'cog-build-evaluator' and b['operation'] == 'review')
        evidence = next(e for e in review['evidence'] if e['id'] == 'reference-comparison')
        record = json.loads(evidence['text'])
        self.assertTrue(record['cases'][0]['normalized_match'])
        self.assertEqual(set(record['cases'][0]['outputs']), {'candidate', 'reference'})
        track = json.loads(Path(second['track']).read_text())
        verification = json.loads(Path(track['steps'][3]['request']).read_text())
        verification['reference']['package_sha256'] = '0' * 64
        path = Path(self.temp.name) / 'changed-reference.json'
        path.write_text(json.dumps(verification))
        refused = self.native(WORKSPACE / 'cog-verify-candidate', 'run', path)
        self.assertFalse(refused['ok'], refused)
