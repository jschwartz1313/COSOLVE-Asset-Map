# Comparison asset picker

The comparison page now has an Add assets button opening a native modal dialog. The visual reference informed the list-and-search layout only; no unrelated geography content was added.

The picker browses the current public inventory without requiring a query, uses the site's existing fuzzy search, and offers asset-type and region filters. It displays 24 results per page. Pending selections persist across searches, filters and pagination and appear in a removable draft list. Previously compared records are checked and unavailable. Existing plus pending selections cannot exceed five.

Add selected assets navigates to the canonical comparison URL and preserves the order of existing assets. Cancel, the close button, clicking the backdrop and Escape leave the comparison unchanged. Keyboard focus stays inside the dialog and returns to its opener. The header and footer remain visible; short landscape screens scroll the filters and results together. Full asset names wrap on narrow screens.

The original server-rendered search remains available without JavaScript. Older comparison search URLs open the picker with their query preserved. The Add assets opener is exposed only after its event handlers are attached, preserving the slow-loading safeguards on comparison controls.

The read-only `/compare/options/` endpoint uses the same public visibility, release-region and institution exclusions as the directory. It returns only name, slug, profile URL, type and public locality. It does not expose contact submissions, review notes or private records. It rejects oversized or malformed filters, is not cached, and remains behind the existing site login when enabled. No database schema, inventory records or permissions changed.

Verification: 555 backend tests and 37 frontend tests passed. The final full browser run passed 291 tests with one existing skip. Picker coverage includes empty browsing, fuzzy spelling, filters, pagination, draft preservation, maximum selections, keyboard containment, cancellation, stale/failed requests, no-JavaScript fallback and existing search URLs. Layout screenshots were inspected at 320, 390, 768 and 1440 pixels and in 844-by-390 landscape. Production-mode static collection, configuration, migration and CI lint checks passed.
