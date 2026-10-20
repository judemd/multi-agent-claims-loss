# Vertex reliability investigation — 20 October 2026

## Latest full-fixture follow-up

**The 50-claim workflow is still not validated end to end.** The public service
remains unchanged and rules-only. The latest offline suite passes **44 tests**.

The initial follow-up allowed 12 attempts. The subsequently approved four-call
recovery raised the combined ceiling to 13; a separately approved reporter call
raised it to 14. One separately approved revised-reporter call raised it to 15.
All 15 attempts have now started:

| Request group | Attempts started | Outcome |
|---|---:|---|
| Final-controls run, temperature 0 | 1 | First extraction batch timed out at 90.02 seconds |
| Temperature corrected to 1.0 | 1 | Model returned in 9.05 seconds; narrative evidence validation rejected structured-field quotations |
| Narrative-only inputs and source-constrained quote schema | 3 | First two extraction batches validated in 10.17 and 20.62 seconds; third timed out at 90 seconds |
| Direct SDK streaming diagnostic, missing MIME | 1 | Rejected with HTTP 400 before useful generation; counted toward the ceiling |
| Corrected JSON streaming diagnostic | 1 | Stalled third batch completed in 5.38 seconds; first chunk at 3.88 seconds; ten facts validated |
| ADK SSE recovery using the three validated extraction batches | 1 | Next extraction batch timed out at 90.02 seconds |
| Instrumented ADK diagnostic of that next batch | 1 | Completed in 6.30 seconds; first SDK chunk and ADK content both at 4.73 seconds |
| Recovery from four validated extraction batches, retries disabled | 3 | Last extractor and investigator validated; challenger timed out at 90.03 seconds; reporter not called |
| Isolated, instrumented challenger using the unchanged validated input | 1 | Completed and validated in 8.92 seconds; first SDK chunk and ADK content both at 7.48 seconds |
| Isolated reporter from linked checkpoints | 1 | Returned in 21.53 seconds; schema passed but manual review found inaccurate membership statements |
| Revised reporter with source quotations and structured references | 1 | Passed validation in 27.70 seconds; 30 exact quotations and no membership-range prose |
| **Total** | **15** | **All stages have validated outputs via recovery; no fresh reliable full run demonstrated** |

The approved allowance is exhausted. After the recovery stopped on its first
failure, the final call was used for the separately agreed isolated challenger
diagnostic. Recovery currently supports extraction outputs only; no automatic
replay of investigator or challenger outputs was added. Public model access
remains disabled.
Timeout outcomes and their final billable token usage are unknown.

Corrections and safeguards implemented:

- Removed the forced temperature 0 setting. Google's
  [Gemini 3 guidance](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/start/get-started-with-gemini-3?hl=en)
  recommends 1.0 and warns that lower temperatures can cause looping or degraded
  performance. This was a configuration error, not proof of the timeout's cause.
- Extractors now see only claim IDs and narratives, with IDs and whole-source
  quotes constrained by schema. The investigator retains the original structured
  fields and must record discrepancies; validation was not relaxed.
- Enabled ADK SSE mode. The direct SDK diagnostic used a shorter equivalent task
  instruction, so its success does not prove that streaming alone resolves latency.
- Added explicit operator-only extraction recovery with source/batch validation,
  dataset/generation-policy checks and source-file/output hashes. No automatic
  replay of uncertain requests or reuse of prior proposals/approvals was added.
- Added a single-batch diagnostic that records SDK entry, first chunk, stream end
  and ADK content/final events without printing response text or credentials.
  It uses the production extraction instruction, schema and generation settings,
  with one SDK call, no retry and a 90-second timeout. Offline checks cover both
  successful event ordering and preservation of timing evidence after timeout.
- Verified ADK's real Gemini stream aggregator offline with a stubbed SDK transport.
  All eight stages finish, and temperature, thinking level, JSON output and disabled
  continuation reach the assembled request correctly. This does not establish the
  cause of the live timeouts.

Local evidence (ignored by Git): `20261020T090931Z.json`,
`20261020T091248Z.json`, `20261020T091537Z.json`,
`20261020T092158Z-stream-diagnostic.json`, and `20261020T092442Z.json`
under `data/live-tests`. The instrumented diagnostic is
`20261020T094238Z-adk-diagnostic.json`. The latest recovery is
`20261020T094655Z.json`. The rejected MIME diagnostic has console evidence only.
The isolated challenger diagnostic is `20261020T095303Z-challenger-diagnostic.json`.
The recovery source-file hashes remain in its progress record.

The earlier completed 10-claim result was independently rechecked offline:
source evidence, membership and integer-pence financial aggregation checks passed.
There is no new 50-claim accuracy result. The instrumented batch-three diagnostic
reached the SDK at 0.906 seconds, received its first chunk at 4.734 seconds, emitted
ADK content at that same timestamp, and finished both layers at 6.297 seconds.
Its exact narrative evidence passed validation. This request shows no measurable
ADK aggregation delay, but it did not reproduce the intermittent timeout and cannot
establish its cause. A successful isolated retry does not validate a full run.

The latest recovery reused four source-validated extraction batches. The fifth
completed in 11.73 seconds (first ADK content at 9.20 seconds), and the investigator
completed in 9.91 seconds (first content at 3.67 seconds). Python validated source
evidence and membership before starting the challenger. The challenger emitted no
ADK content before its 90.03-second timeout. No provider status code was returned,
and final token usage for that uncertain request is unknown. The reporter was not
called. Investigator output is retained locally as an incomplete checkpoint, not
an approved or completed investigation. No accuracy comparison is reported from
this partial workflow.

The subsequent isolated challenger diagnostic reconstructed the same input from
all five extraction checkpoints and the investigator proposal, revalidating exact
source evidence and membership before any network access. It retained the production
instruction, output schema, model, temperature, thinking level and streaming mode.
The input components measured 21,236 bytes of claims, 9,562 of facts, 638 of bulletins,
12,594 of candidate edges and 4,416 of proposals (plus JSON keys/separators). These
are byte counts, not token counts or evidence that input size caused a timeout.
The diagnostic records source and payload SHA-256 hashes locally.

This single call reached the SDK at 0.969 seconds, received its first chunk and
emitted first ADK content at 7.484 seconds, ended the SDK stream at 8.906 seconds
and emitted the ADK final at 8.922 seconds. Schema and objection membership checks
passed. There is no evidence of substantial ADK aggregation delay on this attempt.
The intermittent timeout did not reproduce; network/provider scheduling and other
causes remain unresolved. The reporter remains untested on the 50-claim result,
and these separate checkpoints do not constitute a completed full workflow.

Offline diagnostic tests cover source reconstruction, objection membership denial,
SDK/ADK event ordering and timeout evidence, with no paid calls. Operators can use
`python -m scripts.diagnose_challenger SOURCE --inspect-only` to validate and measure
the input without inference; omitting that flag performs one gated paid request.

## Reporter diagnostic: structural pass, factual review failed

`scripts/diagnose_reporter.py` reconstructs the reporter's production input from
the validated investigation and isolated challenger checkpoints. Before inference
it revalidates extraction sources, proposal membership, objections, dataset/model
identity, generation settings, and the challenger's exact source and input hashes.
Reported claim totals are recomputed in Python; hidden duplicate labels are not
used to alter operational totals. The report must explain each proposal exactly
once, and objections remain unresolved.

Offline inspection passed for three proposals and three objections. The input is
4,416 bytes of proposals, 900 bytes of challenge and 404 bytes of totals, plus JSON
keys/separators. The script's `--inspect-only` mode performs no model calls. Tests
reject mismatched checkpoint links, missing/duplicate/unknown report explanations
and verify that amounts and objections are preserved.

The user then approved one additional reporter call, with no retries and a
90-second timeout. It completed in 21.532 seconds: SDK entry at 0.954 seconds,
first SDK chunk and ADK content both at 17.547 seconds, and stream end/final ADK
output both at 21.532 seconds. Three explanations passed the schema and exact
cluster-ID coverage checks. Provider usage was 2,309 prompt, 726 answer and 708
thinking tokens (3,743 total), not an invoiced cost. Local evidence is
`data/live-tests/20261020T095755Z-reporter-diagnostic.json`.

**Manual factual review failed.** The CL_02 explanation says "C011 to C020",
which includes C012 even though it is unassigned. CL_03 says "C021 to C030",
which similarly includes unassigned C022. These statements do not change the
structured membership or Python totals, but the narrative is inaccurate and
must not be treated as approved. Existing Report validation checks schema and
cluster-ID coverage, not semantic fidelity of free text. No generated output was
silently edited or accepted as a completed investigation.

Every stage has now returned structurally valid output for this fixture through
recovery and isolated diagnostics, but a fresh reliable full workflow has not
been demonstrated, and the reporter's content needs correction. Next work should
ground report statements in structured member references and validate those
references, with deterministic member/amount rendering. This can be developed
offline without extending the exhausted paid-call allowance. No deployment or
public paid access was changed.

## Offline report grounding correction

Live pipeline version 5 replaces free-text observations with claim IDs and exact
narrative quotations. Hypotheses and missing-information statements now have
explicit, nonempty claim-ID lists, validated as unique members of their cluster.
Claim identifiers are forbidden in those prose fields; this prevents the observed
ID-range shorthand from bypassing explicit membership references. The validator
recognizes supplied IDs and unknown IDs in the synthetic C-number format; it is
not a general semantic truth checker for arbitrary prose or spelled-out ranges.

Production reporting and the reporter diagnostic use the same instruction and
validator. The UI renders structured references separately from hypothesis text;
membership and reported amounts remain rendered from Python data. Historical
reports that fail the current checks show a warning and their prose is withheld
from the investigation display. Stored history is not rewritten.

Tests cover the actual offline ADK workflow with the revised schema, fabricated
and wrong-member observations, unknown/nonmember/duplicate references, ASCII and
Unicode ID ranges in prose, legacy schema rejection, and both current and legacy
UI paths. All 44 offline tests passed. No additional inference or deployment was
performed during implementation. Hypotheses can still be wrong despite valid
references and require human review. No claim of reliable full-workflow completion
is justified by these offline checks.

## Revised reporter live validation

The user separately approved one call with the revised reporter schema and
instruction, no retries, and a 90-second timeout. The linked investigation and
challenger checkpoints were revalidated before inference. This call completed
in 27.704 seconds. SDK entry was at 1.000 seconds; the first SDK chunk arrived at
20.110 seconds and first ADK content at 20.125 seconds. Both stream end and final
ADK output were at 27.704 seconds. Local evidence:
`data/live-tests/20261020T101151Z-reporter-diagnostic.json`.

All three explanations passed the current shared report validator. All 30 source
observations were exact quotations belonging to their clusters. Hypothesis and
missing-information references were unique valid members, and no prose claim-ID
ranges appeared. Manual inspection found no recurrence of the prior inclusion of
unassigned C012 or C022. Common causes and suspected duplicates remain hypotheses;
the three challenger objections remain unresolved, with no human approval implied.

Provider usage was 2,638 prompt tokens, 1,504 answer tokens and 1,464 thinking
tokens (5,606 total), not an invoiced cost. Exactly one SDK generation call was
observed, with retries and automatic continuation disabled. The allowance is now
exhausted. No source code changed for this live check, so the previously passing
44-test offline suite remains the current test result.

All stages now have validated outputs on this 50-claim synthetic fixture across
checkpoint recovery and separate diagnostics, including the revised reporter.
That does not demonstrate a reliable fresh end-to-end run or real-world accuracy.
Public paid calls remain disabled and the deployed service was not changed.

```powershell
python -m scripts.diagnose_reporter data/live-tests/20261020T094655Z.json data/live-tests/20261020T095303Z-challenger-diagnostic.json --inspect-only
```

## Recovered result assembled and evaluated offline

`scripts/assemble_recovered.py` validates the linked investigation, challenger and
revised reporter checkpoints, recalculates financial totals, and writes review
JSON and Markdown. Report schema, exact source quotations, cluster membership,
generation settings and checkpoint hashes are rechecked before labels are used
for evaluation. The output is marked `recovered_complete`, with origin explicitly
recorded as linked checkpoints and `reviewer_approved=false`. It is not imported
into the hosted database or treated as a fresh completed live run.

Local artifacts: `data/live-tests/recovered-50.json` and `recovered-50.md`.
Three proposed clusters contain 30 notifications, with 20 unassigned and three
unresolved challenger objections. The fixture has 135 canonical true pairs:

| Metric | Rules baseline | Recovered agents |
|---|---:|---:|
| Pair precision | 0.977 | 1.000 |
| Pair recall | 0.622 | 0.867 |
| Pair F1 | 0.760 | 0.929 |
| Candidate recall | 0.822 | 0.822 |
| Incorrect merged pairs | 2 | 0 |
| Missed true pairs | 51 | 18 |

The 18 missed agent pairs involve unassigned C012 and C022. Candidate edges are
leads rather than a hard membership gate; agents see all claims, so their pair
recall can exceed candidate recall. Both comparisons use identical inputs and no
human edits. This fixture was reused during debugging and is a development result,
not a blind benchmark, proof of real-world accuracy or measured time savings.

Operational amounts preserve suspected duplicates until a reviewer confirms them:

| Cluster | Reported amount | Hidden canonical reference (evaluation only) | Missing amounts |
|---|---:|---:|---:|
| CL_01 | GBP 325,347 | GBP 277,424 | 0 |
| CL_02 | GBP 251,042 | GBP 223,212 | 0 |
| CL_03 | GBP 214,319 | GBP 214,319 | 1 |

These differences reflect unconfirmed duplicates, not arithmetic errors. Hidden
labels do not alter the operational totals or approve the proposed groups. The
review artifact lists explicit membership, source quotations, hypotheses, missing
information and unresolved objections. All 44 offline tests pass, including linked
assembly, mismatched-source denial and invalid reporter-reference denial. No paid
calls or deployment changes were made for assembly. Next is human review of the
recovered artifact; fresh-run reliability and broader blind evaluation remain open.

```powershell
python -m scripts.assemble_recovered data/live-tests/20261020T094655Z.json data/live-tests/20261020T095303Z-challenger-diagnostic.json data/live-tests/20261020T101151Z-reporter-diagnostic.json
```

## Source review of the recovered proposals

An assistant-prepared [review draft](synthetic-review.md) recommends holding C002,
C011 and C021 outside the working groups pending timing clarification, keeping
C012/C022 unassigned, and retaining two duplicate pairs as unconfirmed candidates.
C011's notification predates the proposed flood event, an additional discrepancy
not called out by the challenger. The duplicate pairs' incident times match but
notification dates differ; the challenger's identical-timestamps wording is
corrected in the review. C027's missing amount remains explicit.

The pending revision has 27 grouped and 23 unassigned notifications. It passed
application review validation and has no approvals or confirmed duplicates.
Original and conditional totals are recorded separately. The artifact is local
`data/live-tests/pending-review-50.json`; original analysis history is unchanged.
No inference or deployment changes were made. Adoption of the suggested holds
and confirmation of duplicates remain human decisions.

The remaining sections retain the earlier observations for context.

## Changes

- Global endpoint retained. The original error was PayGo-style `429 RESOURCE_EXHAUSTED`.
  Google documents traffic smoothing and truncated backoff as mitigations, rather
  than evidence that purchasing capacity or raising a fixed quota is necessary.
- Read-only audit lookup returned no additional matching error detail. The published
  quota catalogue exposed no model-specific global entry for Gemini 3.5 Flash;
  its [model documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash)
  lists fixed quota as unsupported. The exact cause of the original 429 remains
  unproven; no quotas, billing limits or provisioned capacity were changed.
- Minimum request-start interval: 30 seconds. One retry per stage only for structured
  provider 429/503 codes. Backoff is capped with jitter; numeric Retry-After is
  respected. Whole-run maximum: 12 attempts, 90 seconds per attempt, 600 seconds total.
- SDK retries explicitly set to one attempt. Automatic generation continuation is
  disabled as well, preventing hidden follow-up generation calls outside the counter.
- Timeouts, cancellation, malformed outputs, authentication and evidence errors are
  not retried. No automatic replay or resume of incomplete paid runs.
- `LOW` thinking is the new default for the configured Gemini 3.5 model. It reduces
  reasoning depth; it is not a hard token or latency guarantee.
- Live snapshots include policy and pipeline version. Operator tests save request
  events, usage and schema-valid structured outputs locally, including on failure.

## Live observations

First paced test: the 50-claim development fixture, seed 42, at most 12 attempts.
The first two extraction batches completed in 30.20 and 36.64 seconds. The third
hit the 90-second timeout. It was not retried. No 429 occurred during these three
logical attempts. Partial evidence: ignored local file
`data/live-tests/20261020T084927Z.json`.

Then a separate 10-claim held-out-template sample, seed 100, with `LOW` thinking
and at most six attempts. This used different requests rather than replaying the
timed-out batch. All four agents completed on the first attempt, producing two
clusters, five unassigned notifications, 21 extracted facts and one challenger
objection. All exact excerpt and membership checks passed. The objection remains
unresolved for human review.

| Metric | Rules baseline | Agent-assisted |
|---|---:|---:|
| Pairwise precision | 1.000 | 1.000 |
| Pairwise recall | 0.429 | 0.571 |
| Pairwise F1 | 0.600 | 0.727 |
| Candidate-pair recall | 0.714 | 0.714 |
| Incorrect pairs merged | 0 | 0 |
| True pairs missed | 4 | 3 |

The comparison uses identical inputs and no human edits. Ten notifications and seven
true pairs are only a smoke test, not a reliable performance estimate. No claim of
real-world improvement or time savings is justified.

Recorded provider token usage for the completed sample:

- Prompt tokens: 11,177.
- Generated answer tokens: 1,908.
- Thinking tokens: 1,238.
- Total: 14,323.

These are provider usage counts, not an invoiced cost. The timed-out request's final
usage is unknown. Successful-run local evidence:
`data/live-tests/20261020T085349Z.json` (not committed).

Across the two tests, seven logical SDK attempts were started. Transport retries
were disabled during these tests. The automatic-continuation guard was added after
the live sample completed and verified offline; physical HTTP generation requests
were not independently audited. No further paid test was run after that guard.

## Offline verification

23 tests passed, including the actual ADK graph with an injected 429, exact source
evidence, exhausted request budgets, Retry-After, pacing, cancellation, authentication
errors and public-mode paid-call denial. A separate SDK-level test returns a
CONTINUATION response and confirms only one generation request occurs with
automatic continuation disabled (`automatic_continuation=False`).

The public Cloud Run image has not been updated or enabled for paid analysis.
The remaining live check is a successful full 50-notification run, followed by
broader held-out evaluation before enabling any public paid access.

References: [Google 429 guidance](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/error-code-429),
[thinking configuration](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking).
