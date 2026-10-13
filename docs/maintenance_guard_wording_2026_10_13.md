# COSOLVE guard and wording correction — October 13, 2026

This is the **16:34 UTC preparation checkpoint** for two narrow fixes based on the deployed
Tuesday source `41e0690eac4a5722eb9481f3335d1ef5c085ce77`. Delivery and live
verification are recorded separately; the dated candidate receipt retains its
original prepared/tested state.

An isolated before-fix regression confirmed that `seed_real_data --add-missing`
preserved an existing exact-name staff command's fields, sources and histories
but added a missing catalog relationship. The correction puts any existing
exact-name record with `identity_guard_terms` into the held-identity set before
skipping the asset. New relationships in either direction are held regardless
of visibility, status or retained catalog provenance. Existing public and hidden
relationships remain unchanged; deleted links stay absent. A new command still
gets its intended link to the existing unguarded Little Creek base, and ordinary
unguarded catalog gaps retain their prior behavior.

About data counts public listings, including Published and Source-backed
records. Its aggregate label now says **listed assets**. Counts, editorial review
and publication rules remain unchanged. A mixed-status regression verifies two
public listings, one reviewed and one pending, excluding Internal and Partner
records.

Validation passed: **343 backend tests**, **30 frontend tests**, Ruff, Django
system checks, migration-drift checks and whitespace checks. Mutation tests used
an explicit in-memory SQLite test database. A separate import/repeat on a private
read-only backup of local SQLite preserved all 555 original assets, 1,861 sources,
207 relationships, histories and taxonomy assignments. Only the command, three
Unreviewed public sources and one base relationship were added. Repeating the
import changed no records and left the clone byte-identical. Main SQLite is
unchanged.

The clone's 503 Published / 40 Source-backed counts are local; the existing hosted
PostgreSQL deployment showed 501 / 42. The replay is not hosted verification.
Full post-release 55-field exports, unmapped/private-history preservation,
print/PDF, standalone API/direct browser health and an explicit JavaScript-disabled
live session remain uncertified until directly checked. Server export responses
were previously HTTP 200; Chrome did not save the complete files. No browser
permission/security change or unrelated native-window inspection is required.

See the [dated candidate receipt](../data/maintenance_guard_wording_candidate_2026_10_13.json)
for detailed reproduction, regressions, hashes and preparation state. Private
logs, replay evidence and the reviewed patch remain owner-only under
`tmp/maintenance-2026-10-13/identity-guard-fix`; they are not included in delivery.
