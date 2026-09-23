# Explicit contract and candidate acceptance Gates (0.2.0)

Closes the first acceptance criteria of
[op-cog-builder#1](https://github.com/cogcloud-ai/op-cog-builder/issues/1) and
plan gap 3 ("artifact acceptance Gates") in the coglab builder plan. The 0.1.0
Op started from a caller-supplied contract digest and always returned
`acceptance: not-granted`. It now starts from a brief, pauses for an explicit
decision over the exact designed contract, and pauses again for an explicit
decision over the exact reviewed candidate.

## What changed, and where

| Component | Change | Verification |
|---|---|---|
| cog-smith Op machinery 0.7.0 | `gate.decides: artifact` with a declared `artifact` (kind, digests, id, summary, detail); `$sha256` mapping operator; artifact pending documents and decisions; `rejected` step/run status; rejected runs never resumed; no write grant from an artifact decision | 30 new tests (`tests/test_op_artifact_gate.py`); 584 earlier tests unchanged; rolled out to op-cog-builder, op-builder-smoke, op-project-triage, op-triage-survey (each suite re-run) |
| op-cog-builder 0.2.0 | `design` step first; contract Gate on it; candidate Gate on `review`; inputs are brief/identity/kind/materials; outputs carry the verdicts, who decided, and the accepted artifact digest | 14 model-free tests; Smith Op check passes |
| cog-author, cog-build-candidate, cog-verify-candidate, cog-build-evaluator, cog-workbench | unchanged | existing suites |

The runner is unchanged in every Op that does not declare an artifact Gate: a
changes decision, a write grant, and every 0.6.x Track read the same.

## The suite boundaries, kept

- **The coordinating Op owns the lifecycle decision points.** Both Gates are
  declared in `op.yaml`; the artifact each asks about is composed from step
  results by closed mapping expressions. No per-Op Python.
- **Cogs own bounded work.** cog-author designs and authors; the deterministic
  Cogs materialize and verify. None of them decides acceptance. The author's
  preflight and cog-build-candidate's `accepted_contract_sha256` check are the
  seams through which the accepted digest is enforced, unchanged.
- **Workbench is the client.** It will render pending documents and write
  decisions ([cog-workbench#1](https://github.com/cogcloud-ai/cog-workbench/issues/1));
  the runner's pending/decision documents are the interface, and a decision
  written by hand is the same decision.
- **Smith stays deterministic.** The machinery gained a Gate shape and a
  digest operator, not judgment.

## What a decision is, and is not

- It is bound to digests: `contract` and `identity` for a contract;
  `contract`, `source`, `package`, `evidence` and `assessment` for a
  candidate. The runner computes `contract`, `evidence` and `assessment` itself
  (`$sha256`); `source` and `package` are the deterministic Cogs' reported
  fingerprints, which they re-check against bytes on every use.
- It is re-validated at application: the pending payload and artifact are
  re-hashed and compared to the Track, so an edited pending file, a decision
  about another digest, run or step, or a decision of the wrong shape is
  refused, and the run stays paused.
- It survives a restart: a paused run asks again on any resume without a
  decision, and re-runs nothing.
- It is final when it is a rejection: the step and the run are `rejected`,
  later steps stay `not-reached`, and a resume is refused by name.
- It is **not** an authenticated approval. `decided_by` is what the caller
  wrote. Authenticating the decider is invocation-environment work
  (Workbench), outside the runner.
- It is **not** a guarantee about bytes on disk after the decision. An
  acceptance names digests; a consumer of an accepted candidate verifies the
  package against them before use.

## Withdrawn

The 0.1.0 entry point that accepted a caller-prepared `operation: revise`
request with prior source is gone: the Op has no conditional steps, and every
candidate now starts from a contract accepted in the same run. Revision under
the same accepted contract, with the evaluator's findings and the rejection
reason as feedback, is the next milestone
([op-cog-builder#2](https://github.com/cogcloud-ai/op-cog-builder/issues/2)).
The 0.1.0 live qualification run remains valid evidence for the five build
steps; the Gates have model-free evidence only until the next live run.

## Failure and refusal behaviour exercised by the tests

| Case | Behaviour |
|---|---|
| Designer returns questions (no contract) | Contract Gate fails by name (`nothing to digest`); `failed_step: design`; nothing authored; no pending document |
| Contract rejected | Run `rejected` before authoring; no candidate directory |
| Decision names another artifact digest | Refused: "decided about something else"; run stays paused |
| Pending artifact edited on disk (digest kept consistent) | Refused: "changed on disk"; run stays paused |
| Changes-style verdict on an artifact Gate | Refused; run stays paused |
| Resume without a decision | Pauses again; nothing re-run |
| Candidate accepted | `outputs.acceptance: accept`, `accepted_by`, `accepted_artifact_sha256`; source/package digests equal the accepted artifact's |
| Candidate accepted, then edited | cog-build-candidate and cog-verify-candidate refuse the recorded requests |
| Failing declared tests | Review classifies `revise`; the Gate shows it; a rejection with a reason ends the run and refuses resume |
