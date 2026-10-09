# FAA research-award release candidate — October 9, 2026

## Outcome and boundaries

Prepared the three-record FAA reconciliation as a release candidate. The existing
production guard was insufficient for a URL retired by an edit or deleted without
an attributed actor. Those failures were reproduced in isolation and the guard
was strengthened before integration. **No production mutation or deployment was
performed by this task.**

The active manifest is
[faa_baa_corrections_2026_10_09.json](../data/faa_baa_corrections_2026_10_09.json).
The original proposed manifest remains as historical preparation evidence.
The generated catalog changes only ANRA Technologies, DroneUp and Devorto, plus
its generation date. No operating-status, capability, location, contact, access
or reference-layer changes are included. VABA enrichments remain separate proposals.

The parent-supplied fresh browser review observed the existing authorized COSOLVE
staff and Render sessions, deployment `b63b34f`, PostgreSQL 18, and 542 public
listings: 504 Published / 38 Source-backed. Its downloaded CSV hash and all three
FAA `before` groups were independently rechecked locally. The proposed FAA source
is absent from each candidate's public sources. These are authenticated hosted
application observations, not a direct production SQL inspection.

The browser task's uncommitted `docs/browser_review_2026_10_09.md`,
`data/maintenance_hosted_comparison_2026_10_09.json` and updates to
`docs/maintenance_2026_10_09.md` remain untouched. Their before/after hashes are
checked separately; they are not bundled into the release candidate commit.

## Guard decision

The correction command queries the production database when the release runs.
It locks the asset row and checks unique identity, catalog provenance, public
status/visibility, current field matching, reviewed-by/assignment/due-date,
attributed asset history and authored review comments. It also checks unrestricted
current source rows, including hidden, stale, rejected and duplicate sources.

The previous source-history predicate checked only attributed deletion events.
That allowed an absent URL to be recreated after a source URL edit, or after a
deletion with no retained actor attribution. New isolated tests failed for both
cases. There is no assertion that either case occurred on production.

The strengthened shared predicate preserves any deletion history for the URL,
regardless of actor, and any missing current URL with prior retained history.
Both corrections and enrichment use it. A source conflict preserves the entire
correction group and records a conflict marker; enrichment respects that marker.
Enrichment also locks a unique matching identity and, for the FAA manifest bound
to the release command, requires exact catalog provenance. A correction skipped
for either condition cannot be bypassed by the following enrichment step.
General profile enrichment retains its prior behavior. A focused reproduction
failed before these checks were aligned and passes afterward. No guard was
removed and no accepted baseline was broadened.

This makes a conditional guarded release safe without claiming that the browser
established absence of hidden/deleted sources. Those predicates are enforced
against actual retained production rows/history before mutation. A database query
failure stops the release; a conflicting record is held rather than forced.
Production SQL/history results and application of the corrections are still
unverified until that release and subsequent inspection occur.

The FAA correction is placed immediately before enrichment in `release.sh`.
Historical editorial-review manifests cannot republish its newly pending claims.
The existing `release_database` command retains PostgreSQL advisory locking,
completion tracking by Render commit and administrator-preservation behavior.
No migration, hosting configuration, service plan or access-setting change is
included. The October 9 source-audit import is not added to this release.

## Tests and rehearsal

| Check | Result |
| --- | --- |
| New retirement/deletion reproductions against old guard | Three tests failed with four assertions; preserved as evidence of the gap |
| Focused guard/review/release tests after hardening | 46 passed |
| Integrated FAA/catalog/review/release tests | 78 passed |
| Final FAA/correction/enrichment tests | 32 passed, including the identity/provenance skip cases |
| Full backend suite after integration | 333 passed in the final rerun; two historical manifest expectations include the October 9 follow-up |
| Ruff, Django system checks, migration drift and shell syntax | Passed; no migrations |
| Full release on a new private SQLite copy | Three FAA corrections applied; 555 stored / 542 public retained |
| Non-target preservation | All 552 unrelated assets and all 1,862 pre-existing source rows unchanged |
| Local profiles/API and editorial state | Three profiles/APIs HTTP 200 and agree; claims remain Source-backed with review dates cleared |
| Repeat release | Completed-version no-op; asset/source rows and history counts unchanged |
| Full release with three source conflicts | Hidden, staff-edited URL and unattributed-deletion cases all held; no public award source added and no enrichment bypass |

Copies and detailed logs are private/untracked under
`tmp/maintenance-2026-10-09/faa-release-20261009T154439Z/`.
They are initialized from local SQLite with an isolated staff-history fixture;
they are not a production database restore. Main `db.sqlite3` is unchanged.
The earlier browser suite is not repeated because this candidate changes no UI
code. A rehearsal harness initially assumed a top-level API activity field;
it was corrected to the existing nested `activity` structure and the check passed.

## Exact browser/Render handoff

Use the fresh task with supported `mcp__cua_repl.js` and the existing authorized
Person 1 Chrome sessions. The final parent handoff supplies the full candidate
commit SHA after GitHub delivery; a push alone is not deployment evidence.

1. Download a fresh authenticated public CSV before deployment. Record its hash,
   counts and timestamp; retain the prior export. Recheck the three candidate
   `before` values and current displayed staff-review context. If these changed,
   report the difference and hold reconciliation. Do not infer source-history
   absence from the public CSV or bounded audit.
2. Open the existing Render service
   [cosolve-asset-map](https://dashboard.render.com/web/srv-d9kgihvqj5pc73eie5bg).
   Confirm the linked repository/branch and that the latest GitHub commit is the
   reviewed candidate SHA supplied by the parent handoff. If it differs, stop for
   review of the new head.
3. From **Deploys**, choose **Manual Deploy → Deploy latest commit**. Use the
   existing service and database. This is the documented manual-deploy option;
   do not change automatic-deploy settings, credentials, plans or resources.
   [Render deployment documentation](https://render.com/docs/deploys).
4. Record deployment ID, actual full SHA, timestamps and the final live status.
   Inspect logs for successful build, `Database release completed`, and the FAA
   correction summary: the final correction line immediately before enrichment.
   Expected if all three runtime guards pass: **Applied 3 catalog corrections;
   preserved 0 conflicts.** A conflict is a held record, not permission to force
   the command or overwrite a staff decision. Do not run `release.sh` directly,
   `--force`, pruning or recovery commands.
5. Reopen the authenticated map and all three profiles. Confirm prior company
   activity plus the attributed award, FAA evidence link, October 9 activity date,
   pending/Source-backed review badge and original operating status, location,
   contacts and capabilities. Expected public source counts are ANRA 6, DroneUp 5,
   Devorto 3; prior evidence must remain.
6. Download the post-deployment public CSV. Compare it with the fresh pre-deploy
   baseline, normalizing taxonomy and aligned source tuples as before. Verify
   unchanged slug set, 542 public listings and all 539 unrelated public rows;
   check the known legacy slugs and staff-edited records in particular. If all
   three apply and no other staff changes intervene, expect **501 Published /
   41 Source-backed**. Do not substitute local SQLite counts for these results.
7. Verify search and review-status filters for the three updated records, related
   links, unchanged layer dates/caveats and an affected mobile profile. Record the
   final screenshots/exports and actual deployment evidence. The prior standalone
   API navigation block must not be bypassed; retain that limitation if it persists.

Complete means the deployed SHA, release result and affected live records agree.
Until that evidence arrives, this remains **prepared and locally tested, not
deployed or live verified**. Tracker/playbook/schedule changes remain with the parent.
