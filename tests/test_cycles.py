"""Native packaging/verification/revision handoff around synthetic inference."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
import unittest

import test_pipeline as fixtures
import op_cycle
import op_track


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
        result = fixtures.PipelineTests.invoke(self, cog_dir, task, request_path, *args, **kwargs)
        if Path(cog_dir).name == 'cog-build-evaluator' and bundle.get('operation') == 'review':
            payload = result['payload']
            if getattr(self, 'outside_scope', False):
                payload['findings'] = [{'severity':'error','quote':next(row['content'][:40] for row in bundle['files'] if row['path']=='COG.md'),'detail':'Unrelated contract change','path':'COG.md'}]
            if getattr(self, 'missing_evidence_once', False):
                self.missing_evidence_once = False
                payload['classification'] = 'insufficient_evidence'
                payload['assessments'][0]['status'] = 'not_tested'
            result = self.suite.bridge('cog-build-evaluator','finish',{'bundle':bundle,'result':payload,'provenance':{'source':'synthetic-cycle-test'}})
        return result

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
        verification=next(row for row in tracks[0]['steps'] if row['id']=='verify')
        report=json.loads(Path(verification['envelope']).read_text())['payload']
        self.assertIn('Synthetic first candidate needs repair',json.dumps(report['review_request']['evidence']))
        self.assertTrue(all('timeout_seconds' in row for row in report['execution']['records']))
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

    def test_out_of_scope_error_is_terminal_with_reason_and_no_repeated_prepare(self):
        self.outside_scope = True
        code, contract = self.start()
        code, refused = self.resume(contract,self.decide(contract))
        self.assertEqual(code,1,refused);self.assertEqual(refused['status'],'refused',refused)
        self.assertIn('scope',refused['reason'].lower())
        state=json.loads(Path(refused['cycle']).read_text())
        track=json.loads((Path(state['phases'][-1]['run_dir'])/'track.json').read_text())
        failed=next(row for row in track['steps'] if row['id']=='revision-request')
        self.assertEqual(failed['status'],'failed')
        self.assertEqual(json.loads(Path(failed['envelope']).read_text())['raw']['error']['code'],'invalid-revision')
        before=len(self.requests)
        with patch.object(fixtures.op_runner,'invoke_cog') as invoke:
            code, again=op_cycle.resume(fixtures.ROOT,refused['cycle_dir'])
        invoke.assert_not_called();self.assertEqual(len(self.requests),before)
        self.assertEqual(again['status'],'refused')

    def test_missing_evidence_round_reuses_candidate_and_policy(self):
        self.missing_evidence_once = True
        code, contract = self.start()
        self.bad=copy.deepcopy(self.authored)
        code, candidate=self.resume(contract,self.decide(contract))
        self.assertEqual(code,3,candidate);self.assertEqual(candidate['attempts'],2)
        self.assertEqual([b['operation'] for name,b in self.requests if name=='cog-author'],['design','author'])
        state=json.loads(Path(candidate['cycle']).read_text())
        materialized=[]
        for phase in state['phases']:
            track=json.loads((Path(phase['run_dir'])/'track.json').read_text())
            materialize=next(row for row in track['steps'] if row['id']=='materialize')
            materialized.append(json.loads(Path(materialize['envelope']).read_text())['payload']['path'])
            verify=next(row for row in track['steps'] if row['id']=='verify')
            self.assertEqual(json.loads(Path(verify['request']).read_text())['execution_policy']['timeout_seconds'],7)
        self.assertEqual(materialized[0],materialized[1])
        self.assertEqual(candidate['cost_units_reserved'],6)

    def test_mid_repair_cost_exhaustion_preserves_new_candidate_before_next_plan(self):
        code, contract=self.start(cost=5)
        code, stopped=self.resume(contract,self.decide(contract))
        self.assertEqual(stopped['status'],'budget-exhausted');self.assertEqual(stopped['cost_units_reserved'],5)
        self.assertEqual([b['operation'] for name,b in self.requests if name=='cog-author'],['design','author','revise'])
        self.assertEqual([b['operation'] for name,b in self.requests if name=='cog-build-evaluator'],['plan','review'])
        state=json.loads(Path(stopped['cycle']).read_text())
        track=json.loads((Path(state['phases'][-1]['run_dir'])/'track.json').read_text())
        materialized=next(row for row in track['steps'] if row['id']=='materialize')
        self.assertTrue(Path(json.loads(Path(materialized['envelope']).read_text())['payload']['path']).is_dir())
        with patch.object(fixtures.op_runner,'invoke_cog') as invoke:
            op_cycle.resume(fixtures.ROOT,stopped['cycle_dir'])
        invoke.assert_not_called()

    def test_native_answer_survives_interruption_without_second_author_turn(self):
        code,contract=self.start()
        save=op_track.save
        def interrupt(track,directory):
            if any(row['id']=='author' and row['status']=='passed' for row in track['steps']):
                raise OSError('Synthetic interruption after durable author answer')
            return save(track,directory)
        with patch.object(op_track,'save',side_effect=interrupt),self.assertRaises(OSError):
            self.resume(contract,self.decide(contract))
        state=json.loads(Path(contract['cycle']).read_text())
        self.assertEqual(state['status'],'running');self.assertEqual(state['cost_units_reserved'],2)
        code,candidate=self.resume(contract)
        self.assertEqual(code,3,candidate)
        self.assertEqual([b['operation'] for name,b in self.requests if name=='cog-author'],['design','author','revise'])
