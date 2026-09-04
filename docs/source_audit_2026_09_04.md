# Source audit — September 4, 2026

The final catalog contains 525 assets and 1,038 unique source, website, activity and contact URLs across 2,793 URL references. Its exact input SHA-256 is recorded in the ledger and was checked against the frozen final catalog. Every URL received a bounded GET request; the ledger retains request times, final destinations, response codes, content fingerprints, associated assets and text-screening signals.

## Results

| Result | URLs |
| --- | ---: |
| reachable | 904 |
| access blocked or rate limited | 108 |
| http not found | 1 |
| network or tls error | 23 |
| redirected to homepage review | 2 |

95 assets have at least one URL requiring review. 66 assets had no successful readable HTML/text source available to the checker; many rely on PDFs or government sites blocking automated requests. These are access and review flags, not findings that the assets are invalid.

## Verified repairs and unresolved evidence

The reviewed source repairs are in `data/source_fixes_2026_09_04.json`. The final catalog incorporates all seven proposed replacements and both additional evidence sources. They restore current official CACI counter-unmanned systems, Axon/Dedrone product, Hampton admission, Wrap annual-report, and three renamed-college VCCS routes. The Wrap document was opened and read through the web tool even though the bounded direct fetch timed out. The replacement report supports the published Norton street address and assembly activities while retaining the distinction between current manufacturing and developmental counter-UAS products.

Haymarket’s council packet and a search-indexed duplicate annual report return 404 to direct requests. The indexed report still contains the historical implemented-program statement, and the separate award schedule plus DCJS board minutes support the CY2026 replacement award. A cached search hit must not be passed off as a working replacement. Blue Ridge Defense Works requires priority editorial follow-up: its homepage is 404, its SAM client-rendered page yielded no entity text, and exact-name searches did not corroborate the Virginia counter-UAS role. These findings do not establish closure or nonexistence.

The full ledger includes a follow-up reason for every affected asset, without changing historical review snapshots or live publication status. No proposed URL repairs are silently applied by the audit script. The catalog corrections separately replace the Haymarket dead packet with a working agency website and official grant-approval evidence, qualify its status, and mark Blue Ridge as research follow-up. A new NOVA record’s expired event URL was replaced with a current official campus-location page before finalization.

## Before and after

The initial 500-asset sweep checked 954 URLs: 823 reachable, 105 blocked, 18 transport/TLS failures, five HTTP 404 responses and three homepage redirects. The final 525-asset sweep checks 1,038 URLs. HTTP 404 sources fell from five to one despite the added records. The only remaining 404 is Blue Ridge’s already-qualified research lead. Both remaining homepage redirects were manually reviewed as retained-identity/homepage routes. Three VCCS failures were successful HTTP responses with missing specific content and therefore were discovered through text review, not the original 404 count.

A compact immutable baseline summary is retained in `data/source_audit_baseline_summary_2026_09_04.json`. The final ledger is `data/source_audit_2026_09_04.json`. Blocks and transport failures remain inconclusive; they are not a count of broken or invalid assets.

## What this audit establishes

All catalog URLs were inventoried and checked. Each asset’s successfully retrieved source text was screened for its exact name, the base street address, and unmanned-systems terms. These literal signals help prioritize review. An address text match is not coordinate verification, and a missing text match is not evidence that an address is wrong. The audit found 285 literal street-address matches in retrieved text.

The checker does not render JavaScript, extract PDF text, or individually verify every descriptive sentence, capability label, operating-status claim, contact person, and geographic coordinate. A successful HTTP status is not substantive verification. 59 responses exceeded the 1 MiB body limit. All classifications preserve these limits.

## Verification workflow issue

The prior implementation of `scripts/build_asset_verification_manifest.py` selected source evidence using name/title/URL scoring and then labeled records `confirmed` unless pre-existing follow-up or historical flags said otherwise. It did not fetch the selected evidence or demonstrate that an editor read the claims. The generator now exports only pending-review candidates and cannot overwrite existing snapshots. Earlier snapshots remain historical artifacts; new confirmations require explicit dated editorial decisions. HTTP availability and editorial fact verification remain separate.

## Additional content findings and priorities

Three renamed community colleges retained obsolete VCCS college slugs: Brightpoint (`jtcc`), Laurel Ridge (`lfcc`), and Mountain Gateway (`dslcc`). The old URLs return HTTP 200 but only generic navigation, with no named-college course descriptions. Current official pages use `brightpoint`, `laurelridge`, and `mgcc`; their unmanned-systems descriptions were fetched and read. This is a concrete failure that a status-only checker misses. A catalog course listing supports the curriculum; it does not guarantee that a class runs in the current semester.

Suffolk Police UAS Unit's original evidence consisted of three staff/contact directory pages. The main EID60 staff page currently identifies a captain without mentioning UAS. A separate official police announcement explicitly identifies UAS Team membership and was confirmed as an accessible PDF. That direct evidence is now attached to the asset; the directory supports contact information. Hampton University's general institution record now also includes its separately published official UAS-program page to substantiate its program claims.

Prioritize explicit claim-to-source records: distinguish identity, current activity, street address, geographic point, and contact evidence, each with an observation date. A staff biography can support a team affiliation only while the text actually says so. A directory page, homepage, or OpenStreetMap copyright notice cannot independently substantiate an exact operating site. Link a specific mapped feature or an authoritative location document, and keep an approximate/site point when that is all the evidence supports.

Do not automatically promote a campus mailing address, administrative headquarters, parcel midpoint, or street-range geocoder match to an exact facility position. Precise decimal coordinates are a display format, not proof of location accuracy. Separately flag scheduled projects, development programs, and historical announcements so that a funding award or old program description is not silently represented as independently confirmed current operations.

The audit also exposed an unsolicited compressed HTML response from Devorto. The reusable checker now decodes bounded gzip content and refetches earlier garbled cached text, avoiding a false readable-text classification.

## Repeating the check

Run `python3 scripts/audit_catalog_sources.py` after catalog changes. Previously checked URLs use the cache at `/private/tmp/cosolve-source-audit-2026-09-04`; new URLs are fetched automatically. Use `--refresh` for a full new fetch, `--catalog` for another input, and `--output` for a separate immutable snapshot. Each cached URL retains its real check time. This script is read-only with respect to the catalog and database.

Run `python manage.py apply_source_audit --dry-run` to preview importing the ledger, then omit `--dry-run` to populate source availability. The command applies only newer observations to exact-matching public source URLs. It writes only `last_checked_at`, `http_status`, and `check_error`, preserving all editorial verification, notes, and accepted/replacement decisions. Six focused tests cover exact matches, private records, preservation of manual decisions, stale observations, idempotence, transport failures, redirects, malformed ledgers, and dry runs.

The audit uses only public HTTP(S) URLs, validates initial and redirect hosts, allows at most two concurrent requests per starting host, and caps response reads. The standard HTTP client does not eliminate DNS-rebinding risk completely; redirects are not independently rate-limited by their final host.
