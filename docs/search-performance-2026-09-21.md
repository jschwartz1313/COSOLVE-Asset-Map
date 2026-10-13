# Reversible search optimization

## Scope

- Previous implementation: commit `3d39f83`.
- Search each taxonomy, public source, and public relationship independently with
  `EXISTS`, instead of joining all to-many relations into one intermediate result.
- Keep the same searchable fields, synonyms, quoted phrases, word intersection,
  relevance ordering, public visibility rules, and regional release scope.
- Fetch one extra result at the API limit. Reuse the returned row count when the
  complete result fits; run an exact count only when results are truncated.
- No changes to asset records, database schema, authentication, hosting plans,
  frontend behavior, or caching. Staff edits remain immediately searchable.

## Comparison

Compared complete response bodies from the old and new implementations for 20
search/filter/limit combinations on both the map GeoJSON API and list API.
All 40 responses matched on the existing local SQLite database (527 public
assets), and all 40 matched again on PostgreSQL. The PostgreSQL check uses a
separate, temporary database seeded with the checked-in 527-asset catalog, not
the live Render database.

Representative PostgreSQL 18 map API timings on the development computer:

| Search | Before | After |
| --- | ---: | ---: |
| airport | 227 ms | 20 ms |
| MAAP | 210 ms | 8 ms |
| drone | 682 ms | 103 ms |
| Virginia Tech | 326 ms | 46 ms |
| No match | 201 ms | 6 ms |

Each number is the median of two interleaved runs of the old and new handlers,
including database work and JSON serialization. These are diagnostic samples,
not production latency guarantees; unrelated backend tests were also running.
Normal, untruncated responses now use six database queries instead of seven;
an empty search result uses one instead of two.

Verification: all 257 backend tests passed on PostgreSQL, 50 focused backend
tests passed on SQLite, and all 27 frontend unit tests passed. Python lint and
the migration-drift check passed; no migration is required.

## Acceptance on Render

After the deploy completes, compare repeated searches for `airport`, `MAAP`,
`drone`, and `Virginia Tech` in the signed-in map. Check region and capability
filters, clear-all behavior, the directory, and exported matching records.
Measure the asset API request separately from map drawing and tile loading.
The authenticated production search has not been benchmarked in this change.

## Rollback

This change is isolated in the commit titled
`Optimize public asset search without changing results`.
Revert that commit and push the revert to `main`, then let Render redeploy.
There are no database migrations or data changes to reverse. Do not reset the
entire repository to `3d39f83`, as that could discard later unrelated work.

## Name typo matching October 13 2026

Search now supplements ordinary matches with close matches to words in public
asset names, display names and approved search aliases. For example, `reactor`
finds **REaKTOR Technology Innovation Center** without changing its official name.
The map, directory, filtered exports and APIs share this search implementation.

- Ordinary matches retain their previous ordering and precede typo-only results.
- Every search term and active filter must still match the same asset.
- Quoted phrases and words shorter than five characters retain literal matching.
- Only alphabetic, unquoted words of 5-48 characters receive typo matching.
- Python's standard-library `difflib.get_close_matches` selects at most three
  candidate name words per search term. Candidates differ in length by at most
  two characters; the similarity cutoff is 0.84, or 0.8 for five-character words.
- Private records, excluded institutions and assets outside the release scope
  cannot contribute name candidates. Private fields and sources are not scanned.
- One lightweight name/alias query is added for eligible searches. There are no
  database extensions, migrations, external search requests or stale name caches.
  Staff name and alias changes are immediately searchable.

Five interleaved local SQLite comparisons returned identical response bodies for
`airport`, `drone`, `MAAP`, `Virginia Tech` and an unrelated no-match string.
`reactor` changed from zero results to the intended single center; its median
complete GeoJSON response was 22 ms. These development timings do not establish
Render performance or remove hosting cold starts.

The focused search regression suite passed 57 tests on both SQLite and a separate
temporary PostgreSQL database. Desktop/mobile browser coverage includes entering
the typo, applying filters and carrying the same search into the directory.
No asset data was edited by this feature. Reverting the dedicated typo-search
commit reverses the feature without undoing the September query optimization.
