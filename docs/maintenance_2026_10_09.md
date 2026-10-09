# COSOLVE maintenance log — October 9, 2026

## Outcome and execution state

The local inventory/source audit and application tests are finished. The full
maintenance review remains open. Hosted health and sign-in boundaries passed.
**Authenticated hosted verification remains
blocked by this runtime's missing browser/session tools. No production record,
reference layer, access setting or application release was changed.**

| Deliverable | Prepared | Locally tested | Deployed/live verified |
| --- | --- | --- | --- |
| Dated inventory, source, location and layer evidence | Yes | Read-only checks passed | Evidence files only; no production import |
| Browser referrer test using the actual test origin | Yes | Full desktop/mobile suite passed | Test code only |
| Corrected smoke checklist for hosted authentication and isolated writes | Yes | Matches anonymous hosted checks and current settings | Documentation only |
| Three guarded FAA research-award enrichments | Yes | Guard tests and copied-database rehearsal passed | **No**; not wired into generation or release |
| Six VABA follow-up comparisons | Yes | Official content and 13 existing local records compared | Evidence/proposals only; no catalog mutation |
| Authenticated hosted feature/inventory comparison | Required | Local counterpart passed | **Blocked**, not certified |

Repository delivery uses `[skip render]`. A Git push of these evidence/test files
does not establish a new hosted deployment. The last deployment confirmed in the
October 6 log is `b63b34f`,
[dep-db2kkb2jnfac73f46d80](https://dashboard.render.com/web/srv-d9kgihvqj5pc73eie5bg/deploys/dep-db2kkb2jnfac73f46d80);
its current state was not rechecked in Render on October 9.

## Required context and preservation

Read the known **COSOLVE Asset Map** conversation's latest user/assistant messages
from its existing local rollout, thread `019f6bc9-79c4-7f42-a4a8-f8f2ba9e164b`.
The runtime exposes no supported local history/thread tool; the known transcript
was streamed read-only, without printing tool payloads or credentials. Personal
context search returned **“Personal context is unavailable for this conversation.”**

Also read the [October 6 maintenance log](maintenance_2026_10_06.md),
[October 6 audit](audit_2026_10_06.md), README,
[deployment guide](deployment.md), [data dictionary](data_dictionary.md),
[import guide](import_guide.md), [smoke checklist](smoke_test.md),
[reference-layer maintenance](reference-layer-maintenance.md),
[October 2 MAAP integration](maap-integration-2026-10-02.md), and relevant local
Codex memory/hosting-hardening summary. Current repository workflows supersede
older memory notes about seeding and hosting plans. No applicable AGENTS.md was
found in the checked repository/ancestor paths; `.agents` was absent.

The checkout began on `main` at `288d6922c9d958ef7ccf136d7439bf0c6cd24d79`,
matching GitHub. Only the existing untracked `tmp/` archive was present. All
earlier archives were retained. The main SQLite database remains unchanged;
its modification time is October 6. New copied databases remain untracked and
restricted to their owner. No confidential stakeholder material was imported.
The canceled supplied-folder access dependency was not reopened.

## Access and database boundaries

| Surface | October 9 result |
| --- | --- |
| GitHub | Existing credentials read the repository and successfully pushed [a0a689a](https://github.com/jschwartz1313/COSOLVE-Asset-Map/commit/a0a689a530786733cca1acb33478b846d6e6dcb0). The remote branch was independently confirmed at that commit. |
| Hosted health | `/health/` returned HTTP 200 with `status: ok`. |
| Hosted protection | Anonymous map, API, directory, comparison and MAAP-reference requests redirected to the sign-in page. Final HTTP 200 is the login page, not the protected application. |
| Hosted authenticated session | **Unavailable to this runtime.** No browser/computer/session tools are exposed. October 6's signed-in session is historical evidence, not a new access check. |
| Render project/database | Authenticated dashboard inspection and direct SQL access were not available. October 6 documented paid Render PostgreSQL 18; those metadata were not freshly verified. |
| Local source database | SQLite `db.sqlite3`: 555 stored assets, 1,861 sources, 542 public listings. This is not Render PostgreSQL. |
| Mutation QA | In-memory test databases and new local SQLite copies only. No hosted imports, saved-view writes or staff-account changes. |

The [anonymous hosted receipt](../data/hosted_access_check_2026_10_09.json)
records actual timestamps and final URLs without session tokens or response bodies.
The blocker was reported during the review; independent work continued. To finish,
resume in an environment exposing the supported browser/session tools, use the
existing authorized session, inspect Render and export the current public inventory.
No password reset, cookie extraction or login-bypass workaround was attempted.

### Reconnection follow-up, 14:42 UTC

After the parent reported a freshly connected, authorized Mac, the executor was
confirmed as Darwin in the same repository. Its 340 callable tools still expose
no browser/CUA/JavaScript REPL, local-history API, Render connector or reconnect
action. Executor skill discovery returns no skills. The newly cached Chrome and
Browser packages, version `26.1007.21159`, have empty skill directories; Chrome's
plugin metadata refers to the absent `node_repl` runtime.

Packaged read-only diagnostics confirm Chrome is installed/running and the
native-host manifest is valid. The fresh diagnostic now selects a profile without
the ChatGPT extension, while another profile has it enabled. Before reconnection,
the diagnostic selected the enabled profile. Neither result checks actual
browser-client transport or a signed-in site. No profile was switched. There is
also no Render CLI or database connection in the shell/project dotenv.

The exact local diagnostic receipt is
`tmp/maintenance-2026-10-09/browser-route-check.json` (untracked). The parent/platform
must expose the supported browser runtime and confirm the intended authorized
profile. Packaged Chrome troubleshooting documents extension checks and a Browser
plugin UI reinstall if restored transport still fails; it prohibits shell browser
substitutes and native-host repair. No failed transport call or need to reinstall
is inferred from missing tool registration alone.

### Intended Chrome account follow-up, 15:10 UTC

After the user clarified the intended account, read-only non-secret Chrome profile
metadata maps it to **Default**, displayed as **Person 1**. The fresh automatic
extension diagnostic now selects that matching profile and passes: installed,
registered and enabled. A diagnostic-only check explicitly targeting Default also
passes. Chrome is running and the native-host manifest remains valid. The 14:42
profile-selection mismatch is historical; it is no longer the current blocker.

The remaining blocker is unchanged tool registration: 340 callable tools expose
no supported browser/CUA/JavaScript REPL or reconnect action, and executor skill
discovery remains empty. Actual extension transport, signed-in map access and
Render PostgreSQL/staff-history access cannot be tested without that runtime.
The smallest next step is for the parent/platform to expose the Browser/Chrome
runtime in this execution context, or resume in a context with those tools. The
diagnostics do not indicate a need to switch profiles, install an extension or
create a login; profile selection alone cannot supply missing runtime tools.

The private local receipt is
`tmp/maintenance-2026-10-09/chrome-account-route-2026-10-09T151012Z.json` (untracked,
owner-only). No cookies, tokens or passwords were inspected or retained; no
profile, security, access or extension settings changed. Staged FAA corrections
remain unapplied pending current production and staff-history comparison.

## Inventory and display agreement

The [stored-record review](../data/asset_review_pass_2026_10_09.json) covers all
555 local records and all 542 public profiles/APIs. There were no asset/source
model-validation failures, missing public evidence sets, incomplete profiles,
broken profile responses, public-name mismatches or duplicate candidates.
Forty-eight shared coordinate groups were retained; shared campuses are not
automatically duplicates. Basic public-field exclusion checks and the existing
privacy/publication tests passed.

The same open local findings remain: 39 pending editorial reviews, 28 locality
points, two unlocated site records and 58 records lacking a confirmed dedicated
website. The other 13 stored records are configured specialized-institution
exclusions. Source-backed public listings are counted separately from reviewed
listings; no verification dates were renewed by a link or model check.

The [copied-database agreement check](../data/local_display_agreement_2026_10_09.json)
compares all 542 CSV/GeoJSON records with models, public source sets and geometry.
All 414 related-entity entries point to public records, all 12 regional API totals
match their model counts, and the tested pages return HTTP 200. There are 524
non-null map geometries: 16 regional listings and two unlocated sites have none.

Publication totals differ by database and must not be substituted for one another:

| Dataset | Published | Source-backed pending | Listed |
| --- | ---: | ---: | ---: |
| Unchanged local main SQLite, October 9 | 503 | 39 | 542 |
| Isolated copy after existing release workflow | 502 | 40 | 542 |
| Last verified hosted inventory, October 6 | 504 | 38 | 542 |

The copy applies the previously deployed ESCC enrichment that the older local
database lacked. October 6's
[hosted/local difference ledger](../data/maintenance_hosted_comparison_2026_10_06.json)
and [ESCC live receipt](../data/maintenance_escc_live_receipt_2026_10_06.json)
remain historical baselines. The date/source/status differences and two legacy
slug counterparts require fresh hosted history review; no SQLite-to-PostgreSQL
overwrite was attempted.

## Sources and developments

Fresh bounded public-URL checks covered 1,238 unique URLs from all 555 stored
records: 1,048 reachable, 163 access-blocked/rate-limited, 24 network/TLS errors,
one HTTP 404, and two homepage redirects needing review. The detailed local
archive is `tmp/maintenance-2026-10-09/local-source-audit.json`.

The reproducible [canonical source ledger](../data/source_audit_2026_10_09.json)
covers 542 checked-in records and 1,209 URLs: 1,028 reachable, 157 blocked,
23 network/TLS errors and one 404. All checks carry October 9 timestamps. Its
[exact-URL comparison](../data/source_audit_delta_2026_10_09.json) identifies
35 classification changes since October 6, no removed URL, and the added ESCC
announcement. The guarded source-import dry run matched all 1,209 URLs and would
update 1,817 source observations; it was not applied to production or local main.

These are availability/text-screen checks, not full editorial recertification.
PDF text was not extracted and JavaScript-dependent content has limits. Blocked
pages and transient transport failures are inconclusive. Blue Ridge Defense
Works' already-flagged homepage still returns 404; no closure was inferred.

The [FAA October 5 announcement](https://www.faa.gov/newsroom/faa-funds-drone-research-support-safe-integration)
supports award context for three existing records: ANRA airspace/integration
research, DroneUp identity/authorization research and Devorto cargo-drone research.
[Prepared corrections](../data/proposed_faa_baa_corrections_2026_10_09.json)
retain company evidence, locations, contacts, capabilities and operating-status
fields. They add attributed award context and return the changed claims to pending
editorial review. No per-company funding amount, assigned test site, completed
deployment or operating permission is inferred.

The [isolated proposal receipt](../data/proposal_rehearsal_2026_10_09.json)
confirms three source additions, 552 unrelated asset rows and 1,851 unrelated
source rows unchanged, valid profiles/APIs, constant inventory size and an
idempotent repeat. The proposal is intentionally absent from `release.sh` and
default catalog generation. Current hosted baselines/history and authenticated
verification must be checked before integrating and releasing it.

Targeted official/news review also checked ownership, office and opening claims:

- [Liquid Robotics contact](https://www.liquid-robotics.com/contact-us/) still
  publishes Herndon; its [May relocation announcement](https://www.liquid-robotics.com/resource/liquid-robotics-relocation-jessup-maryland/)
  describes a Jessup move by year-end. Completion remains unconfirmed.
- [Robin Radar's official opening announcement](https://www.robinradar.com/news-events/robin-opens-new-larger-u.s.-operations-center-as-global-c-uas-demand-accelerates)
  agrees with the existing Sterling office record. No radar operating area is inferred.
- [Dedrone legal information](https://www.dedrone.com/legal/overview) lists the
  historical Sterling address, but it does not resolve current occupancy under
  Axon. The record's historical/locality qualification stays in place.
- [SPA locations](https://spa.com/about-us/locations/) confirms its existing
  Alexandria office address. A fresh Census query returned no match; no point was invented.
- [September 25 Navy-center reporting](https://defensescoop.com/2026/09/25/navy-creates-robotic-autonomous-systems-warfighting-development-center/)
  identifies RASWDC at JEB Little Creek, established September 24 with phased
  capability development. No matching record/acronym was found in the inventory.
  The Navy announcement and NAVADMIN PDF returned 403; retain this as a research
  candidate pending authoritative full-content review, without a guessed facility pin.

The [follow-up ledger](../data/location_followup_review_2026_10_09.json) retains
all 30 generalized/unmapped dispositions, Blackstone geometry and COA questions,
MAAP area discrepancies, NASA Wallops' unresolved UAS facility pin, and the
specific evidence checks above. Two stored excluded institutions have source-route
follow-up: Riverside's official site now brands itself College of Health Sciences,
and VUIM's admissions URL redirects home. Any identity correction must preserve
the intended specialized-institution exclusion.

### VABA follow-up supplied by the parent

The parent subsequently supplied six topics. The
[comparison ledger](../data/vaba_followup_comparison_2026_10_09.json) records official
content, 13 matched local records and their existing sources, proposed enrichments,
precision limits and the outstanding hosted comparison. The initial context gap
is resolved for these topics; the VABA-specific newsletter/deliverable remains
unavailable. No new asset or catalog/database change was made.

| Topic and public evidence | Local comparison / proposed disposition |
| --- | --- |
| [Textron demonstration](https://www.textronsystems.com/our-company/news-events/articles/press-release/textron-systems-aerosonde-uas-completes-first-uas) | Already sourced on Smart Airspace and VTTI. Consider attributed activity enrichment on the existing Textron center; preserve separate airport, pad and flight-area records. |
| [Current FAA roster](https://www.faa.gov/uas/programs_partnerships/test_sites/locations) | Lists nine sites; the Textron release's seven-site count is stale. No matching stale count was found in checked map text. |
| [Winchester AIP award](https://www.govirginiaregion8.org/news/winchester-awarded-airport-improvement-program-grant/) | Add awarded/planned taxiway context to the existing airport; construction is not established as complete. |
| [Liberty DC-8 Overlook](https://www.liberty.edu/news/2026/09/21/liberty-university-receives-grant-from-boeing-to-support-dc-8-overlook-project/) | Existing university, aeronautics school and airport match. Consider a planned-project note; no pavilion point, opening date or grant amount is established. |
| [CSIIP](https://vsgc.odu.edu/csiip/) | Existing statewide workforce program. Consider its subsidy ceiling in activity information; retain unmapped regional representation. |
| [InternshipsVA](https://www.vedp.org/internshipsva) | Consider linking this workforce resource from existing VEDP information; eligibility/training require current checks. |
| VABA-specific study/toolkit lead | Publication is unverified. VEDP's general Employer Toolkit does not establish publication of the distinct VABA deliverable. |

These are review proposals, not a guarded VABA mutation manifest. Fresh hosted
record/source/history comparison remains required before integration, isolated
mutation tests, release and live verification. Private correspondence and inferred
assignments were excluded; no outreach or application was made.

The six-topic/13-record JSON consistency check passed: all identities/slugs match,
source links are public HTTPS URLs, and the catalog hash and main SQLite timestamp
remain unchanged. Existing application/proposal test results below remain valid;
this follow-up changed only documentation and evidence files.

## Reference layers and functional QA

The [reference-file review](../data/reference_review_2026_10_09.json) checks all
ten shipped geographic files; every geometry is valid and non-empty. FAA counts
remain 7,002 facility-map cells, 33 controlled-airspace features, 139 constraints
and 128 heliports, dated October 6. MAAP's three outlines retain October 2;
the curated test sites retain August 12. None is due under the current review
intervals, and no snapshot was re-dated. Geometry validity does not certify COA
approval, public access, capacity or flight permission.

| Check | Result | Local archive |
| --- | --- | --- |
| Full backend suite | 323 passed | `backend.log` |
| Frontend suite | 30 passed | `frontend.log` |
| Full desktop/mobile browser suite after correction | 143 passed, one expected desktop-only drawer skip | `browser-final.log` |
| Prepared correction/staff/source guards | 17 passed, including five new proposal tests | `proposal-guard-tests.log` |
| Existing release workflow on copied SQLite | Completed; existing administrator retained | `release-copy-rehearsal.log` |
| Source import | Dry run only, all canonical URLs matched | `source-import-dry-run.log` |
| Django checks/migration drift | No issues; no model changes | Command output |
| New-test lint and whitespace | Passed | Ruff and `git diff --check` |

Archives above are under `tmp/maintenance-2026-10-09/`. Browser coverage includes
loading, search, filters, markers, public profiles, reference controls, drawing,
analysis, selection exports, view-state restoration, themes and responsive layouts.
Saved-view ownership/mutations, staff CSV/import/publication guards, related-asset
visibility and regional behavior are covered by isolated backend tests and the
agreement checks. Browser provider requests use fixtures; this does not certify
the live provider's availability or licensing.

The initial browser run passed 141 tests but failed two referrer assertions solely
because the test expected port 8002 while the isolated server used 8019. The test
now compares the actual site origin, still excluding paths/search parameters.
Affected tests and then the full suite passed. An initial empty-database release
rehearsal stopped correctly because it lacked an administrator fixture; the copied
database rehearsal passed without changing accounts. The first focused proposal
test run exposed an incomplete published-record fixture, which was corrected;
all 17 tests then passed. No such failure was observed in the hosted application.

## Remaining hosted work

Authenticated hosted loading/search/filter/marker/profile/layer/drawing/export,
related assets, saved-view access, regional comparisons and mobile inspection
remain unverified on October 9. Render deployment metadata, current hosted
inventory and staff history also remain unverified. These are explicit blocked
checks, not inferred passes from localhost, an anonymous login response or GitHub.

Once supported browser/session tooling is restored, check the existing signed-in
site and Render project, compare fresh hosted public CSV/API data with the guarded
proposal, preserve staff conflicts, and only then integrate/release eligible
changes. Record the actual deployment and repeat the affected live checks. Keep
major redesigns, destructive database/access changes, commitments, outreach and
client submissions with the parent for approval. Tracker/playbook/schedule
maintenance remains with the parent; this pass supplies the dated map evidence.
