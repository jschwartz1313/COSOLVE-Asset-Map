# COSOLVE maintenance — October 13, 2026

## Outcome and state

The Tuesday candidate is **prepared and locally tested**. It adds one pending Navy
command, preserves staff relationship decisions, refreshes validated FAA reference
snapshots and imports newer public-source availability observations. Delivery uses
`[skip render]`; **no Tuesday deployment or production write was performed**.
Friday's `53a6df32271f955bbf321e2b456bc16f8b66e2ca` release was not repeated.

Current authenticated hosted exports remain **555 stored / 542 public**,
**501 Published / 41 Source-backed public**. The public CSV is byte-for-byte
identical to Friday's post-deployment CSV. Staff access worked as `jschwartz`.
The bounded recent audit's newest entries are Friday's system-attributed FAA
corrections. This is not a complete production-history inspection.

Render's session expired and requires sign-in. Later, supported browser transport
closed during drawing QA; one read-only recovery check also failed. File access
recovered. The remaining hosted checks and deployment require restored supported
browser control plus Render sign-in. No browser installation, profile switch,
credential extraction, access change or shell browser substitute was attempted.

## Context and preserved work

Read the original **COSOLVE Asset Map** review and **Review COSOLVE asset map**
maintenance task through supported thread history. Personal context search was
unavailable. Read the October 6/9 audit, maintenance, browser and deployment
evidence, smoke checklist, deployment guide and reference maintenance procedure.
No applicable AGENTS.md or checkout `.agents` skills were found.

The checkout started at `53a6df3`. Friday's two modified documents, five untracked
evidence files and existing `tmp/` archives were preserved. Main SQLite remains
unchanged at SHA-256
`1560f31bc94c6ed377d09a662beef73151ebf889a8ea5c9cb20f28be15712d4d`.
The canceled Tombo dependency was not reopened. No private tracker was edited,
external communication sent or final client submission made.

## Little Creek lead and candidate

The [official Navy establishment release](https://www.dvidshub.net/news/575564/us-navy-establishes-robotic-and-autonomous-systems-warfighting-development-center)
confirms RASWDC's September 24 establishment at JEB Little Creek-Fort Story under
Fleet Forces. Its role covers operational integration, testing, doctrine and
training across air, surface and undersea systems. Full operational capability
is still developing; DRPM RAS is the separate acquisition portfolio.

Before preparation, the catalog/local inventory and authenticated staff search
were checked for the full command name, RASWDC, JEB/Little Creek, Fort Story and
Fleet Forces. No command identity was found in the staff results. The existing
base, TALSA East and NSWC Carderock records are retained. Norfolk/Navy, NATO and
broad DoD records were not treated as command duplicates.

[The one-record expansion](../data/asset_expansion_2026_10_13.json) creates a
**Source-backed, editorial-review-pending organization** with one `located-at`
relationship to the existing base. It uses the existing installation reference
point, labels it as headquarters/site precision, and explicitly says it is not
a command building, test-bed footprint or operational boundary. It uses existing
taxonomy vocabulary and does not infer commercial intake, fees, availability,
flight permissions, a range, an operating BVLOS corridor or a benchmark score.
The public contact is Fleet Forces media information, not commercial test intake.

The Navy release was readable. The Fleet Forces media and installation contact
pages returned access-blocked responses; no contact phone/email was invented.
All three new sources remain unreviewed.

The release tests reproduced two existing relationship-preservation failures:
`--add-missing` republished hidden relationships and restored deleted ones.
It now preserves existing relationships and holds absent edges with retained
history. The new command also has explicit identity terms: if a staff name,
display name or alias matches, both addition and new relationship are held.
No staff record is renamed or merged by this command-specific guard.

## Inventory and sources

- All 555 initial local assets and their sources passed model validation; all
  542 local public profiles/APIs passed. No high-signal duplicate candidate was
  found. Shared installation/campus points remain legitimate co-location.
- The unchanged main SQLite has 503 Published / 39 Source-backed public records;
  these counts must not replace the hosted 501 / 41 result.
- Existing gaps remain: 28 locality points, two unlocated sites and 58 records
  without confirmed dedicated websites. No point or closure was invented.
- The source ledger covers the union of local stored and hosted public URLs plus
  the prepared command: **1,259 unique URLs**. Results: 1,047 reachable, 166
  blocked/rate-limited, 30 network/TLS errors, 11 missing-page responses and five
  homepage redirects requiring review. These are availability checks, not fresh
  editorial certification of every claim; PDFs and JavaScript have limits.
- Current hosted URLs account for three missing-page responses: Blue Ridge
  Defense Works' homepage, Orange County Drone Team's retained Louisa newsflash
  route and SAIC's products route. Replacement discovery was inconclusive, so
  they remain explicit follow-ups. Older local retained routes explain the other
  missing-page responses. No speculative source replacement was applied.
- Prior VABA enrichment proposals and location/ownership/COA follow-ups remain
  separate from this candidate. The fresh Navy release resolves the previously
  blocked RASWDC source lead; unrelated uncertain claims were not promoted.

The newer source audit uses the existing guarded importer: only newer
`last_checked_at`, HTTP status and check-error observations are changed on public
sources. Verification, manual link decisions, source content and notes remain
protected. Hidden sources and equal/newer observations are retained.

## Reference layers

Downloaded and validated same-day FAA candidates: 7,002 facility-map cells,
33 surface-airspace features, 139 flight constraints and 128 heliports. Source
identity, identifiers, geometry and popup fields pass validation. Geometry and
property multisets are identical to October 6; FAA reassigned 5,477 facility-map
IDs. Only the actual retrieval date and those upstream IDs changed.

The four shipped candidates now record October 13 locally. These dates are
**not yet hosted**. Curated test facilities retain August 12 and MAAP outlines
October 2, including the draft Central Virginia qualification. All ten shipped
geographic layers have valid, nonempty geometry. Snapshots are not flight
authorization, live NOTAMs/TFRs or site-access permission.

## Tests and isolated release

Final code passed **338 backend tests**, **30 frontend tests**, lint, Django
system checks and migration checks. The suite covers isolated imports,
review/publication/archive, saved-view mutations and preservation guards.
The new command/relationship regressions include staff alias, hidden link,
deleted link and existing internal staff-record cases. Historical catalog
completeness checks now recognize the new pending expansion.

The full release was rehearsed on an owner-only SQLite copy after replaying
Friday's baseline code. It added one asset, three sources and one relationship;
all **555 existing assets, 207 relationships and the existing administrator**
were preserved. All protected fields on **1,865 existing sources** are preserved;
1,848 source records received availability metadata only. Same-version release
repeat skipped updates. The final guarded release also completed.

The candidate copy has 556 stored / 543 public records, 499 Published / 44
Source-backed because its earlier local editorial baseline differs from hosted
PostgreSQL. All 543 profiles/APIs, CSV/GeoJSON/model agreement, 416 related entries
and all 12 regional totals pass. Public private-field exclusion passes. **Expected
hosted result**, if no staff changes intervene and identity guard permits the
addition, is 556 stored / 543 public, **501 Published / 42 Source-backed**.

## Live browser QA completed and outstanding

| Check | Tuesday evidence |
| --- | --- |
| Authenticated loading and inventory | Map woke successfully; 542 public / 555 working export. |
| Staff access and current changes | `jschwartz`; recent bounded audit observed; public CSV unchanged since Friday. |
| Combined filters/export | Hampton Roads + test environments + maritime surface returned 12; CSV also has 12. |
| Marker/card/profile | Card selected NSWC Carderock marker; popup location/precision and View asset link matched; profile loaded. |
| Back/forward and reset | Filter state restored across history; clear returned 542. |
| Radius analysis/export | 25-mile map-center selection: seven cards, summary and downloaded CSV agree. |
| Standalone API | Chrome blocked navigation with `ERR_BLOCKED_BY_CLIENT`; no bypass. |
| Rectangle/polygon, remaining analysis | Rectangle mode started; transport closed before drawing completed. No pass claimed. |
| Related links, layers, saved views, comparisons, mobile | Local/data tests passed; Tuesday live checks remain to be completed after browser restoration. Friday checks remain historical evidence. |
| Render/deployment/PostgreSQL metadata | Sign-in required; no fresh Render inspection or Tuesday release. Direct production SQL not used. |

Fresh public, private working and combined-filter CSV files are respectively
`cosolve-assets (16).csv`, `(17).csv` and `(18).csv` in Downloads. The private
working file is owner-only and was not committed. The seven-row radius export is
`cosolve-selected-assets (3).csv`. Public CSV SHA-256 remains
`3db1ec88cb3178eafe4efc4a5d0fb972cdfb6a0f6806d131552a208cf80888a4`.

## Resume and release

1. Restore supported browser control in a connected Mac task and sign in to
   Render in the retained tab. Keep Chrome Person 1. No setup change is indicated.
2. Read this log and the final handoff SHA. Independently verify GitHub main is
   the reviewed `[skip render]` candidate, inspect the existing service/database
   and export fresh public/working CSV baselines. Recheck the command identity
   terms in all staff statuses immediately before release; hold conflicts.
3. Finish rectangle/polygon, related assets, all reference overlays/caveats,
   saved-view restoration, regional comparison and mobile live QA. Mutation
   tests remain isolated. Do not bypass the standalone API block.
4. Manually deploy **the Tuesday candidate once**, using the existing service
   and database. Do not repeat Friday's deployment, force commands, prune data,
   change access or overwrite staff decisions.
5. Record exact deployed SHA/ID, release summary and final Live status. Expect
   one new pending command, three unreviewed sources and one base relationship
   if its runtime identity guard passes; source metadata imports may skip newer
   observations. Verify new profile/alias search, preserved base/related records,
   October 13 FAA overlays with existing caveats, and pre/post CSV preservation
   of all 542 original public rows. Check working/private history bounds without
   treating local SQLite as production. Expected public counts are 543 / 501 / 42.
6. Keep prepared, tested, pushed, deployed and live-verified states distinct.
   Report findings to the parent for tracker reconciliation; do not edit it here.

Evidence: [inventory](../data/asset_review_pass_2026_10_13.json),
[hosted comparison](../data/maintenance_hosted_comparison_2026_10_13.json),
[source ledger](../data/source_audit_2026_10_13.json),
[source follow-ups](../data/source_followup_2026_10_13.json),
[reference review](../data/reference_review_2026_10_13.json),
[release rehearsal](../data/maintenance_release_rehearsal_2026_10_13.json),
[display agreement](../data/local_display_agreement_2026_10_13.json).
Private copies and detailed execution logs remain under `tmp/maintenance-2026-10-13`.
