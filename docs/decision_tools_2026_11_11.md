# Planning tools and operator intake

## Public tools

- Directory/profile: Add to comparison selects up to five assets in this browser. The comparison URL can be shared with other authorized viewers. Compare also has a server-rendered asset chooser and CSV export.
- More > Manufacturing search: process, material, service mode and documented access. Only usable matching public sources enable positive matches. Missing specifications remain unknown, not confirmed incompatibility or capability. Current capacity and acceptance require an operator conversation.
- Profile > Prepare an inquiry: creates a text draft from the user's project requirements. It does not send email or store project information in the asset database. The user can edit or download the draft.

Directory presentation follow-up: comparison now occupies a normal-flow row directly below the result heading and above the records. Compact checkboxes replace the repeated add/remove links. The count and clear action stay together at the top; no floating selection bar covers records. Five selections disable unselected controls until one is removed. Existing browser selections and comparison URLs are unchanged. Eleven focused backend and 28 desktop/mobile regression tests passed for this adjustment.

Selected-name follow-up: the comparison section now lists every selected public display name, with profile links and individually labeled remove buttons. Names remain visible across filters, pagination, profiles, reloads and browser tabs. Full names wrap rather than truncate at 320, 390, 768 and 1440 pixels. The browser still stores only slugs; missing names resolve in one bounded public-scoped query, never a per-asset request. Hidden or retired records are dropped without revealing their names. A failed lookup preserves the selection and offers Retry. Delayed responses cannot restore removed selections; keyboard focus is maintained after removal or clearing. Legacy saved selections remain compatible. The full UI pass covered 271 passing browser tests with one existing skip; all 34 frontend tests passed.

The selected-name follow-up also passed all 545 backend tests, configuration and migration checks, CI lint, and production-mode static-file collection.

The hosted browser check exposed an early-click race on a slow initial script load: a native checkbox could be clicked before the selection handler initialized and then reset. Directory checkboxes and profile selection buttons now stay disabled until their handlers are ready. The slow-module regression failed before the fix and passed afterward. The final full UI run passed 273 tests with the same one existing skip.

## Operator review

Staff with asset-edit and operator-review permissions can select one public asset in Admin > Assets and choose Create operator review invitation. The resulting record displays a private, two-week link on the current site's domain. Staff manually shares the link with the operator; the application sends no email.

The operator can propose use cases, access requirements and public contact details without a site account. The form separates private follow-up identity from public content and requires explicit publication consent. An invitation is single-submission, expiring and revocable. Invalid links reveal no asset details; responses are non-cacheable and suppress referrers/indexing.

In Admin > Operator reviews, review the proposed public content, select the proposal and choose Approve selected operator proposals. Approval preserves the main asset and its editorial status; it publishes supplemental information only. A changed asset/taxonomy or an intervening accepted proposal blocks approval. Start a fresh invitation rather than overwriting staff decisions. Revocation removes the supplemental information. If the asset changes after approval, supplemental details are hidden pending renewed review.

Guest and Viewer accounts cannot create invitations, approve proposals, read private submitter information or change records. Editor and higher groups receive the new maintenance permissions. No public approval dates or editorial review badges were introduced.

## Diagrams

Admin asset records accept site diagrams with an image URL, alternative text, source, caption and credit. Staff must explicitly approve publication and confirm rights/sensitivity. Approved images appear only inside Supporting details. Private sharing links, credential/query-bearing image links, non-HTTPS images and non-bitmap images are rejected. The server does not retrieve remote images. No operator diagrams have been assumed approved or invented for this release.

## Manufacturing evidence

Eight existing records have an insert-only structured profile in `data/manufacturing_fit_2026_11_11.json`: IALR, Allocortech, Kollmorgen Radford, Ryzing, P1/Keltech, Fulcrum Newport News, Radian Forge Portsmouth and Moog Blacksburg. The manifest records each primary source and its site-specific scope. No numeric build envelope, tolerance, material or contract-access permission was inferred.

`seed_manufacturing_fit` previews by default. The release runs it with `--apply --add-missing-sources`. Existing profiles, staff-managed records, changed identities, retired sources and private/unusable sources are preserved. This adds structured information, not new inventory assets.

## Earlier profile pass

The previous 30-record enrichment is deployed. Hosted comparisons matched 29 records completely; Hampton Roads Mobility Innovation Center retained its prior overview/contact text under the staff-protection rules. Its public source links remain present. This record was not force-updated.

## Verification

Backend coverage includes public scoping, unknown-vs-match behavior, CSV formula escaping, draft-only inquiry behavior, publication consent, single-use/expired/revoked invitations, stale approval conflicts, public/private contact separation, safe image links, permissions and source retirement. Browser checks cover desktop and phone layouts and the existing map workflows. New diagrams require operator-approved source material before population.

Final publication-copy results: 543 backend tests passed, 31 frontend tests passed, 253 browser tests passed and one existing browser test was skipped. The final 10-test browser run also covers shortlist removal persistence. Configuration, migrations, static-file collection and CI lint passed. An isolated operator-form browser check exercised submission, consent, CSRF and single-use links on desktop and mobile. Temporary QA records were not added to the live database.
