# Suggested review of the recovered 50-claim fixture

Assistant-prepared draft, pending human review. No group is approved, no duplicate
is confirmed, and no hosted review record has been changed. Recommendations use
source claim fields and narratives, not hidden evaluation labels. This review does
not determine coverage, liability, reserves or contractual aggregation.

## Timing questions

| Claim | Source evidence | Suggested treatment |
|---|---|---|
| C002 | Incident starts 12 January 2026 at 09:00 UTC; CL_01's proposed power event is around 10 January. Narrative reports supply failure but gives no event date. | Hold outside CL_01 until continuity or an incorrect date is established. A separate incident is possible, not proven. |
| C011 | Incident time is missing; notification is 11 January at 09:00 UTC, before CL_02's proposed 13 January flood. | Hold outside CL_02 and clarify both timestamps. This additional issue was absent from the challenger objections. |
| C021 | Incident time is missing; notification is 12 January at 09:00 UTC, before CL_03's proposed 16 January windstorm. | Hold outside CL_03 pending chronology correction or evidence of a separate incident. |
| C001 | Incident time is missing; notification is 12 January, after the proposed 10 January power event. | Retain provisionally in pending CL_01; request incident timing. Notification time does not establish incident time. |
| C012 and C022 | Reported incident starts are 15 and 18 January respectively, later than the proposed flood and wind events. | Keep unassigned pending evidence connecting these later losses. Do not add them just to improve benchmark recall. |
| C027 | Reported amount is missing. | Retain pending membership but flag CL_03's sum as incomplete; do not treat the missing amount as zero. |

## Duplicate candidates

Both pairs match business name, incident start/end, coordinates, narrative and
reported amount. Their notification dates differ, so the challenger's statement
that the flood pair has identical timestamps is too broad.

| Candidate mapping | Incident time (UTC) | Notification dates | Amount per notification |
|---|---|---|---:|
| C049 → C004 | 10 January, 07:37:18.904797–09:37:18.904797 | C004: 16 January; C049: 17 January | GBP 47,923 |
| C050 → C017 | 13 January, 10:54:42.976709–12:54:42.976709 | C017: 16 January; C050: 17 January | GBP 27,830 |

These are strong candidates for duplicate confirmation, not confirmed duplicates.
Check that they are repeat notifications of the same loss rather than distinct
components or amended amounts. If confirmed, use the earlier notification as the
canonical record and retain an auditable mapping. The draft's operational
`duplicates` map remains empty; neither amount has been deducted automatically.

## Suggested pending membership

- CL_01: C001, C003, C004, C005, C006, C007, C008, C009, C010, C049.
- CL_02: C013, C014, C015, C016, C017, C018, C019, C020, C050.
- CL_03: C023, C024, C025, C026, C027, C028, C029, C030.

This leaves 27 notifications in proposed groups and 23 unassigned, including the
three timing holds. Common-cause hypotheses remain unproven. Original proposals,
agent explanations and objections are retained; membership edits do not rewrite
the original agent explanations or imply those objections have been resolved.

## Reported-amount scenarios

All sums below were calculated in Python from source amounts. The final column is
a conditional scenario, not an applied decision or approved total.

| Group | Original proposed amount | Suggested pending revision, duplicates retained | Only if both duplicate mappings are confirmed |
|---|---:|---:|---:|
| CL_01 | GBP 325,347 | GBP 279,285 | GBP 231,362 |
| CL_02 | GBP 251,042 | GBP 206,346 | GBP 178,516 |
| CL_03 | GBP 214,319 | GBP 187,278 | GBP 187,278 |

CL_03 has one missing amount in every scenario. These are reported claim amounts,
not estimates of payable loss, reserves or reinsurance recovery.

## Draft artifact and validation

The local artifact `data/live-tests/pending-review-50.json` records the proposed
revision, source-checkpoint hashes, timing evidence, duplicate comparisons and
conditional totals. It passed the application's `review_revision` validation:
known, unique, nonoverlapping membership; at least two underlying claims per group;
valid duplicate structure; all decisions pending. Totals were recomputed using the
same `total` function as the application. Nothing was imported into a local or
cloud review database. No paid call or deployment was needed for this review.

Next decisions are whether to adopt the three timing holds, confirm either
duplicate pair, and obtain the missing incident times and amount before approving
groups. This document records recommendations, not those approvals.

## Local review app

The recovered investigation and suggested pending revision have now been imported
into a separate local database, `data/recovered-review.db`, using
`scripts/import_recovered.py`. The three timing holds are applied only in the
pending review revision; original proposals, explanations and objections remain
attached to the imported analysis. All three decisions are pending and the
confirmed-duplicate map is empty. The public database is unchanged.

The local review session is available at http://127.0.0.1:8502. Open **Review** to
inspect or edit the suggested membership. **Event investigation** retains the
original proposals and evidence. The recovery notice makes clear that this is
not a fresh end-to-end run. Paid calls are disabled for this session.

To recreate the import and start the local app:

```powershell
python -m scripts.import_recovered data/live-tests/20261020T094655Z.json data/live-tests/20261020T095303Z-challenger-diagnostic.json data/live-tests/20261020T101151Z-reporter-diagnostic.json data/live-tests/pending-review-50.json
$env:DATABASE_URL='sqlite:///data/recovered-review.db'
$env:CLAIMCASCADE_ALLOW_PAID_CALLS='false'
python -m streamlit run app.py --server.port=8502 --server.address=127.0.0.1
```

Import verifies checkpoint sources, original evidence, report references and review
membership before writing. It atomically creates the analysis and first pending
revision; repeating an identical import returns the existing run and preserves
later review edits. The import rejects approved groups and confirmed duplicate
maps. Its CLI accepts a local SQLite file path, rather than a remote database URL.

All 45 offline tests passed, including imported-history rendering without inference,
pending membership display, repeat-import preservation and approval refusal. The
actual local database was also opened with Streamlit AppTest: three pending rows,
the recovery notice and no app exceptions. The local health endpoint returned
`ok`. No deployment or paid inference was performed for this step.
