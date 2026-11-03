# Test-site criteria and access search

## Entry Points

- More > Test-site search (`/test-sites/`).
- Map and Directory > Project and site details > Documented test-site access.
- Aircraft comparison link in those filters and the profile's collapsed searchable criteria.

## Comparison Rules

Compare only requested criteria. An empty request is a reference listing, never a
suitability claim. A documented numerical limit below the request produces a
published-limit conflict. Missing values, unpublished launch/activity coverage,
unusable evidence, and pilot/planned/developing availability produce needs
confirmation. A category's absence does not establish prohibition.

Aircraft weight and span/width use pounds and feet. No numeric envelope is inferred
from acreage, pad/enclosure dimensions, aircraft Groups, runway length or COAs.
The Xelevate Leesburg operator's less-than-55-lb condition has an exclusive bound;
55 lb is a conflict, not a match. It is not assigned to Luray. No documented maximum
span has been invented to complete the fields.

Structured facts need their own public source and check date. Source records that
are hidden, rejected, stale or marked for replacement disable matching; duplicate
contradictory source decisions also fail closed. Runway comparisons use their
separate existing source. Historical facilities are excluded from the search.
Public regional scope, user permissions and publication status are retained.

Access conditions are nonexclusive, not promises of availability or public entry:
commercial inquiries, research access, partner approval and restricted/sponsored
access. Unknown access remains selectable. Initial conservative transcription
covers seven records in `data/test_site_criteria_2026_11_03.json`; other records
remain unknown. Operator narrative and contact information remain available.

## Storage and Maintenance

Migrations add optional structured fields to assets and their history. Admin uses
checkboxes for option sets. Existing staff edit permissions are unchanged. CSV
imports/exports preserve JSON option lists and strict-bound flags; imports retain
the existing internal/draft review workflow. The public detail API masks unusable
structured evidence. Comparisons export selected outcomes with requirements,
source references and the planning-only qualification.

The catalog builder and guarded release corrections share the new facts. Staff and
source decisions are preserved. Generic enrichment deliberately does not fill
structured facts or interpret their empty lists/false defaults as an existing
legacy profile. There are no hosting, account or handoff changes.

## Interface Checks

Use the established light design and wrapping select controls. Results are unframed
rows. Operator conditions remain collapsed. On phones, submission jumps to results
and Edit requirements returns to the form. Test 320, 390 and 1280 pixel widths,
strict numerical boundaries, unknown information, hidden/stale evidence, map and
directory parity, clear/reload, CSV exports and admin editing before release.
