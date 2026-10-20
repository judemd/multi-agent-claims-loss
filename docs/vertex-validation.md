# Vertex reliability investigation — 20 October 2026

## Latest full-fixture follow-up

**The 50-claim workflow is still not validated end to end.** The public service
remains unchanged and rules-only. The latest offline suite passes **30 tests**.

The approved follow-up stayed below its combined 12-generation-attempt ceiling:

| Request group | Attempts started | Outcome |
|---|---:|---|
| Final-controls run, temperature 0 | 1 | First extraction batch timed out at 90.02 seconds |
| Temperature corrected to 1.0 | 1 | Model returned in 9.05 seconds; narrative evidence validation rejected structured-field quotations |
| Narrative-only inputs and source-constrained quote schema | 3 | First two extraction batches validated in 10.17 and 20.62 seconds; third timed out at 90 seconds |
| Direct SDK streaming diagnostic, missing MIME | 1 | Rejected with HTTP 400 before useful generation; counted toward the ceiling |
| Corrected JSON streaming diagnostic | 1 | Stalled third batch completed in 5.38 seconds; first chunk at 3.88 seconds; ten facts validated |
| ADK SSE recovery using the three validated extraction batches | 1 | Next extraction batch timed out at 90.02 seconds |
| Instrumented ADK diagnostic of that next batch | 1 | Completed in 6.30 seconds; first SDK chunk and ADK content both at 4.73 seconds |
| **Total** | **9** | **No full-run proposals, totals or metrics produced** |

Three attempts remain unused. Even retaining the diagnostic extraction, at least
four successful calls are needed to finish (last extractor plus three later agents).
No further calls were made under this allowance.
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
`20261020T094238Z-adk-diagnostic.json`. The rejected MIME diagnostic has console evidence only.
The recovery source-file hashes remain in its progress record.

The earlier completed 10-claim result was independently rechecked offline:
source evidence, membership and integer-pence financial aggregation checks passed.
There is no new 50-claim accuracy result. The instrumented batch-three diagnostic
reached the SDK at 0.906 seconds, received its first chunk at 4.734 seconds, emitted
ADK content at that same timestamp, and finished both layers at 6.297 seconds.
Its exact narrative evidence passed validation. This request shows no measurable
ADK aggregation delay, but it did not reproduce the intermittent timeout and cannot
establish its cause. A successful isolated retry does not validate a full run.

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
