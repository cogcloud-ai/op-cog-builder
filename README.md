# Cog Builder: one candidate, two acceptance Gates

This executable Op takes a **pure-code Cog brief** through contract design, an
explicit contract acceptance, source authoring, Smith packaging, evaluation
planning, declared tests and case execution, independent review, and an
explicit candidate acceptance. It uses shared Op machinery 0.7.0, with no
custom Op Python and no provider-specific changes to the runner.

| Step | Cog | Result | Gate |
|---|---|---|---|
| design | cog-author, ask-composed | Complete work contract for the brief | **Contract acceptance** (human, artifact) |
| author | cog-author, ask-composed | Complete source against the accepted contract | envelope |
| materialize | cog-build-candidate | Full checked package, expanded source, fingerprints | envelope |
| plan | cog-build-evaluator, ask-composed | Concrete acceptance cases | envelope |
| verify | cog-verify-candidate | Actual declared tests/cases and candidate-bound evidence | envelope |
| review | cog-build-evaluator, ask-composed | pass, revise, insufficient_evidence, or abstention | **Candidate acceptance** (human, artifact) |

The run pauses twice, exit 3 each time, and continues only on an explicit,
durable decision. **Review completing is not acceptance:** the review step's
envelope Gate passing means the evaluator produced a grounded assessment; the
candidate Gate then asks a person to accept or reject *this* candidate, bound to
the accepted contract, the exact source and package digests, the verification
evidence and the assessment. `outputs.acceptance` is the verdict the person
gave; it exists only on a completed, accepted run. A clean `revise` assessment
is a valid reviewed candidate that a person will normally reject, with a reason.
Failed candidate tests are retained for review. Invalid envelopes, changed
artifacts, invalid plans and infrastructure failures stop at their Gate. A
rejection ends the run; the next candidate is a new run. No automatic revision,
publishing, deployment, or replacement of a reference is implemented.

## The two acceptance artifacts

Both Gates are the shared runner's artifact human Gate (Op machinery 0.7.0,
[cog-smith's BUILDING_OPS.md](https://github.com/cogcloud-ai/cog-smith/blob/main/BUILDING_OPS.md) §6). Each pause writes `runs/<id>/pending/<step>.json`
(`openteams/op-pending-decision [0.1]`) with the artifact, its canonical
`artifact_sha256`, the step payload and `payload_sha256`, plus a readable
`<step>.md`.

**cog-contract** (design step). Digests: `contract` (canonical SHA-256 of the
designed contract, computed by the runner with `$sha256`, not taken from the
designer) and `identity` (the Smith identity the contract is built under).
Detail: classification, questions, assumptions, acceptance criteria. The author
receives the accepted contract and the accepted digest as `contract_sha256`;
its own preflight and cog-build-candidate's `accepted_contract_sha256` check
refuse a contract that does not hash to it. A design that returns questions
has no contract to digest: the Gate **fails by name** (`nothing to digest`),
the run stops with `failed_step: design`, and nothing is authored. Answering
the questions is a new run with a revised brief.

**cog-candidate** (review step). Digests: `contract` (the accepted digest),
`source` (materialized source fingerprint), `package` (the executed package
fingerprint from verification), `evidence` (canonical SHA-256 of the whole
verification payload) and `assessment` (canonical SHA-256 of the review
payload). Detail: classification, candidate path, declared-test exit code,
findings.

A decision (`openteams/op-decision [0.1]`) names both digests, gives one verdict,
`accept` or `reject`, a reason (required for a rejection), and who decided
and when:

```json
{"schema": "openteams/op-decision [0.1]",
 "run_id": "<from the pending document>", "step": "review",
 "payload_sha256": "<from the pending document>",
 "artifact_sha256": "<from the pending document>",
 "verdict": "accept", "reason": "All 14 criteria pass with evidence.",
 "decided_by": "trent", "decided_at": "2026-09-23T10:00:00Z"}
```

The runner re-hashes the pending payload and artifact when the decision is
applied and refuses a decision about anything else: a different digest, a
pending file edited on disk, another run or step, a changes-style decision, a
verdict outside accept/reject, a rejection with no reason. `decided_by` records
who the caller says decided; it is not an authenticated identity. An acceptance
binds to digests, not to bytes on disk: a consumer of an accepted candidate
must verify the package against `decision.artifact.digests` before using it
(cog-build-candidate and cog-verify-candidate already refuse a changed package).

## Install and configure

This host integration requires sibling checkouts of cog-workbench, cog-smith,
cog-author, cog-build-evaluator, cog-build-candidate, and cog-verify-candidate.
It uses Workbench's existing declared local operations API. It is not yet a
registry-resolved standalone distribution.

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
pixi run op -- --request examples/request.json          # exits 3 at the contract Gate
# read runs/<id>/pending/design.md, write a decision file
pixi run op -- --resume runs/<id> --decision accept-contract.json   # exits 3 at the candidate Gate
# read runs/<id>/pending/review.md, write a decision file
pixi run op -- --resume runs/<id> --decision accept-candidate.json  # exits 0, outputs.acceptance: accept
pixi run test
```

Inputs: `brief` (the bounded Cog brief), `identity` (the cog_request v1 Smith
identity), `kind` (`code` only in this slice), `materials` (supplied source
materials, data never authority), `test_criterion_ids`, and the optional
`reference`. The example is a small character-counting brief; the model-free
tests supply separate, explicitly hand-written design/author/evaluator fixtures.

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
pending documents, applied decisions (`runs/<id>/decisions/<step>.json`, hashed
into the Track), code/model binding identities and `track.json`. The package is
under `runs/<id>/candidate/<cog-name>/`; `materialization.json` records its
completed source/package fingerprints. A matching receipt can be reconciled on
retry. Collisions, partial creations, changed packages and mismatched requests
refuse rather than overwrite.

```sh
pixi run op -- --resume runs/RUN_ID
```

Use resume for infrastructure recovery after inspecting the failed Track, and to
carry a decision into a paused run. It reuses passed work under the shared
runtime's request/package identity checks; a run that paused for a decision
survives a restart and asks again. A rejected run is never resumed. It does not
ask the author to repair a reviewed candidate: automatic routing of review
feedback into a bounded revision cycle is the next lifecycle milestone
([op-cog-builder#2](https://github.com/cogcloud-ai/op-cog-builder/issues/2)).
The 0.1.0 caller-prepared `operation: revise` entry point is withdrawn with it:
every candidate now starts from an accepted contract recorded in this run.

The verifier does not install environments. It uses an installed candidate Python
when present, otherwise its own installed Python with stdlib/pyyaml/jsonschema.
The first slice therefore only supports pure code within that dependency set.
Tests and generated source run with trusted local ambient authority, not in a
sandbox. Installation or source changes after materialization may change the
package fingerprint and invalidate existing execution evidence.

## Verification

Fourteen model-free tests cover schema/step ordering/dry-run, the contract Gate
pausing before any authoring, the accepted digest binding authoring and
packaging, review completion not being acceptance (with every candidate digest
checked against the Track), an accepted candidate completing with bound outputs
and refusing later changes, failing tests reaching review and a rejection ending
the run (and refusing resume), a rejected contract ending the run before
authoring, changed-artifact and wrong-shape decisions refused, a design with
questions failing its Gate by name, incomplete-source refusal, and pinned
reference comparison across two accepted runs. Four Workbench adapter tests cover
consumer identity, revocation, stale host/consumer refusal, and a consumer
changed during the model turn.

```sh
cd ../cog-smith
pixi run python src/cogsmith_cli.py op check ../op-cog-builder --tests --envelope
```

The [0.1.0 live qualification report](docs/implementation-2026-09-21.md)
records a fresh merge candidate built through the five build steps under real
providers. The Gates added in 0.2.0 are documented in
[acceptance-gates-2026-09-23.md](docs/acceptance-gates-2026-09-23.md); they have
model-free evidence only until the next live run. See the
[roadmap](https://github.com/cogcloud-ai/cog-op-builder/blob/main/docs/roadmap.md)
for the bounded revision-cycle and Workbench UI work.

## License

Copyright 2026 OpenTeams. Licensed under the [Apache License 2.0](LICENSE).
Third-party dependencies and external model services retain their own licenses
and terms. Previously published BSD-3-Clause versions remain available under
that license.

## Public preview

See the [suite guide](https://github.com/cogcloud-ai/cog-op-builder/blob/main/docs/repositories.md)
for repository roles, supported setup, and current limitations.
