# COSOLVE maintenance log — October 6, 2026

## Scope and continuity

This maintenance pass follows Jake's October 6 authorization for routine,
evidence-backed corrections and reversible fixes, tests, deployment and hosted
verification. It does not approve major redesigns, destructive database changes,
access changes, purchases, outreach or final client submissions.

Required context was read before making changes:

- The existing **COSOLVE Asset Map** local chat, thread
  `019f6bc9-79c4-7f42-a4a8-f8f2ba9e164b`, including its latest October 6 audit.
- [October 6 audit](audit_2026_10_06.md), README,
  [deployment workflow](deployment.md), [data dictionary](data_dictionary.md),
  [import guide](import_guide.md), [September 16 review](review-pass-2026-09-16.md),
  [reference-layer maintenance](reference-layer-maintenance.md), and
  [October 2 MAAP integration](maap-integration-2026-10-02.md).
- Local Codex memory summary and the COSOLVE hosting-hardening rollout summary.
  Current repository instructions take precedence over older seed/release notes.

No applicable AGENTS.md was found in the checked repository/ancestor locations;
`/Users/jakeschwartz/.agents` was absent. The checkout began on `main` at
`9168408a6c75330f6ac494a33983d0c18a6a926c`, matching the remote. The existing
untracked `tmp/` research archive was preserved. No staff-authored data was
overwritten; the guarded catalog enrichment is described below.

## Access and database boundaries

| Surface | Observed result |
| --- | --- |
| GitHub repository | Authenticated push succeeded using existing Git credentials. |
| Hosted map | Existing Chrome session is signed in as `jschwartz`; map, profiles, CSV and reference pages loaded. |
| Render workspace | Existing authenticated session can inspect the web service and database metadata. |
| Hosted database | Render reports an available PostgreSQL 18 database in Oregon. Direct SQL credentials were not retrieved and a direct production SQL session was not established. |
| Local database | Django uses SQLite at the checkout's `db.sqlite3`; 555 stored assets and 1,861 sources. It is not the hosted PostgreSQL database. |
| Mutation tests | Dedicated `sqlite:///:memory:` test databases; no production saved-view or catalog mutations were used for QA. |
| Standalone API navigation | Chrome returned `net::ERR_BLOCKED_BY_CLIENT` for the standalone GeoJSON URL. The map's in-page data loading and CSV export worked. This is not evidence of a server outage. |

The earlier audit commit `9168408` was confirmed **Live** in Render, resolving
the prior chat's outstanding deployment verification. Its deployment is
[dep-db2jv67f3r2c73b8402g](https://dashboard.render.com/web/srv-d9kgihvqj5pc73eie5bg/deploys/dep-db2jv67f3r2c73b8402g).

## Inventory and agreement checks

The initial hosted public CSV contains 542 listed records: 505 `published` and 37
`source-backed`. Local public queries also return 542 records, while local
storage contains 555; configured specialized-institution exclusions account
for the other 13. Local pending-review counts must not be copied to production:
the earlier local audit reports 39, while the hosted public CSV has 37 records
with `source-backed` status.

All 542 hosted rows were checked for basic completeness and precision rules:
no empty description, public source URL set or contact route; no incomplete
coordinate pair; no regional record asserting a map point; no exact duplicate
name or slug; and all exported internal-note fields were blank. Shared campus
locations alone do not establish duplicates.

Hosted precision values are 141 exact, 357 site, 28 locality and 16 regional.
Two site records remain unlocated: NASA Wallops UAS Test and Integration
Facility and Systems Planning & Analysis. No substitute point was invented.
Fifty-eight records lack a confirmed dedicated primary website; supporting
articles and parent-organization evidence remain separate from a homepage.

After normalizing source-list ordering, the ledger contains 44 row differences:
42 matched records with field differences and two hosted slugs with local
counterparts under different slugs. The difference ledger is
[maintenance_hosted_comparison_2026_10_06.json](../data/maintenance_hosted_comparison_2026_10_06.json).
Most differences involve verification dates (32); others include source sets,
website/contact routes, location context, ownership/development evidence,
mission tags and two publication states. Hosted `fort-ap-hill` and
`radford-army-ammunition-plant` have local `-2` slug counterparts, rather than
two duplicate public records. Mare Custos and Trident have publication-state
differences. These are follow-up findings, not approved overwrite instructions.
Review production audit/history and correction baselines before resolving them.
This ledger is the initial, pre-ESCC baseline; the later intentional ESCC change
is recorded separately in the live receipt below. Local SQLite was not resynchronized
from production or changed to imitate the hosted record.

The earlier complete audit covers all 555 stored assets, all 542 public profiles
and API responses, and 1,215 actual local source URLs. This pass independently
checked the hosted export and exercised the hosted workflows below. Neither
pass freshly certifies every capability, operating permission or location.

## MAAP, Blackstone and Dedrone follow-up

The October 2 supplied MAAP material is already integrated and is visible on
the hosted map and [MAAP reference page](https://cosolve-asset-map.onrender.com/references/maap/).
Four flight environments, two distinct vertiport records and seven enriched
existing profiles were confirmed in the published summaries. They should not
be treated as an uncompleted import.

- Three outlines load: Kentland, Eastern Shore and dashed **Central Virginia
  draft 108625**. Import date is not an approval/expiry date. Original reported
  area figures remain attributed; the known polygon-area discrepancy remains
  for operator reconciliation.
- Blackstone airport, MAAP flight environment and Smart Airspace vertiport are
  distinct resources. The reported 4.2 nm / 73 square mile area, 2,500 ft MSL
  limit and R-6602A exclusion are preserved. No actual Blackstone boundary file
  was supplied, so no circular substitute is mapped.
- VTTI 8VA2 remains private/PPR and uses the FAA site reference, avoiding the
  obsolete Shivok association. Procedure submission is not approval. Roanoke
  remains a temporary demonstration site with permanent location/availability
  unresolved. Proprietary procedure waypoints are not published.
- CTRC's supplied infrastructure is attributed and its farm-level point is not
  represented as an exact building or sensor platform. The illustrative sensor
  circle does not establish a guaranteed detection range.
- Dedrone already has a historical Sterling-area record and current Axon
  inquiry routing. The [official October 2, 2024 acquisition](https://www.axon.com/blog/axon-completes-acquisition-of-dedrone)
  was rechecked; it does not establish current occupancy of the former office.

Fresh inspection of the private Virginia Tech shared folder was blocked by
automatic approval review, which rejected the browser navigation because the
delegated/quoted authorization was not accepted as direct user permission for
that private folder. The exact requested retry was also rejected. The action
was stopped and reported to the parent; no alternate access path was used.
Existing checked-in sanitized integration notes remained available. The user
subsequently said to ignore the already-integrated Tombo SharePoint file.
That access dependency is canceled: do not inspect it or request access. The
supplied integration is complete. Current COA instruments, expiry/conditions
and Blackstone geometry remain ordinary operator-evidence follow-ups, separate
from inspecting that folder.

## Public-source developments

These targeted official rechecks do not amount to a new full news sweep:

- [Liquid Robotics' May 7 relocation announcement](https://www.liquid-robotics.com/resource/liquid-robotics-relocation-jessup-maryland/)
  describes headquarters/manufacturing moving to Jessup by year-end 2026. The
  current contact page still lists Herndon. The existing map already discloses
  the transition; completion and remaining Virginia operations are unresolved.
- The [April 17 GO Virginia announcement](https://www.governor.virginia.gov/newsroom/news-releases/2026/april-releases/name-1116537-en.html)
  awards $788,700 for ESCC's FAA Uncrewed Aerial Systems College Initiative.
  The hosted ESCC UMS course record has curriculum evidence but no grant source
  or implementation detail. The guarded enrichment below adds this announcement
  to the existing program; funding is evidence of planned expansion, not proof
  the expanded program is operating.
- The same announcement supports the $3,061,400 Hampton Roads Mobility
  Innovation Center project. Its existing hosted profile already describes
  funded/future facilities and does not claim currently open BVLOS access.
- ESCC's [own news archive](https://es.vccs.edu/category/uncategorized/page/2/)
  corroborates the grant, existing training and planned expansion. It supplies
  additional partnership and equipment context for follow-up, without confirming
  current enrollment or completion of the funded expansion. Direct VCCS course
  extraction failed during the fresh check; that does not establish course closure.
- A fresh [FAA October 5 research-award announcement](https://www.faa.gov/newsroom/faa-funds-drone-research-support-safe-integration)
  lists projects for ANRA Technologies, DroneUp and Aerial Vantage, among others.
  ANRA and DroneUp are already in the catalog; Aerial Vantage is a candidate to
  check for Virginia presence/scope. Match award recipients to the correct
  entity and site before assigning new activity or capabilities. The FAA now
  lists nine designated test sites; current repository descriptions checked in
  this pass did not contain the obsolete seven-site claim.

Blue Ridge Defense Works' missing homepage remains a research follow-up, not
proof of closure. No closure, current facility capacity, newly available land
or operational approval was inferred from a blocked or inaccessible website.

## Hosted functional verification

| Workflow | Observed hosted result |
| --- | --- |
| Initial load and markers | 542 listings; clustered markers; all observed street-map tile images loaded. |
| Search and reset | Blackstone search returned 10 related listings; airport, area and vertiport remained distinct. |
| Counter-UAS filter | 29 results, including domain-only records; unlocated Systems Planning & Analysis says Not mapped. |
| Profiles and related links | Blackstone airport profile loaded with precision/operating context; its connected DOAV profile link opened. Adaptive Aerospace mobile profile loaded with sources and related assets. |
| FAA/MAAP layers | 33 controlled-airspace features, 139 flight constraints, 128 heliport references and the facility-map canvas loaded. MAAP produced three outlines with one draft style. |
| Layer dates | FAA snapshots October 6; MAAP October 2; curated test sites August 12. Unchanged material was not re-dated. |
| Radius analysis | 25-mile radius selected seven records; selected CSV contained the same seven. |
| Copied view | Copied radius link restored seven results, selection geometry and selected layers. |
| Rectangle / polygon | Rectangle selected 135 Hampton Roads records; polygon selected 126. Result totals, selection geometry and export-enabled state agreed. |
| Visible extent | Selected 135 records in the observed extent. |
| Saved views | Existing private View Test restored stored map state. Creation form loaded; no new production view was saved or deleted. |
| Presentation / print | Presentation entered/exited. Print preview generated six pages; report contained exactly 135 rows for 135 selected records. Preview was canceled without printing or saving. |
| Public CSV | Downloaded 542 valid rows. Selection export also completed; browser download-event waiting timed out despite the file being saved successfully. |
| Regional comparison | Hampton Roads 139 versus New River Valley 46; precise mapped counts 134/42 agree with CSV. |
| Mobile | Actual 390 × 844 viewport; Hampton Roads filter returned 139, drawer closed, marker popup/profile route worked, map/profile document width remained 390. Temporary override reset. |

The functional smoke pass used authenticated hosted pages. Saved-view mutations,
permission enforcement and all four appearances have broader coverage in the
earlier isolated audit suite; those results are not represented as new live
mutation tests.

## Prepared, tested and deployed changes

**Prepared:** Regional totals counted public `source-backed` records as well as
`published` records, but the label said “published assets.” The template now says
“listed assets.” The data dictionary now includes `source-backed` lifecycle
status and accurately explains public query rules, exclusions and pending review.
No catalog manifest, source, geometry, schema or access setting changed.

**Tested:** 39 correction/release safeguard tests and 46 view/API tests passed,
all with `DATABASE_URL=sqlite:///:memory:`. Local comparison render returned 200,
showed two “listed assets” labels and no old label. `git diff --check` passed.
Logs remain in `tmp/maintenance-guard-tests-2026-10-06.log` and
`tmp/maintenance-view-tests-2026-10-06.log`. The earlier audit's 317 backend,
30 frontend and 143 browser passes (one intentional skip) are reused supporting
evidence, not tests rerun in this pass.

**Pushed:** Commit `c9d4efdd8c2471de33579fece2181e92a9026d3b` pushed to `origin/main`.

**Deployed and verified:** Render auto-deploy
[dep-db2kdbrncjis738m01hg](https://dashboard.render.com/web/srv-d9kgihvqj5pc73eie5bg/deploys/dep-db2kdbrncjis738m01hg)
completed in 6m27s. Render identifies `c9d4efd` as the last successfully deployed
commit and **Live**. A fresh hosted comparison-page reload showed Hampton Roads
139 and New River Valley 46 with “listed assets” under both totals. This is
hosted verification of the change, in addition to the local test and push.

## ESCC funded-initiative enrichment

After the first deployment/log stage was completed, the parent explicitly
requested preparation or safe application of the routine ESCC grant enrichment.

**Prepared:** [escc_grant_correction_2026_10_06.json](../data/escc_grant_correction_2026_10_06.json)
adds four exactly guarded fields to the existing ESCC UMS course record:
`current_activity`, its official source URL and review date, and searchable
initiative-name aliases. It also adds the official grant announcement as a
source while retaining all three existing course/campus sources. Current
coursework remains distinct from planned expanded training. The record-wide
activity status, campus coordinates, website and taxonomy are unchanged.
New claims require editorial review; the safe correction changes the record
to `source-backed` and clears prior catalog certification. A staff-authored
history/review, changed baseline or hidden/rejected source blocks the update.

The checked-in canonical catalog and generator include the same enrichment so
future catalog rebuilds retain it. `release.sh` applies the new manifest through
the existing commit-locked, baseline-guarded production release workflow.

**Tested:** Final 69 focused and catalog tests passed, including preservation of staff
history, divergent text, hidden sources, existing evidence/location and repeat
runs and catalog regeneration. Linting, Django system checks and diff whitespace
checks passed. A full release rehearsal succeeded against an isolated copy of local
SQLite: exactly one ESCC grant correction applied; the record retained its
campus point and four sources, remained `source-backed`, and had no editorial
review date. Isolated profile and API returned 200 with matching activity and
pending-review state; initiative-name search resolved to this existing record.
The main local SQLite database was not modified. Logs are
`tmp/maintenance-escc-tests-2026-10-06.log` and
`tmp/maintenance-escc-release-2026-10-06.log`.

**Deployed and verified:** Implementation commit
`b63b34f75131504346b43f53a6e7ae42c8910106` is **Live** in Render at
[dep-db2kkb2jnfac73f46d80](https://dashboard.render.com/web/srv-d9kgihvqj5pc73eie5bg/deploys/dep-db2kkb2jnfac73f46d80)
after a 6m13s auto-deploy. The hosted ESCC profile displays the grant wording,
official activity source/date, four sources and pending editorial review.
Initiative-name search returns exactly this existing record; filtered CSV
matches the manifest. The full hosted export still has 542 rows, now 504
`published` and 38 `source-backed`. Normalized before/after comparison confirms
only ESCC changed and all other 541 rows are unchanged. Its campus coordinates,
precision, name, course descriptions, website, activity status and taxonomy
match the initial hosted export. Regional totals still label records as listed
assets (Hampton Roads 139, Eastern Shore 16).

The machine-readable verification receipt is
[maintenance_escc_live_receipt_2026_10_06.json](../data/maintenance_escc_live_receipt_2026_10_06.json).
The final log/receipt update is documentation only and uses Render's
[documented skip-auto-deploy phrase](https://render.com/docs/deploys#skipping-an-auto-deploy).
The tested implementation commit above remains the hosted application version.

## Next maintenance work

1. Inspect production history for the 44 local/hosted differences, then prepare
   narrowly guarded corrections only where authoritative evidence and baseline
   agreement permit. Do not reload SQLite over PostgreSQL.
2. Confirm ESCC's funded initiative rollout and enrollment before changing the
   explicit planned-expansion wording to an operating-capability claim.
3. Resolve MAAP draft/current COA evidence, Blackstone boundary/conditions,
   temporary Roanoke availability and Dedrone's remaining Virginia presence.
4. Continue the 39 local editorial follow-ups, missing homepages and locality/
   regional/unmapped location checks without inventing precision.
5. Follow the established FAA candidate-validation/review cadence. Keep the
   heliport 28-day and curated-site 90-day review intervals distinct.

The parent task maintains the private project tracker/playbook and Tuesday/Friday
09:00 Eastern schedule. This log and the difference ledger feed that task;
this maintenance pass did not write the shared tracker, create a duplicate
schedule or send outreach.
