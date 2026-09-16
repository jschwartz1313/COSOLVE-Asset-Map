# Reference layer maintenance

## Cadence and ownership

The site maintainer reviews FAA airspace snapshots weekly, heliports at least every
28 days, and the three curated test-facility profiles every 90 days. The weekly
GitHub Actions **Reference layer refresh review** workflow downloads and validates
candidate FAA airspace and heliport files each Monday. It can also be run manually.
Candidates are uploaded as a 30-day artifact; they are not automatically deployed.
The maintainer must review, commit, and push accepted changes. A failed run leaves
the published files untouched; check Actions for failure notifications.

The interface reads `metadata.generated_at` from the shipped GeoJSON and shows
**Snapshot** beside each reference layer. Once the review interval elapses, it
shows **Refresh review due**. Rebuilding the application cannot make an old
snapshot appear new. Missing, malformed, and future dates are shown as unavailable.
The cache version comes from the same date. A retrieval date does not establish
that FAA records changed, that a facility is available, or that flight is permitted.

## Review and publish

Run from the repository root with its Python environment activated:

```sh
python scripts/build_drone_airspace_layers.py --faa-only --output-dir tmp/reference-refresh
python scripts/build_heliport_layer.py --output-dir tmp/reference-refresh
python scripts/review_reference_refresh.py tmp/reference-refresh
```

Inspect source identity, feature counts, geometry, key popup fields, and differences
from the previous snapshot. The validator rejects empty/incomplete datasets,
duplicate identifiers, invalid geometry, changed sources, missing fields, and
feature-count changes over 25%. Investigate rejected data rather than bypassing a
check simply to obtain a newer date. An old downloaded artifact should be fetched
again before publishing; publication validation requires a same-day retrieval.

After reviewing the differences:

```sh
python scripts/review_reference_refresh.py tmp/reference-refresh --publish
python manage.py test tests.backend.test_drone_airspace_layers tests.backend.test_layer_freshness
```

Smoke-test all four FAA overlays, then commit and push the four changed GeoJSON
files through the normal deployment process. No database migration is required.
If necessary, restore the previous snapshot files with a new reviewed commit.

## Curated facilities and other geography

The test-site builder deliberately retains `TEST_SITES_REVIEWED_AT`. Review each
operator source and specification before updating that date and regenerating the
test-site file. A network refresh must never imply those descriptions were vetted.
County/state boundaries remain labeled by their source vintage (currently Census
2025); regional groupings and potential MPZ tracts are analytical reference data,
not operational airspace layers. Revisit them when the source or definition changes.

## September 15, 2026

Refetched 7,002 UAS Facility Map cells, 33 surface controlled-airspace features,
139 flight-constraint features, and 128 heliports. Test-site specifications retain
their August 12 snapshot date. These reference layers do not include live NOTAMs,
TFRs, authorizations, or site-access permissions.

The earlier downloader rounded polygons to six decimal places. Validation found
that this collapsed a small ring at Dulles Discovery 2 and introduced a
self-intersection at MCB Quantico. The downloader now retains the FAA's full
coordinate precision; both polygons pass validation without modifying the source
boundaries or dropping features.

## Basemap requests

Leaflet tile images use `strict-origin` as their referrer policy: providers receive
the site's origin, not page paths, searches, or account details. This fixes a
conflict with Django's default `same-origin` policy, which suppressed the referrer
required by the [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/).
The site's policy for other requests is unchanged. Previously blocked tiles can
remain in the browser cache until they expire. Do not bypass provider caches or
bulk-download tiles. For sustained production use, configure an appropriately
licensed provider using the existing basemap environment variables.

Outstanding provider setup: on September 15 the default CARTO Light basemap
returned tiles watermarked "API KEY REQUIRED" in a normal browser. Street works
after the referrer correction. The maintainer should configure a licensed Light
provider through `LIGHT_BASEMAP_TILE_URL` and its matching attribution; no API
credentials were created, purchased, or committed as part of this change.
