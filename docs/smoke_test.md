# Browser smoke-test checklist

1. Load `/map/` without authentication and confirm the map and published result count appear.
2. Filter Hampton Roads, Test and operational environments, and Maritime surface systems.
3. Confirm map markers and result cards represent the same records.
4. Select a card, confirm its marker opens, then open its public profile.
5. Confirm the profile includes relevance, taxonomy, public sources, and last-verified date.
6. Use browser back and forward controls and confirm filter state is restored.
7. Clear all filters and confirm the URL and result set reset.
8. Load `/directory/` with JavaScript disabled and verify filtering and profiles still work.
9. At mobile width, open and close the filter drawer and inspect text for clipping or overlap.
10. As staff, import the sample CSV, review the draft, add evidence, verify, publish, and archive it.
11. Open `/regions/compare/`, change both regions, and confirm counts and map links update.
12. Open `/about-data/` and confirm the catalog, source, region, and verification summaries render.
13. Open a profile with related assets and confirm outgoing and incoming connections link correctly.
14. As staff, export a filtered CSV and review `/admin/imports/data-quality/`.
15. Confirm the legend, reset-view control, active-filter count, and collapsed-section counts work.
