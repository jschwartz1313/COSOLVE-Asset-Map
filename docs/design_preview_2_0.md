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
