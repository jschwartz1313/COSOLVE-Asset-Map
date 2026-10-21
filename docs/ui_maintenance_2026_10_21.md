# UI follow-up — October 21, 2026

Hosted QA of the released `097f6bc180a9a927ae7bd66e853965dbd354bef9` candidate found two presentation defects. The asset import and guarded MIC completion are already verified and are not repeated by this work.

## Overlay failure and recovery

After a failed reference-layer request, the checkbox correctly reset and the legend stayed hidden, but a successful retry left the old failure text visible. Asset loading and reference-layer failures previously wrote to the same status field.

The map now keeps the asset-list message and each layer's failure separately. A successful layer operation clears that layer's failure while retaining other failed layers, a truncated-list notice or an asset-loading error. All nine reference layers use the existing shared toggle lifecycle. The viewer module's version changes so returning browsers receive the fix.

The old failed-overlay browser test used `check()`, which requires the checkbox to remain checked after a click. That races the intended immediate reset after an injected HTTP 503. The regression now clicks from an explicitly unchecked state, then asserts the error, unchecked/enabled control, absent geometry and hidden legend. Each of the nine layers is retried and must restore its geometry and legend and clear the obsolete warning. Additional tests preserve unrelated layer failures, truncated-result notices and asset-loading failures. The FAA ceiling layer is checked using its actual canvas renderer; other layers use SVG paths or markers.

## Incoming relationship direction

Incoming profiles formerly reused outward verbs, so Maxbyte's profile said “Hosts Tidewater Community College” even though the stored relationship is TCC → Maxbyte. Incoming links now say “Hosted by,” “Supported by,” “Operated by,” “Funded by,” “Location of,” “Participants include,” “Partners with,” or “Receives manufacturing from,” as appropriate. Unknown legacy values use neutral wording.

Stored relationship directions/types, outgoing labels, API direction fields, history and privacy/regional filters are unchanged. Regression tests cover all eight supported types and real desktop/mobile navigation for TCC/Maxbyte, ODU/AAES, MIC/the flying field and P1/Blue Vigil.

## Delivery boundaries

Final isolated validation passed: 400 backend tests, 31 frontend tests and 189 desktop/mobile browser checks plus one expected skip, with zero browser failures or retries. Ruff, Django configuration and migration checks also passed. The first browser launch could not bind inside the sandbox and ran no tests; the subsequent run exposed two new SVG-only assertions for the existing canvas ceiling layer. Those assertions were corrected and the final full suite passed. Earlier receipts remain in the private dated evidence directory.

This work starts from the user's basemap-preview commit `73d32abfcbee24ea9aeadc46b940907041f15fd9` and preserves that change, existing maintenance edits, release evidence and the original SQLite database. Validation uses fresh isolated databases and bundled Chromium, not hosted PostgreSQL or Jake's Chrome profile.

Exact-commit CI, authenticated Render history/access, deployment and hosted verification are separate delivery stages. The explicit Chrome `ERR_BLOCKED_BY_CLIENT` final public-CSV download remains blocked and must not be bypassed. The completed release's working export proves its current-field comparisons; it is not a complete database-history dump.

The separate [VA-FIX reference review](asset_reference_review_2026_10_21.md) describes the new email's narrowly guarded reference update and held suggestions.
