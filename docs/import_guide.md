# CSV import guide

Staff users can validate a CSV at `/admin/imports/preview/`. No database writes occur during preview. A valid preview may then be committed atomically; new records are always created as internal drafts and updated records return to review.

The upload limit is 2 MB and encoding must be UTF-8. Required columns are:

- `name`
- `record_type`
- `short_description`
- `unmanned_systems_relevance`

Use the **Export complete working CSV** command as the preferred template. It includes:

- Identity and description fields
- Website, public contact scope, phone, email, contact link, and full address fields
- Current activity, collaboration route, public source, and activity review date
- Owner/operator, published acreage, development status, infrastructure notes, public source, and development review date
- Coordinates, location precision, and region
- Every taxonomy facet
- Pipe-aligned source titles, URLs, and dates
- Current workflow metadata and internal notes

The complete columns are defined in `apps/imports/services.py`. Legacy `source_title` and `source_url` columns remain accepted for a single source.

Use taxonomy slugs, not display names. Separate multiple slugs with `|`. Source titles, URLs, and dates must have matching positions in their respective pipe-separated columns. Dates use `YYYY-MM-DD`. Latitude and longitude must be provided together.

Any populated activity or partnership field requires `activity_source_url` and `activity_last_verified_at`. Any populated site-readiness field requires `development_source_url` and `development_last_verified_at`. The preview rejects unsourced dynamic claims before a database write.

Records are matched by stable slug first, then by case-insensitive name and city. By default, matches are counted and skipped. Staff may explicitly update matches. Import never trusts workflow status from the spreadsheet: updated records become internal and return to editorial review, and all imported sources return to unreviewed status.

Use [sample_assets.csv](../data/sample_assets.csv) as a column template. Review every imported draft, confirm its evidence, set its verification date, then publish through the guarded admin action.
