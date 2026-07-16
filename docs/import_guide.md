# CSV import guide

Staff users can validate a CSV at `/admin/imports/preview/`. No database writes occur during preview. A valid preview may then be committed atomically; new records are always created as internal drafts.

The upload limit is 2 MB and encoding must be UTF-8. Required columns are:

- `name`
- `record_type`
- `short_description`
- `unmanned_systems_relevance`

Optional columns include `city`, `state`, `latitude`, `longitude`, `region`, `strategic_categories`, `platform_domains`, `capabilities`, `missions`, `source_title`, and `source_url`.

Use taxonomy slugs, not display names. Separate multiple slugs with `|`. Latitude and longitude must be provided together. Records are matched by case-insensitive name and city; duplicate matches are reported and skipped during commit.

Use [sample_assets.csv](../data/sample_assets.csv) as a column template. Review every imported draft, confirm its evidence, set its verification date, then publish through the guarded admin action.

