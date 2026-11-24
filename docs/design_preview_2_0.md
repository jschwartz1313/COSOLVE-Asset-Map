# 2.0 Design Preview

The standard light interface remains the default. The owner can select **2.0** in
the header, then **Current** to restore the original presentation. This is an
opt-in review prototype, not a replacement launch or a separate inventory.

The preview uses the same Django views, asset records, queries, filters, map,
comparison selection, sources and permissions. No assets are copied or modified.
A CSRF-protected POST stores the selected presentation in the browser session.
The switch preserves the current URL and its filters. Navigation between pages
and states retains the selected version. Exported and shared data remain the same.

The new presentation adds a desktop navigation rail, a separated map tool strip,
a quieter results column, updated directory hierarchy, and reorganized profile
styling. Tablet and phone layouts retain the compact navigation and filter drawer.
Printing and presentation mode hide the navigation rail.

The button and presentation are available only to accounts on the private preview
allowlist with existing asset access. Currently that is `jschwartz` alone. An old
session flag cannot enable it for another account. Ale, Chelsea, and other users
retain the standard Virginia site. The GitHub repository remains public by the
owner's explicit decision; website restrictions do not conceal repository files.

All preview CSS is isolated in `static/css/experience-v2.css`. Removing the opt-in
flag restores the standard styles. No schema migration or hosting change is needed.

## Information Layout Trial, November 24

The first 2.0 version is preserved at Git tag
`design-v2-before-data-layout-20261124`, commit `3137210ce0207a894372bd808393422283dfaa70`.
A source ZIP and before screenshots are also stored on the owner's Desktop in
`COSOLVE Design History/2026-11-24 Before data layout`.

The trial retains the navigation rail and existing controls. Directory rows group
identity and location together, give descriptions a wider column, and keep focus
and portfolio information visible. Map result names lead each record. Profiles
promote contact/location to a horizontal section and use one reading column for
the substantive asset information. No asset fields, sources, permissions or
exports are changed. The standard interface retains its original layout.

To undo the trial, restore only its changed presentation files from the baseline
and remove the two trial-only partials. Do not reset the repository or restore a
database: later asset edits and unrelated work must be preserved.
