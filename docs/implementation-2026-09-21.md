# First executable Cog Builder slice

The Op owns five steps: author, materialize, plan, verify, review. The existing
shared Op runtime is unchanged at machinery 0.6.6. This implementation starts
from an accepted pure-code contract and stops after one review; it does not
implement brief intake, generalized artifact approval, automatic revision,
publication or the future Workbench lifecycle UI.

## Components and tests

| Component | Change | Verification |
|---|---|---|
| op-cog-builder | Declarative five-step package; real deterministic stages under model fixtures | 9 tests; Smith Op check passes with no warnings |
| cog-build-candidate | Checked source export/materialization, receipt reconciliation, collision refusal | 3 tests; runnable hand-written example; Smith check passes |
| cog-verify-candidate | Declared tests/cases, exact source/package evidence, optional pinned reference comparison | 2 contract tests plus Op integration tests; runnable example; Smith check passes |
| cog-author | Opt-in composed usage task; native ask retained | 23 tests; Smith check passes |
| cog-build-evaluator | Opt-in composed usage task; native ask retained | 21 tests; Smith check passes |
| cog-workbench | Explicit composition activation, canonical usage adapter, consumer recheck after turn | 67 tests, including 4 adapter regressions |

Expected existing Workbench ResourceWarnings remain; its tests pass. Pipeline
infrastructure is hand-authored. Model-free author/evaluator responses are
explicit fixtures and do not establish model quality. The failing-candidate
fixture actually fails its declared tests and reaches a revise assessment;
workflow completion never becomes acceptance. The changed-package and pinned
reference tests use actual package bytes and native declared operations.

The native usage adapter preserves the context Cog identity and full provider
provenance. Its binding is installation state, not task input. Revoked bindings,
stale consumer/host fingerprints, and a consumer changed during a model turn
are refused. The shared runner already fingerprints the installed composition
record, so there is no second execution engine or provider-specific runner path.

## Authority and distribution limits

The new deterministic workers use the explicit local-builder-host extension and
a sibling Workbench installation. They do not import another Cog's task logic.
Materialization never runs generated tests. Verification is a separate explicit
step of trusted local code execution, using the candidate's installed Python or the
verifier's declared environment; it is not a sandbox and installs nothing.

A contract digest records the caller's choice, not an authenticated approver.
Candidate receipts reconcile completed local work; partial materialization is a
collision requiring inspection, not an invitation to overwrite. Source/package
fingerprints bind evidence to bytes, not to authenticated execution. Independent
review remains fallible. No commits, publishing, or reference replacement were
performed by this implementation.

## Live qualification

Run `20260922T014600Z-f98016ad` completed all five steps. The reviewer returned
**pass on all 14 criteria**, with no findings and a clean checked envelope.
This is a real provider-backed run, not the deterministic test fixture.

The caller supplied the previously accepted Merge Findings contract and prior
authored source as a revision input with a new package identity. The author
produced a fresh `cog-merge-findings-op-candidate` package snapshot. Its merge
implementation remains byte-identical to the previous candidate; its authored
documentation and test setup were revised. This qualifies the Op's revision
input path, not a claim of an independently invented new merge algorithm.

The first planner output contained `kind: bogus`. The evaluator's packaged
checks reported schema and coverage errors, and the Op stopped before running
any candidate cases. We clarified the evaluator prompt's distinction between
schema-invalid test inputs and schema-valid semantic violations, reactivated its
composition, and resumed the same run. **Author and materialize each ran once.**
The failed plan remains preserved; the successful plan is `envelopes/plan.a2.json`.
Always follow the envelope paths in the Track instead of assuming a filename.

| Live observation | Result |
|---|---|
| Candidate declared tests | 13 pass; known stale reference consumer-fixture warning retained |
| Valid planned cases executed | 15 |
| Criterion-linked evidence records | 52 |
| Shared fixtures run against candidate and unchanged reference | 5/5 normalized payload/problem-code matches |
| Full diagnostic problem lists | 2/5 exact matches; 3 differ in wording, both envelopes retained |
| Final assessment | All 14 criteria pass; no findings |
| Recovery | One resume; paid authoring and packaging retained |
| Reference and prior candidate | Unchanged, verified after completion |

Authoring requested `gpt-6-astra` through the ChatGPT provider; planning/review
requested `sonnet` through the Claude provider. These are recorded selectors and
composition identities, not independently attested weights. Separate role/provider
calls do not prove independent reasoning, and evaluator pass is not release approval.

Source fingerprint:
`0591ba1c2d0740ea6dcc0042f2a62bb32878160f693deb4fac8a1fc9a0637d52`.
Executed package fingerprint:
`bc394984c8b41ca743b45842fe016ade6ef5cb074f39292025d1691d8ca26f65`.

Local evidence: [Track](../runs/20260922T014600Z-f98016ad/track.json),
[completion record](../runs/20260922T014600Z-f98016ad/completion-record.json),
[final review](../runs/20260922T014600Z-f98016ad/envelopes/review.json),
[initial rejected plan](../runs/20260922T014600Z-f98016ad/initial-plan-failure.json),
and [generated candidate](../runs/20260922T014600Z-f98016ad/candidate/cog-merge-findings-op-candidate/COG.md).
These raw files are in ignored runs/ and are not a portable or redacted release
bundle. The executed Op spec is retained beside the Track as `executed-op.yaml`.

## Public-preview evidence scope

This is a historical qualification summary. References to `runs/`, `var/`, or
workspace-relative artifacts identify private local execution records; those
records are not distributed. The public model-free tests are reproducible
checks of mechanics, not a replay or independent verification of the live model run.
