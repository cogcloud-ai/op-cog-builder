# Cog Builder

Build a pure-code Cog from a bounded brief, accept its contract, and review repaired
candidates within a fixed budget. This Op uses shared Smith machinery; model
outputs and passing tests never replace the person's final acceptance.

1. **Design** proposes the contract and pauses for acceptance before authoring.
2. **Author, materialize, plan, verify, review** retain source, package, tests,
   case observations and independent findings.
3. A `revise` review prepares a candidate-bound revision request and restarts at
   authoring under the same accepted contract. An `insufficient_evidence` review
   replans and verifies the same candidate. Other outcomes pause for final
   acceptance or rejection.

Every phase has its own native Track, requests, envelopes and candidate directory.
The cycle records all attempts and cost reservations. The default is three rounds
and twelve model-turn units; design, author, plan and review reserve one unit per
invocation (including retries). These are caps on declared work, not vendor bills.
Reservations precede invocation and are not silently refunded after interruption.
Exhaustion stops before additional work. Budgets cannot be raised on resume.

## Setup

Use the supported public sibling workspace and install its declared Pixi
environments. The suite guide provides [setup](https://github.com/cogcloud-ai/cog-op-builder/blob/main/docs/getting-started.md).
Connect and admit a compatible provider with Workbench, then activate all model
consumers in one operation:

```sh
cd ../cog-workbench
pixi run suite -- bindings
pixi run suite -- activate-op --op ../op-cog-builder --binding-id YOUR_BINDING --revision 1
cd ../op-cog-builder
pixi install
```

Activation reports already-current consumers and concrete repair commands.
Binding identity is installation state rather than task input. Changes to the
consumer, provider, model binding or Workbench host invalidate reuse as appropriate.

## Start, decide, resume

```sh
pixi run cycle -- --request examples/request.json
```

The JSON result identifies `cycle_dir` and `active_run_dir`. Read the native
pending document in `active_run_dir/pending/design.md`. Prepare a decision using
Smith, then pass it to the cycle. Substitute the returned paths:

```sh
cd ../cog-smith
pixi run op-decide -- CHILD_RUN_DIR --by YOUR_NAME --accept --output /tmp/contract-decision.json
cd ../op-cog-builder
pixi run cycle -- --resume CYCLE_DIR --decision /tmp/contract-decision.json
```

After repairs/evidence rounds, read the final candidate, test observations and
review in the active child's Track. Prepare the final decision the same way.
For rejection use `--reject-artifact --reason 'Why this artifact is unsuitable'`.
A rejection is terminal. A successful reviewer response is still awaiting your
acceptance; the final decision binds contract, source, package, evidence and
assessment digests. `decided_by` records the caller's stated name, without claiming
authenticated identity. Do not add `--resume` to `op-decide`: continuation belongs
to the cycle after the prepared decision is saved.

The Workbench Studio exposes the same start, inspect, accept/reject and resume
operations and reconstructs them from saved Tracks after reload or server restart.
For infrastructure recovery, inspect the retained error and use:

```sh
pixi run cycle -- --resume CYCLE_DIR
```

Passed work is reused only under matching request, Cog and admitted binding
identities. A successful answer durably written before interruption is reconciled
without another model turn. Failed Gates retry and consume their declared units.
No previous candidate, review or decision is overwritten.

## Inputs and repair scope

`brief` and `identity` supply a small bounded task and Smith `cog_request: 1`
identity. `kind` is `code`. Materials are data. Optional inputs include
`max_attempts`, `max_cost_units`, `revision_paths`, `test_criterion_ids`,
`reference`, `execution_policy` and designer `build_origin`.

By default only `src/task_logic.py` and `tests/test_cog.py` may change during
repair. The Author's deterministic `prepare-revision` task binds the full original
request, accepted contract, candidate digest, actual clean review and permitted
paths/criteria. Contract or out-of-scope changes are refused. Missing evidence
reuses candidate bytes and prepares new observations rather than redesigning.

Learners can leave `test_criterion_ids` empty. The declared test result is retained
as an observation for all accepted criteria; a passing test suite does not prove
those criteria or its coverage. Review still assesses authored cases, expected
behavior and source. A pinned pure-code `reference` may be compared against
1–100 authored named bundle fixtures, retaining both envelopes. It is never
modified or replaced.

Verification defaults to labelled, bounded `trusted-local` execution using the
installed candidate Python or verifier Python. It supports stdlib, PyYAML and
jsonschema. For filesystem/network/resource isolation, supply the explicit
[Docker policy](https://github.com/cogcloud-ai/cog-verify-candidate/blob/main/isolation/README.md)
with a locally available immutable image ID. Docker mode has no host fallback.
Neither verification nor this Op installs candidate environments automatically.

A designer's stable `build_origin` is retained in the accepted candidate artifact,
so its finalization operation can prove that the child belongs to the original
proposal and recheck all digests before composing the final Op.

## Compatibility and validation

`pixi run op` remains the original single-candidate operation. `pixi run cycle`
adds bounded repair orchestration using shared Op machinery 0.9.0, with no
per-Op Python logic. Sixteen model-free tests exercise the acceptance Gates,
changed-artifact refusal, reference observations, native revision preparation,
real candidate packaging/verification, repaired review and budget exhaustion.

```sh
pixi run test
cd ../cog-smith
pixi run python src/cogsmith_cli.py op check ../op-cog-builder --tests --envelope
```

The earlier [live qualification](docs/live-gates-2026-09-23.md) documents the
single-candidate implementation. New bounded-cycle tests use synthetic inference
fixtures and do not claim live model qualification, publication or deployment.

## License

Copyright 2026 OpenTeams. Licensed under the [Apache License 2.0](LICENSE).
Previously published BSD-3-Clause versions remain available under that license.
