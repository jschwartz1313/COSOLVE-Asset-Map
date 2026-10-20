# COSOLVE maintenance — October 20, 2026

## Preparation checkpoint

This review starts from `806ac4f4e3e62b466da3189967b9067574a5d1f8`.
The October 13 Tuesday candidate was already deployed; it was not deployed again.
The October 16 review-footer and external-link changes are preserved. This
checkpoint describes a new guarded candidate. Its delivery states are recorded
separately in the candidate receipt and subsequent local delivery receipt.

Authenticated Render inspection confirmed deployment
`dep-db92kfmk1f9s73f21deg`, exact source `806ac4f`, **Deploy succeeded | Live**.
It started October 16 at 09:44:30 EDT and became Live at 09:52:21 EDT
(13:52:21 UTC). Database release completed at 09:52:06 EDT, Gunicorn listened on
10000 and repeated `/health/` requests returned 200. Existing source observations
were skipped (1,618 / 1,816 / 1,848); duplicate removal was zero and the existing
administrator was retained. The earlier failed deployment
`dep-db923n6q1p3s738s40p0` ended at an internal health-check deadline after release
completion. A successful deployment of the same earlier source followed it,
then the currently Live `806ac4f`. The failure notification is historical.

No deployment, source-audit import, production fixture, access change, private
tracker write or external message was performed in this review.

## Preservation and fresh hosted evidence

Jake's existing Chrome session initially provided authenticated Render, map and
staff access. The map loaded **543 listed: 501 Published / 42 Source-backed**.
A fresh public CSV contains 543 rows and all 55 columns. Compared with the
October 13 pre-command 542-row public CSV, every original identity and exported
field is equivalent after aligned source-tuple and taxonomy-order normalization.
Only two raw source-URL orderings differ. RASWDC is the sole new identity.
This public comparison does not cover private records, reviewer workflow or
complete history. The 18 unmapped records remain (16 regional, two site).

Staff review loaded with its existing choices; its aggregate dashboard has 55
pending, no duplicate pairs and two missing-coordinate records. RASWDC search
returns one directory record. Its profile retains developing status,
headquarters/site precision, the installation-reference caveat, three Unreviewed
sources and the Little Creek link. The review footer is intentionally absent.
No new incoming-link navigation pass is claimed after browser control failed.

Main SQLite is an older **555 stored / 542 public** snapshot, with 503 Published
and 39 public Source-backed rows. Its SHA-256 remains
`1560f31bc94c6ed377d09a662beef73151ebf889a8ea5c9cb20f28be15712d4d`.
It is separate from hosted PostgreSQL. All original uncommitted October 9/13
evidence is preserved. The smoke checklist retains its original bytes and has
appended October 20 findings; it is excluded from the candidate commit.

## Candidate corrections

1. Add existing `hosts` and `manufactures-for` relationship choices and readable
   labels. Three hosts edges and one manufactures-for edge previously failed
   model validation. Preserve their codes, direction, IDs and history. Migration
   0016 updates model choices only. Catalog validation now rejects unknown or
   blank relationship codes.
2. Use the existing guarded corrections command for Orange County Sheriff's
   Office Drone Team's contact URL. Both main SQLite and the fresh hosted export
   retain the old Louisa newsflash URL; the checked-in catalog already contains
   the correct Orange sheriff route. Apply only with unique exact identity,
   catalog provenance, exact old URL and existing staff/history protections.
   Preserve sources, verification, priority, taxonomy, location and relationships.
3. Replace Drone Park's confirmed 404 reference-layer URL with the official
   [facilities page](https://ictas.vt.edu/Facilities.html) and
   [scheduling/orientation page](https://drones.ictas.vt.edu/dronepark.html).
   Only four source properties change. Geometry, IDs, count, specifications,
   caveats and the actual August 12 geometry snapshot date remain unchanged.
4. Correct the read-only source-audit classifier's missed CivicPlus
   `/Identity/Account/Login` redirect. Match exact terminal login/signin/sign-in
   segments without case sensitivity, preserving explicit-login-source behavior
   and ordinary content paths. No runtime monitor, importer or editorial choice
   changes. Frozen evidence remains unchanged; one observation is reclassified.
5. Keep UAS facility and ordinary asset popups below the toolbar and allow their
   contents to scroll within the available map height, using the existing MAAP
   popup behavior. Settled 390px reproductions and baseline comparisons establish
   the overlap on all three facilities and the RASWDC asset popup; no toolbar or
   page redesign is involved. Final browser evidence is recorded with the
   candidate checks.

The RASWDC regression test now agrees with the October 16 footer decision while
asserting pending API status and no review/verification dates. README and data
documentation describe the two active appearances and current listing semantics.

## Inventory, sources and references

All 543 hosted public names match the catalog. The 162 records with direct
catalog/export differences are preserved choices, not a mandate to overwrite.
Read-only local checks cover 555 assets, 1,861 sources, 207 relationships and all
542 public profiles/API/GeoJSON records, with no asset/source validation errors,
display mismatches or high-signal duplicate candidates. The four legacy
relationship choice errors are addressed above.

Availability checks attempted 1,242 unique URLs: raw results were 1,038 reachable,
172 blocked/rate-limited, 28 network/TLS-inconclusive, two 404s and two homepage
redirects. HTTP 200 is not editorial verification: CivicPlus sign-in, an NCES
redirect shell affecting 130 catalog records and an old Laurel Ridge generic
course shell need content-aware follow-up. The classifier correction changes
the returned CivicPlus observation only; the raw ledger is retained. SAIC's
`/products` 404 has an official `/cuas` replacement candidate, not yet applied.
Blue Ridge's 404 has no confirmed equivalent replacement; no closure is inferred.
GMU RobotiXX remains TLS-inconclusive. No new audit was imported into PostgreSQL.

All ten shipped geographic/reference layers validate: 7,465 nonempty features.
Four freshly fetched FAA candidates have identical semantic geometry/properties
to October 13, with upstream facility-map ID reassignment. No ID/date-only
refresh is shipped. MAAP checked-in KML geometry hashes and recomputation match;
external original packages and current operating permission were not re-attested.
The published snapshot dates and non-authorization caveats remain accurate.

Sixteen development items across fourteen primary channels produced no confirmed
new Virginia site, closure or coordinate correction. ANRA VISTA is optional
existing-record context, not aircraft detection or counter-UAS capability.
Other partnerships were not converted into invented Virginia operating sites.

## Tests and coverage limits

Final combined checks pass **374 backend and 30 frontend tests**, Ruff, Django
system checks, migration-drift checks and whitespace checks. These supersede
the earlier 368-test result before the six classifier regressions were added.

The final isolated browser suite passed **145 checks with one expected desktop
skip** across desktop/mobile after both popup corrections. Its eight new
regressions exercise all three facilities' unobscured headings/close controls,
seven scrollable content rows, clickable source links and map bounds, plus
RASWDC's ordinary popup close/reopen, scrolling and actual profile navigation.
The initial unchanged-UI
suite had passed 137 with the same skip. Eight additional normal-login SavedView
create/reopen/delete checks passed in an explicit SQLite clone. Twelve candidate
checks passed for the four legacy relationship edges, guarded Orange correction
and Drone Park source popups. Settled mobile before/after captures were inspected.
These are isolated results, not authenticated production certification. Native
preview/actual hosted PDF and external basemap availability are outside them.

The relationship migration forward/reverse rehearsal preserves all 207 existing
edges and 4,550 relationship-history rows. Orange's clone correction changes
only its contact URL/update timestamp and adds the expected system history/
comment; repeating is a no-op. Other assets, sources and relationships remain.

| Area | Fresh hosted October 20 result / remaining scope |
| --- | --- |
| Authentication, inventory, health | Existing session works; 543 public; public CSV complete; anonymous health 200. |
| RASWDC search/profile | One directory result; pending-source labels, site caveats and outgoing link observed. Incoming-link navigation remains open. |
| Staff/internal export | Dashboard observed. Working CSV returns Chrome `ERR_BLOCKED_BY_CLIENT`; no file downloaded. Private 55-field/history preservation remains open. |
| API/GeoJSON | Direct browser navigation returns `ERR_BLOCKED_BY_CLIENT`. Map JS loads data, but full authenticated standalone payloads remain open. |
| Search/filter/markers/relationships | Broad isolated checks pass; complete fresh hosted combinations and navigation remain open. |
| Layers/drawing/analysis/views/regions | Broad isolated checks pass; full fresh hosted checks remain open. |
| Print, PDF and no-JavaScript | Prior isolated evidence remains historical; hosted PDF/native preview and explicitly disabled-JS session remain open. |
| Mobile/appearances | Isolated Current/Dark checks pass; fresh hosted checks remain open. Settled 390px facility/asset-popup overlaps are addressed in the isolated candidate and require hosted confirmation. |

## Browser recovery and resume

Supported CUA transport closed during the RASWDC/base-link step. A bound read and
supported runtime reset also failed. A fresh delegated environment exposed no
callable CUA surface. The Mac remained connected and file/process/HTTP tools
worked. No native-window, cookie/profile, credential, CDP, private-window or
blocked-route bypass was used. No installation or permission change was made.

[Official browser troubleshooting](https://learn.chatgpt.com/docs/chrome-extension#troubleshooting)
says starting a new ChatGPT Work or Codex chat can clear chat-specific connection
state. The smallest documented next attempt is a **fresh local chat using
`@Chrome` on this connected Mac**. This is untested here and not a guaranteed
diagnosis or fix. The parent can request that handoff; no new chat was created
automatically.

After supported access returns, inspect Render history before any action. Verify
the exact pushed candidate SHA and whether it already has a deployment; inspect
an existing deployment instead of repeating it. Obtain fresh public/working
baselines and inspect current staff choices. If the candidate is absent, deploy
latest commit once, watch guarded corrections/migration/release completion and
health, then verify exact Live SHA and expected contact/relationship/source-link
behavior. Complete the open hosted coverage above and compare all exported
fields without reconciling PostgreSQL from local SQLite. Keep tested, pushed,
deployed and fully live-verified states separate.

Private receipts, logs, CSVs and browser captures are owner-only under
`tmp/maintenance-2026-10-20/`, including `inventory/inventory-summary.json`,
`browser-regressions/receipt.json`, `browser-regressions/candidate-targeted/receipt.json`,
`browser-regressions/popup-fix/receipt.json`,
`source-login-fix/receipt.json`, `reference-link-fix/receipt.json` and
`tests/relationship-types/relationship-types-receipt.json`.
