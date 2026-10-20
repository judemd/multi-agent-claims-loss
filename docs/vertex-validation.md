# Vertex reliability investigation — 20 October 2026

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
The remaining live check is a full 50-notification run with the final configuration,
followed by broader held-out evaluation before enabling any public paid access.

References: [Google 429 guidance](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/error-code-429),
[thinking configuration](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking).
