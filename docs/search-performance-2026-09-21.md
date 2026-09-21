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
