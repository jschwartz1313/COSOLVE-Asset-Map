# Source-backed catalog review — October 20, 2026

## Candidate and delivery state

Prepared on top of `77ec7b3f3b0de5ea7319af85b12db3d37406a115`, preserving the
October 20 basemap changes. This candidate adds **12 Source-backed listings**,
**seven relationships**, and **two guarded profile corrections**. It does not
promote the additions to Published or mark their sources editorially verified.
The primary catalog grows from 543 to 555 records; all 540 unrelated catalog
records and all 208 existing catalog relationships are unchanged. One catalog-only
AAC address cleanup matches the already-correct saved hosted address.

Prepared, tested, pushed, deployed and live-verified are separate states. The
delivery receipt is maintained locally in
`data/asset_review_delivery_status_2026_10_20.json`. A deployment of the preceding
basemap commit is not delivery evidence for this candidate.

## Reviewed additions

The dated [expansion](../data/asset_expansion_2026_10_20.json) retains exact public
source URLs, maturity, access and location qualifications for each listing.

| Listing | Scope and location treatment |
| --- | --- |
| Newport News Park Radio Control Club Flying Field | Existing member-operated field, distinct from MIC readiness. Official club GPS; site reference and published field rules. |
| U.S. Army Futures and Autonomous Systems Command | Official October 2026 FCC redesignation at Fort Eustis. Organization, no command-building or range pin. |
| Rocket Lab Virginia Launch Operations | LC2 Electron/HASTE activity and opened LC3 complex; Neutron remains developmental. One regional organization record, no guessed launch-pad point. |
| Jefferson Lab | Scientific computing, accelerator engineering and technical workforce support. Campus address retained; point held because Census ZIP differs from the official address. |
| Aerospace Academy of the Eastern Shore | ODU/school-division/ESCC multi-site education program with a published UAS credential pathway; no single-campus pin. |
| Hampton Roads Workforce Council | Regional maritime skilled-trades and employer support. Qualified Census office-address reference. |
| VTCRC Newport News and Secure Energy Future Center | One coordinated Newport News office/center listing, distinct from Blacksburg HQ. Building 700 address; conflicting suites omitted and unmatched coordinates held. |
| 757 Collab | Startup and defense commercialization support, including documented USV enabling technologies. Assembly/Norfolk context; no unverified street or suite point. |
| Innovate Hampton Roads | Regional entrepreneurship resources and appointment-only office. Own published address and qualified Census building reference. |
| Maxbyte Industry 4.0 Centre of Excellence at TCC | Hosted manufacturing/automation training and pilot programs. TCC Virginia Beach campus address reference; Building H is not individually positioned by the geocoder. |
| Pancopia LLC | Aerospace-origin water-recovery R&D and current agricultural products. Federal contact address and qualified building reference; present occupancy is not independently confirmed. |
| Liti Holographics, Inc. | Published holographic optics, XR and technical education capabilities. Own Hampton address and qualified Census building reference. |

The six published/address-derived reference points locate fields or public
addresses. They do not define suites, equipment inventories, operating areas or
access permissions. The six unpinned listings remain searchable profiles and
regional/program resources. No product family is added as a separate physical
site. Supporting research and workforce roles are distinguished from documented
core autonomous-systems activity.

## Existing profiles enriched

The [correction manifest](../data/asset_corrections_2026_10_20.json) changes only
the following atomic groups when exact baseline values and protection guards
permit:

- **James City County Police Drone as First Responder Program:** replaces the
  earlier pilot/not-operational AED statement with the county's later report
  that testing was completed and live AED delivery began August 1. The two
  documented baseline groups differ only in their August activity-review date.
  Editorial status, location, taxonomy and editorial verification dates stay
  protected.
- **Hampton Roads Mobility Innovation Center:** adds the September implementation
  MOA, USI's program-integrator/operator role and the development period. Existing
  airport and club operations remain distinct from fully commissioned MIC/BVLOS
  infrastructure. The existing MIC identity and point are retained.

AAC's current [official contact page](https://advancedaircraftcompany.com/contact/)
lists different suites in its body and
footer. The raw catalog now retains only `1100 Exploration Way`, as the saved
hosted and old local profiles already do. No hosted address, pin or staff choice
is overwritten by this catalog-only cleanup.

USI resolves to the existing **Universal Solutions International, Inc.** record.
Existing AAC, Psionic, Tidal Flight, RASWDC, ODU MASTS and other matched identities
are reused. Private, proposed, unresolved and nonphysical suggestions remain in
the local disposition review rather than becoming public facilities.

## Preservation and validation

Final aggregate checks completed October 21: **387 backend tests**, **31 frontend
tests**, and **159 isolated desktop/mobile browser tests with one expected skip**.
The browser run used zero retries and reported no failures or flaky tests. Ruff,
Django system checks, migration checks and the final scoped review pass. All
candidate input hashes and the original SQLite hash remain unchanged. These
checks use isolated local databases/profiles; they do not certify live hosting.

`seed_real_data --add-missing` preserves existing assets and sources. Guarded
new identities now check **both current rows and historical names, display
names and aliases**, including deleted and renamed records. A match holds the
new identity and touching relationships. Existing hidden links and links with
retained deletion history remain protected.

Corrections require the unique expected name, catalog provenance, an intact
before-value group and no protected staff review/history. Retired or manually
controlled evidence is preserved. New evidence defaults to Unreviewed.

The isolated rehearsal starts from a private copy of the old SQLite snapshot,
establishes the preceding RASWDC catalog baseline, then runs the actual full
catalog add-missing command plus the two new correction groups. Results:

- Baseline 556 stored / 543 public; candidate **568 stored / 555 public**.
- Exactly 12 new pending assets, 50 sources for additions, two correction
  sources, and seven relationships.
- Only the stated JCC and MIC fields change on original assets; all unrelated
  asset values, history and taxonomy, old source rows and old relationships are
  preserved.
- Repeat changes nothing, including the SQLite file bytes.
- New models/profiles/APIs, public CSV and GeoJSON, working CSV and all 12 regional
  totals agree. This is isolated SQLite evidence, not hosted PostgreSQL proof.

The main SQLite file remains unchanged at SHA-256
`1560f31bc94c6ed377d09a662beef73151ebf889a8ea5c9cb20f28be15712d4d`.
The old local editorial counts differ from hosted PostgreSQL and are not used to
certify production status.

## Review exports and remaining hosted work

Owner-only local review artifacts under `tmp/chelsea-assets-2026-10-20/` account
for all **50 original suggestion lines** and **18 supplemental portfolio names**.
The original count groups Langley, Fort Eustis and ACC as one suggestion. The
portfolio's three pre-existing matches and three prepared additions are distinct
from its held or noncore entries; its separate claim of 20 active ventures is
not treated as a complete named roster.

The saved hosted public capture has 140 Hampton Roads rows. The prepared overlay
adds ten Hampton Roads listings while preserving those saved hosted regional
choices. The raw generated catalog has different regional assignments for some
existing airports; it is exported separately and does not overwrite production
regional choices. Review exports distinguish saved hosted rows, prepared changes,
local SQLite UUIDs and hosted slugs. They are review artifacts, not sent messages.

The Mac is connected. Supported browser control is not callable in this task's
current tool set. Current Render authentication, release logs, live SHA and full
hosted search/filter/marker/profile/relationship/layer/drawing/analysis/saved-view/
export/comparison/mobile behavior therefore remain unverified for this candidate.
No browser permission, profile, credential or access settings were changed and no
shell browser substitute was used. Inspect an existing candidate deployment
before requesting one; do not repeat a deployment with an uncertain outcome.

## Maintenance lessons

Keep program maturity separate from editorial status; official source availability
does not establish current facility access. Preserve organizational predecessors
in identity checks, including history. Treat products, demonstrations, service
areas and physical facilities as different resources. Use geocoding to position
a corroborated public address, not to infer occupancy or create an operating
footprint. Reconcile hosted and generated regional choices through guarded
updates, never by forcing export counts.
