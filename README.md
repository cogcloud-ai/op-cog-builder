# Cog Builder: one candidate

This executable Op takes an **accepted pure-code Cog contract** through source
authoring, Smith packaging, evaluation planning, declared tests and case execution,
and independent review. It uses shared Op machinery 0.6.6, with no custom Op
Python and no provider-specific changes to the runner.

| Step | Cog | Result |
|---|---|---|
| author | cog-author, ask-composed | Complete source against the accepted contract |
| materialize | cog-build-candidate | Full checked package, expanded source, fingerprints |
| plan | cog-build-evaluator, ask-composed | Concrete acceptance cases |
| verify | cog-verify-candidate | Actual declared tests/cases and candidate-bound evidence |
| review | cog-build-evaluator, ask-composed | pass, revise, insufficient_evidence, or abstention |

The Op stops after one review. **Completed does not mean accepted:** read
`outputs.assessment.classification`; `outputs.acceptance` is always `not-granted`.
A clean `revise` assessment is a valid completed workflow. Failed candidate tests
are retained for review. Invalid envelopes, changed artifacts, invalid plans and
infrastructure failures stop at their Gate. No automatic revision, contract
approval, publishing, deployment, or replacement of a reference is implemented.

## Install and configure

This first host integration requires sibling checkouts of cog-workbench,
cog-smith, cog-author, cog-build-evaluator, cog-build-candidate, and
cog-verify-candidate. It uses Workbench's existing declared local operations API.
It is not yet a registry-resolved standalone distribution.

From this directory:

```sh
for package in cog-workbench cog-smith cog-author cog-build-evaluator cog-build-candidate cog-verify-candidate; do
  pixi install --manifest-path "../$package/pixi.toml"
done
pixi install
```

Connect/qualify provider bindings using [Workbench's existing workflow](https://github.com/cogcloud-ai/cog-workbench/blob/main/docs/tool-suite.md).
Activate one admitted binding per context Cog before running the Op:

```sh
cd ../cog-workbench
pixi run suite -- bindings
pixi run suite -- activate-composition --context cog-author --binding-id AUTHOR_BINDING --revision 1
pixi run suite -- activate-composition --context cog-build-evaluator --binding-id EVALUATOR_BINDING --revision 1
cd ../op-cog-builder
```

Replace the example binding IDs/revisions with actual admitted records. Activation
writes ignored `.op-composition.json` inside each consumer, separate from task
input. That record pins the consumer, provider revision, binding state location,
and local Workbench host code. Recompose after consumer/host changes. Revoked
or stale bindings refuse execution. The Op includes the installed record in its
consumer fingerprint when deciding reuse on resume. Binding records identify the
requested provider/model configuration, not independently attested model weights.
Native `ask` remains available on the context Cogs for other consumers.

## Run

```sh
pixi run op -- --request examples/request.json --dry-run
pixi run op -- --request examples/request.json
pixi run test
```

The example is a small character-counting contract; the input author request
contains no prewritten model response. Its contract digest is the caller's
accepted contract choice, not proof of a human identity. The model-free tests
supply separate, explicitly hand-written author/evaluator fixtures.

For a real build, replace `author_request` with a complete accepted author or
revise request. Set `accepted_contract_sha256` to SHA-256 of canonical JSON of
its contract (sorted object keys, compact separators, UTF-8, Unicode unescaped).
Supply the same digest as `author_request.contract_sha256` for the author's
own preflight check. Contract changes require a new acceptance choice.

`test_criterion_ids` states which criteria the declared test suite is relevant
to. Linking a successful test run does not prove those criteria; the evaluator
must inspect actual test coverage and observations. Missing evidence can produce
`insufficient_evidence`, even when all ordinary invocation cases complete.

Optional `reference` input names a separate pure-code package, its exact
Workbench package fingerprint, an authored JSON fixture path, and a criterion
ID. The fixture is an array of `{name, bundle, ...}` objects (1–100 cases).
Verification feeds each bundle to both Cogs and retains their full envelopes.
Normalized comparison excludes Cog identity and diagnostic prose; full problem
lists and a prose-equality observation are also retained. A changed reference
refuses comparison; differences are observations for review, not automatic failure
or acceptance. No reference source is modified.

## Artifacts and recovery

Each run writes its original input, mapped requests, full Cog envelopes, Gates,
code/model binding identities and `track.json`. The package is under
`runs/<id>/candidate/<cog-name>/`; `materialization.json` records its completed
source/package fingerprints. A matching receipt can be reconciled on retry.
Collisions, partial creations, changed packages and mismatched requests refuse
rather than overwrite. Both prior merge packages are preserved by the live replay.

```sh
pixi run op -- --resume runs/RUN_ID
```

Use resume for infrastructure recovery after inspecting the failed Track. It
reuses passed work under the shared runtime's request/package identity checks.
It does not ask the author to repair a reviewed candidate. To revise, start a
new run with a caller-prepared `operation: revise` request, the previous full
source, the same accepted contract, and explicit feedback. Automatic routing
belongs to the next lifecycle milestone.

The verifier does not install environments. It uses an installed candidate Python
when present, otherwise its own installed Python with stdlib/pyyaml/jsonschema.
The first slice therefore only supports pure code within that dependency set.
Tests and generated source run with trusted local ambient authority, not in a
sandbox. Installation or source changes after materialization may change the
package fingerprint and invalidate existing execution evidence.

## Verification

The [live qualification report](docs/implementation-2026-09-21.md) records a
fresh merge candidate built through all five steps: 13 declared tests pass,
15 planned cases executed, and the final evaluator passed all 14 criteria.
It also records an initial invalid plan and successful same-run recovery without
repeating authoring or packaging. The original merge Cog and prior candidate
remain unchanged. This live result does not turn review into release acceptance.

Nine model-free Op tests cover schema/step ordering/dry-run, full real packaging
and verification under fixed model responses, failing tests flowing into a revise
assessment, contract-digest refusal, incomplete-source refusal, artifact-change
refusal, idempotent materialization, and pinned reference comparisons. Four
Workbench adapter tests cover consumer identity, revocation, stale host/consumer
refusal, and a consumer changed during the model turn.

```sh
cd ../cog-smith
pixi run python src/cogsmith_cli.py op check ../op-cog-builder --tests --envelope
```

See the [implementation plan](https://github.com/cogcloud-ai/cog-op-builder/blob/main/docs/roadmap.md)
for the remaining acceptance Gate, bounded revision-cycle, and Workbench UI work.

## License

Copyright 2026 OpenTeams. Licensed under the [Apache License 2.0](LICENSE).
Third-party dependencies and external model services retain their own licenses
and terms. Previously published BSD-3-Clause versions remain available under
that license.

## Public preview

See the [suite guide](https://github.com/cogcloud-ai/cog-op-builder/blob/main/docs/repositories.md)
for repository roles, supported setup, and current limitations.
