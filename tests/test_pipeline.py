"""Model-free seam tests. Only design/author/evaluator inference is replaced.

Packaging, export checks, candidate tests, case execution, the two acceptance
Gates, the pending/decision documents and the Track are real. The decisions
here are written by the test, exactly as a person (or Workbench) writes them:
from the pending document, naming both digests.
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
import op_spec
import op_track
from workbench_suite import Suite, digest


class PipelineTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'runs').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'runs')
        self.addCleanup(self.temp.cleanup)
        self.suite = Suite()
        self.designed = json.loads((ROOT / 'tests/fixtures/designed.json').read_text())
        self.authored = json.loads((ROOT / 'tests/fixtures/authored.json').read_text())
        self.plan = json.loads((ROOT / 'tests/fixtures/plan.json').read_text())
        self.native = op_runner.invoke_cog
        self.requests = []

    def invoke(self, cog_dir, task, request_path, *args, **kwargs):
        name = Path(cog_dir).name
        bundle = json.loads(Path(request_path).read_text())
        self.requests.append((name, bundle))
        if name == 'cog-author':
            payload = self.designed if bundle['operation'] == 'design' else self.authored
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

    def patched(self):
        return patch.object(op_runner, 'invoke_cog', side_effect=self.invoke)

    def start(self, request=None):
        path = ROOT / 'examples/request.json'
        if request is not None:
            path = Path(self.temp.name) / 'request.json'
            path.write_text(json.dumps(request))
        with self.patched():
            return op_runner.run(ROOT, path, runs_dir=self.temp.name)

    def resume(self, result, decision=None):
        with self.patched():
            return op_runner.resume(ROOT, result['run_dir'], decision_path=decision)

    def pending(self, result):
        return json.loads(Path(result['pending']).read_text())

    def decide(self, result, verdict='accept', reason='Accepted in a seam test.', **overrides):
        pending = self.pending(result)
        doc = {'schema': op_runner.DECISION_SCHEMA, 'run_id': pending['run_id'], 'step': pending['step'],
               'payload_sha256': pending['payload_sha256'], 'artifact_sha256': pending['artifact_sha256'],
               'verdict': verdict, 'reason': reason, 'decided_by': 'trent', 'decided_at': op_track.utc_now()}
        doc.update(overrides)
        path = Path(self.temp.name) / f"decision-{pending['step']}-{len(self.requests)}.json"
        path.write_text(json.dumps(doc))
        return str(path)

    def track(self, result):
        return json.loads(Path(result['track']).read_text())

    def step(self, track, sid):
        return next(s for s in track['steps'] if s['id'] == sid)

    def through_review(self, request=None):
        """Start, accept the contract, and stop at the candidate Gate."""
        code, paused = self.start(request)
        self.assertEqual(code, 3, paused)
        code, result = self.resume(paused, self.decide(paused))
        self.assertEqual(code, 3, result)
        self.assertEqual(result['step'], 'review')
        return result

    def test_contract_gate_pauses_before_any_authoring(self):
        code, result = self.start()
        self.assertEqual(code, 3, result)
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(result['step'], 'design')
        pending = self.pending(result)
        self.assertEqual(pending['decides'], 'artifact')
        artifact = pending['artifact']
        self.assertEqual(artifact['kind'], 'cog-contract')
        self.assertEqual(artifact['id'], 'openteams/cog-code-fixture')
        self.assertEqual(artifact['digests']['contract'], digest(self.designed['contract']))
        self.assertEqual(artifact['digests']['contract'], self.designed['contract_sha256'])
        self.assertEqual(artifact['detail']['classification'], 'designed')
        self.assertEqual(pending['artifact_sha256'], op_runner.canonical_sha256(artifact))
        track = self.track(result)
        self.assertEqual(track['status'], 'paused')
        self.assertEqual(self.step(track, 'design')['status'], 'awaiting-decision')
        self.assertEqual([s['status'] for s in track['steps'][1:]], ['not-reached'] * 5)
        self.assertEqual([n for n, _ in self.requests], ['cog-author'])
        self.assertFalse((Path(result['run_dir']) / 'candidate').exists())
        # resuming without a decision asks again and runs nothing
        code, again = self.resume(result)
        self.assertEqual(code, 3)
        self.assertEqual(len(self.requests), 1)

    def test_accepted_contract_binds_authoring_and_packaging_to_its_digest(self):
        code, paused = self.start()
        code, result = self.resume(paused, self.decide(paused, reason='Criteria are testable.'))
        self.assertEqual(code, 3, result)
        accepted = self.pending(paused)['artifact']['digests']['contract']
        author = next(b for n, b in self.requests if n == 'cog-author' and b['operation'] == 'author')
        self.assertEqual(author['contract_sha256'], accepted)
        self.assertEqual(author['contract'], self.designed['contract'])
        track = self.track(result)
        design = self.step(track, 'design')
        self.assertEqual(design['status'], 'passed')
        self.assertEqual(design['gate']['status'], 'pass')
        self.assertEqual(design['decision']['value']['verdict'], 'accept')
        self.assertEqual(design['decision']['value']['decided_by'], 'trent')
        build = json.loads(Path(self.step(track, 'materialize')['request']).read_text())
        self.assertEqual(build['accepted_contract_sha256'], accepted)
        self.assertEqual(build['author_request'], author)
        self.assertEqual([n for n, _ in self.requests].count('cog-author'), 2)   # design never re-ran

    def test_review_completion_is_not_acceptance(self):
        result = self.through_review()
        pending = self.pending(result)
        artifact = pending['artifact']
        self.assertEqual(artifact['kind'], 'cog-candidate')
        self.assertEqual(artifact['detail']['classification'], 'pass')
        self.assertEqual(artifact['detail']['declared_tests_exit_code'], 0)
        track = self.track(result)
        self.assertEqual(track['status'], 'paused')
        self.assertNotIn('outputs', result)
        review = self.step(track, 'review')
        self.assertEqual(review['status'], 'awaiting-decision')
        self.assertEqual(review['gate']['envelope_status'], 'pass')
        materialized = json.loads(Path(self.step(track, 'materialize')['envelope']).read_text())['payload']
        verified = json.loads(Path(self.step(track, 'verify')['envelope']).read_text())['payload']
        reviewed = json.loads(Path(review['envelope']).read_text())['payload']
        self.assertEqual(artifact['digests'], {
            'contract': self.designed['contract_sha256'],
            'source': materialized['source_sha256'],
            'package': verified['package_sha256'],
            'evidence': digest(verified),
            'assessment': digest(reviewed)})
        self.assertEqual(artifact['detail']['candidate_path'], materialized['path'])

    def test_accepted_candidate_completes_with_bound_outputs_and_evidence(self):
        result = self.through_review()
        pending = self.pending(result)
        code, done = self.resume(result, self.decide(result, reason='All criteria pass with evidence.'))
        self.assertEqual(code, 0, done)
        out = done['outputs']
        self.assertEqual(out['acceptance'], 'accept')
        self.assertEqual(out['accepted_by'], 'trent')
        self.assertEqual(out['accepted_artifact_sha256'], pending['artifact_sha256'])
        self.assertEqual(out['contract_sha256'], self.designed['contract_sha256'])
        self.assertEqual(out['contract_accepted_by'], 'trent')
        self.assertEqual(out['assessment']['classification'], 'pass')
        self.assertEqual(out['tests']['exit_code'], 0)
        self.assertEqual(out['source_sha256'], pending['artifact']['digests']['source'])
        self.assertEqual(out['package_sha256'], pending['artifact']['digests']['package'])
        track = self.track(done)
        self.assertEqual(track['status'], 'completed')
        self.assertEqual([s['id'] for s in track['steps']],
                         ['design', 'author', 'materialize', 'plan', 'verify', 'review'])
        self.assertEqual(len(track['resumes']), 2)
        self.assertEqual(self.step(track, 'review')['decision']['value']['artifact'], pending['artifact'])
        candidate = Path(out['candidate_path'])
        for row in self.authored['files']:
            self.assertEqual((candidate / row['path']).read_text(), row['content'])
        review = next(b for n, b in self.requests if n == 'cog-build-evaluator' and b['operation'] == 'review')
        self.assertEqual(len(review['evidence']), 5)
        self.assertEqual({e['candidate_sha256'] for e in review['evidence']}, {out['source_sha256']})
        # Repeat materialization reconciles the exact receipt, never overwrites.
        build = self.step(track, 'materialize')
        rerun = self.native(WORKSPACE / 'cog-build-candidate', 'run', build['request'])
        self.assertTrue(rerun['ok'], rerun)
        self.assertEqual(rerun['payload']['path'], str(candidate))
        # An accepted candidate changed afterwards no longer matches the
        # digests the acceptance is bound to: the deterministic Cogs refuse it.
        (candidate / 'src/task_logic.py').write_text('# changed after acceptance\n')
        refused = self.native(WORKSPACE / 'cog-build-candidate', 'run', build['request'])
        self.assertFalse(refused['ok'], refused)
        refused = self.native(WORKSPACE / 'cog-verify-candidate', 'run', self.step(track, 'verify')['request'])
        self.assertFalse(refused['ok'], refused)

    def test_failing_tests_reach_review_and_a_rejection_ends_the_run(self):
        for row in self.authored['files']:
            if row['path'] == 'src/task_logic.py':
                row['content'] = row['content'].replace("len(bundle['notes'])", "len(bundle['notes']) + 1")
        result = self.through_review()
        pending = self.pending(result)
        self.assertEqual(pending['artifact']['detail']['classification'], 'revise')
        self.assertNotEqual(pending['artifact']['detail']['declared_tests_exit_code'], 0)
        calls = len(self.requests)
        code, ended = self.resume(result, self.decide(result, 'reject', 'Declared tests fail; revise the count.'))
        self.assertEqual(code, 1, ended)
        self.assertEqual(ended['status'], 'rejected')
        self.assertEqual(ended['step'], 'review')
        self.assertEqual(ended['reason'], 'Declared tests fail; revise the count.')
        track = self.track(ended)
        self.assertEqual(track['status'], 'rejected')
        self.assertIsNone(track.get('outputs'))
        review = self.step(track, 'review')
        self.assertEqual(review['status'], 'rejected')
        self.assertEqual(review['gate']['status'], 'rejected')
        self.assertEqual(review['decision']['value']['verdict'], 'reject')
        self.assertEqual(review['decision']['value']['artifact'], pending['artifact'])
        self.assertTrue(Path(review['decision']['decision']).exists())
        self.assertEqual(len(self.requests), calls)
        with self.assertRaises(op_spec.OpSpecError) as caught:
            self.resume(ended)
        self.assertIn('rejection is final', '\n'.join(caught.exception.problems))
        self.assertEqual(len(self.requests), calls)

    def test_rejected_contract_ends_the_run_before_authoring(self):
        code, paused = self.start()
        code, ended = self.resume(paused, self.decide(paused, 'reject', 'The abstention rule is wrong.'))
        self.assertEqual(code, 1, ended)
        track = self.track(ended)
        self.assertEqual(track['status'], 'rejected')
        self.assertEqual(self.step(track, 'design')['status'], 'rejected')
        self.assertEqual([s['status'] for s in track['steps'][1:]], ['not-reached'] * 5)
        self.assertEqual([n for n, _ in self.requests], ['cog-author'])
        self.assertFalse((Path(ended['run_dir']) / 'candidate').exists())

    def test_a_changed_artifact_invalidates_a_decision(self):
        code, paused = self.start()
        # a decision about a different contract digest
        with self.assertRaises(op_spec.OpSpecError) as caught:
            self.resume(paused, self.decide(paused, artifact_sha256='0' * 64))
        self.assertIn('something else', '\n'.join(caught.exception.problems))
        # the pending artifact edited on disk, its digest kept consistent
        pending_path = Path(paused['pending'])
        pending = json.loads(pending_path.read_text())
        pending['artifact']['digests']['contract'] = 'f' * 64
        pending['artifact_sha256'] = op_runner.canonical_sha256(pending['artifact'])
        pending_path.write_text(json.dumps(pending))
        with self.assertRaises(op_spec.OpSpecError) as caught:
            self.resume(paused, self.decide(paused))
        self.assertIn('changed on disk', '\n'.join(caught.exception.problems))
        # a decision with no verdict, or a changes-style decisions list
        with self.assertRaises(op_spec.OpSpecError):
            self.resume(paused, self.decide(paused, verdict='approve'))
        self.assertEqual(self.track(paused)['status'], 'paused')
        self.assertEqual(len(self.requests), 1)

    def test_a_design_with_questions_fails_its_gate_by_name(self):
        self.designed = {'abstained': False, 'classification': 'needs_input', 'reason': '',
            'questions': ['Which Unicode normalization form applies?'], 'assumptions': [],
            'contract': None, 'smith_request': None, 'files': []}
        code, result = self.start()
        self.assertEqual(code, 1, result)
        track = self.track(result)
        self.assertEqual(track['status'], 'failed')
        self.assertEqual(track['failed_step'], 'design')
        design = self.step(track, 'design')
        self.assertEqual(design['status'], 'failed')
        self.assertEqual(design['gate']['decides'], 'artifact')
        self.assertTrue(any('nothing to digest' in r for r in design['gate']['reasons']), design['gate'])
        self.assertFalse((Path(result['run_dir']) / 'pending').exists())
        self.assertEqual([n for n, _ in self.requests], ['cog-author'])
        envelope = json.loads(Path(design['envelope']).read_text())
        self.assertEqual(envelope['payload']['questions'], ['Which Unicode normalization form applies?'])

    def test_bad_author_source_is_refused(self):
        self.authored['files'] = [f for f in self.authored['files'] if f['path'] != 'src/task_logic.py']
        code, paused = self.start()
        code, result = self.resume(paused, self.decide(paused))
        self.assertEqual(code, 1, result)
        track = self.track(result)
        self.assertEqual(track['failed_step'], 'author')
        self.assertEqual(self.step(track, 'design')['status'], 'passed')

    def test_pinned_reference_comparison_records_both_envelopes(self):
        self.authored['files'].append({'path': 'tests/fixtures/shared.json',
            'content': json.dumps([{'name': 'shared', 'bundle': {'notes': 'abc'}}])})
        first = self.through_review()
        code, first = self.resume(first, self.decide(first))
        self.assertEqual(code, 0, first)
        request = json.loads((ROOT / 'examples/request.json').read_text())
        request['reference'] = {'path': first['outputs']['candidate_path'],
            'package_sha256': first['outputs']['package_sha256'],
            'fixture_path': 'tests/fixtures/shared.json', 'criterion_id': 'length'}
        self.requests.clear()
        second = self.through_review(request)
        review = next(b for n, b in self.requests if n == 'cog-build-evaluator' and b['operation'] == 'review')
        evidence = next(e for e in review['evidence'] if e['id'] == 'reference-comparison')
        record = json.loads(evidence['text'])
        self.assertTrue(record['cases'][0]['normalized_match'])
        self.assertEqual(set(record['cases'][0]['outputs']), {'candidate', 'reference'})
        track = self.track(second)
        verification = json.loads(Path(self.step(track, 'verify')['request']).read_text())
        verification['reference']['package_sha256'] = '0' * 64
        path = Path(self.temp.name) / 'changed-reference.json'
        path.write_text(json.dumps(verification))
        refused = self.native(WORKSPACE / 'cog-verify-candidate', 'run', path)
        self.assertFalse(refused['ok'], refused)


if __name__ == '__main__':
    unittest.main()
