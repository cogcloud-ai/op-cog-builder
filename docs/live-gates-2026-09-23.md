# Live qualification of the acceptance Gates (0.2.0), 2026-09-23

Two provider-backed runs built `cog-word-tally`, a self-contained pure-code
Cog, from a brief through both acceptance Gates. The second run completed with
`acceptance: accept`; its package is published as
[cog-word-tally](https://github.com/cogcloud-ai/cog-word-tally) and is now the
smoke Op's fixture. The first run is retained as evidence of two component
gaps. Authoring used the ChatGPT provider (`gpt-6-astra` through Codex CLI);
design, planning and review used the Claude provider (`sonnet` through Claude
Code). These are recorded composition identities, not attested weights.

Both acceptance decisions were made in a Claude session on Trent Oliphant's
behalf and say so in `decided_by`. The runner records the string it is given;
authenticating the decider is Workbench's work (cog-workbench#1).

## Run 1: `20260924T040839Z-8db9f1b7`, failed at review

| Step | Outcome |
|---|---|
| design | Contract with the six requested criterion ids, exact tokenization rule, testable examples. Accepted at the contract Gate. |
| author | Complete source; `task_logic.py` correct on inspection. |
| materialize | Packaged; Smith check clean. |
| plan (attempt 1) | Invocation failure: the Claude adapter reported "Vendor result was not a JSON object". The adapter keeps no raw reply, so the cause is unrecoverable. Resumed. |
| plan (attempt 2) | The planner correctly kept schema-invalid inputs out of `test_cases`, then left `invalid_input` uncited; the evaluator's packaged coverage check refused the plan. **Component fix:** cog-build-evaluator's plan prompt now says a schema-violation-only criterion must still be cited on a schema-valid case with the limitation stated. Composition reactivated; resumed. |
| plan (attempt 3) | 10 cases, every criterion cited. |
| verify | All 15 planned observations passed. Declared suite: 12 tests, 1 failure: `test_boundary_tokenization` asserts `total_words` 15 while its own expected counts sum to 13, which the candidate returns. |
| review (twice) | The reviewer found exactly that defect (error finding, classification `revise`) but rated criteria `pass` on the strength of the passed planned cases. The verifier attaches the whole-suite failure to every criterion as a `declared-tests:<criterion>` record with status `failed`, and the evaluator's packaged check refuses a `pass` over a failed record. Two review attempts, same refusal. The run stays `failed` at review. |

What this shows:

- **Resume works across a pending decision and a repaired component.** The
  paid design, authoring and packaging were never repeated across four
  resumes; the second resume's `changed_cogs` records the evaluator's new
  digest.
- **cog-verify-candidate#2 is real.** One suite-level exit code is attached to
  every criterion, so a single wrong assertion in an unrelated test makes every
  criterion carry failed evidence, and a reviewer that reads the actual test
  transcript will not call the criteria failed. Per-criterion declared-test
  evidence is what the review needs.
- **A rejection was not recorded**, because the review never produced a clean
  envelope. The candidate Gate was not reached in run 1.

## Run 2: `20260924T042851Z-356db650`, accepted

The request carried run 1's seven source files as `materials` and the
reviewer's finding, verbatim, in the brief. That is the revision route the Op
supports today: no conditional steps, every candidate from a contract accepted
in the same run.

| Step | Outcome |
|---|---|
| design | Re-designed contract: identical input and output schemas, same six criterion ids, reworded prose, boundary example total corrected to 13. Different digest from run 1 (`9e07330f…`); accepted at the contract Gate. |
| author | Source reproduced from materials; the only change is the one-line test fix. |
| plan, verify | 10 cases; all observations passed; declared suite 12 tests, exit 0. |
| review | All six criteria `pass`, no findings, clean envelope. |
| candidate Gate | Accepted, bound to contract `9e07330f…`, source `8dde7e44…`, package `5d68047c…`, evidence and assessment digests. Before accepting, the candidate was diffed against run 1, its tests were run in a full environment, and `smith check --tests` passed. |

`outputs.acceptance: accept`; the Track carries both decisions, both resumes,
and every envelope.

## Limits

- A re-run re-designs. Two runs from the same brief produced semantically
  equivalent contracts with different digests. Revision under the *same*
  accepted contract, with the evaluator's findings routed automatically, is
  op-cog-builder#2.
- The Claude adapter should retain the raw vendor reply on a parse failure
  (cog-claude#1 territory); without it, a transport failure is a blind retry.
- The reviewer/verifier disagreement above is a contract gap between two
  components, not a model quality claim either way.
- Raw run directories are ignored local state and are not distributed; the
  published package and this record are the portable evidence.
