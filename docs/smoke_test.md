# Browser smoke-test checklist

Use the hosted site's existing authorized session for live checks. Record the deployment
and database being checked. Local SQLite results do not certify the hosted Render
PostgreSQL database. Run import, publication, archive, saved-view mutation and other
write tests against an isolated test database; preserve staff edits and production data.

1. Check `/health/` anonymously, then confirm protected hosted `/map/` and `/api/assets/` redirect to sign-in. In the existing authorized session, load `/map/` and confirm the listed-asset count appears. Local development can have login disabled.
2. Filter Hampton Roads, Test and operational environments, and Maritime surface systems.
3. Confirm map markers and result cards represent the same records.
4. Select a card, confirm its marker opens, then open its public profile.
5. Confirm the profile includes relevance, taxonomy, public sources, and last-verified date.
6. Use browser back and forward controls and confirm filter state is restored.
7. Clear all filters and confirm the URL and result set reset.
8. Load `/directory/` with JavaScript disabled and verify filtering and profiles still work.
9. At mobile width, open and close the filter drawer and inspect text for clipping or overlap.
10. In an isolated database as test staff, preview and import the sample CSV, confirm it becomes an internal draft, add evidence, review, verify, publish, and archive it. Exercise guarded corrections with conflicting staff edits and confirm those edits survive.
11. Open `/regions/compare/`, change both regions, and confirm counts and map links update.
12. Open `/about-data/` and confirm the catalog, source, region, and verification summaries render.
13. Open a profile with related assets and confirm outgoing and incoming connections link correctly.
14. As staff, export a filtered CSV and review `/admin/imports/data-quality/`.
15. Confirm the legend, reset-view control, active-filter count, and collapsed-section counts work.
16. Check every enabled reference layer, retrieval dates, attribution, access caveats and precision labels. Confirm unmapped and regional records do not acquire invented points.
17. Draw an area, check selected assets and analysis totals, and export the selection. Test saved-view creation/deletion only in isolation; check copied-view restoration without writing production data.
18. Compare the complete public CSV/API records with cards, markers, profiles and related assets. Report source-backed pending listings separately from editorially reviewed listings.
19. Record prepared, locally tested, pushed, deployed and live-verified outcomes separately, including blocked checks and the evidence needed to resume them.
