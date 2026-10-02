# MAAP supplied-file integration, October 2, 2026

## Source package

Downloaded all six files from the shared folder provided by the user. The original ZIP is
`/Users/jakeschwartz/Downloads/OneDrive_2026-10-02.zip`; extracted originals are in the
local, untracked `tmp/maap-2026-10-02/` research archive. Do not commit SharePoint sharing
tokens, the full presentation, or proprietary approach/procedure material.

- `Central VA COA Operations Area.kmz`: one polygon plus waypoint placemarks; internal
  folder label **COA DRAFT 108625**. Only the polygon is retained in the published layer.
- `EasternShoreCOA.kmz`: one over-water polygon, retained without state/land clipping.
- `Kentand Farms.kml`: one Kentland outline; original spelling preserved in attribution.
- `MAAP Overview and C-UAS briefing.pptx`: 27 slides. Reviewed flight areas (7-11), CTRC
  infrastructure (14-18), staffing, planning, safety and sensor characterization (19-26).
- `One Page MAAP COAs.pdf`: one-page overview. Altitude datums are clarified using the
  presentation: Kentland AGL; Central Virginia, Blackstone and Eastern Shore MSL.
- `VA AAM Smart Airspace_Sept 2026.pdf`: 11 pages. Reviewed node/status milestones,
  demonstration dates and pad illustrations. No proprietary IFP designs or ZK waypoint
  coordinates are transcribed or mapped.

Sanitized, polygon-only KML inputs are in `data/references/maap/`. They preserve original
coordinate precision, geometry and draft status, while omitting styling, camera positions,
waypoints and remote-resource links. Original-file SHA-256 values are retained in
`data/maap_reference_2026_10_02.json`; generated features also identify their geometry-input
hashes. Rebuild using `.venv/bin/python scripts/build_maap_flight_areas.py`.

## Published changes

- Optional **MAAP flight-area outlines** layer under Layers > Test infrastructure.
  Off by default; saved/copied map views preserve it. Popups show the operator's reported
  dimensions, altitude datum, aircraft scope, access constraints and source status.
- Central Virginia uses a dashed outline and explicit draft status. Import date is not a
  COA approval/expiry date. Blackstone is not synthesized as a circle because R-6602A is
  excluded and no actual geographic boundary file was supplied.
- Six separate records: four MAAP flight environments, Blackstone Smart Airspace vertiport,
  and the temporary Roanoke demonstration vertiport. Area records and unlocated pads have
  no invented point. These represent different resources, not additional companies.
- Seven enriched existing profiles: MAAP, Kentland laboratory, CTRC, VTTI vertiport,
  Smart Airspace program, Blackstone airport and Roanoke airport. Canonical count: 542.
- VTTI 8VA2 now uses FAA feature-service coordinates, checked October 2 and archived in
  `data/references/maap/8va2-faa-2026-10-02.json`. It is labeled a site reference, private/PPR,
  not a surveyed pad boundary. Do not confuse reused identifier 8VA2 with the old, closed
  Shivok Airport; older third-party directories still associate that identifier with Callao.
- CTRC's main-campus administrative proxy is replaced by an explicitly farm-level point
  inside the supplied Kentland outline. No exact sensor platform, building or entrance is
  inferred from a slide image.
- `/references/maap/` provides readable, attributed source summaries. Primary website fields
  remain official operator/program websites, not the private SharePoint folder or a PDF.

## Limits and follow-up

These supplied summaries are evidence of described capabilities, not independent verification
of current COA validity, completeness, access, certification or operator eligibility. New and
materially changed claims remain **source-backed; editorial review pending**. Baseline-guarded
updates preserve later staff edits, private records and staff decisions about sources.

The one-page area claims are attributed, not calculated from polygons. QA using an equal-area
projection (EPSG:5070) estimates outline footprints of approximately 2.55, 4,873.07 and
998.77 square miles for Kentland, Central Virginia and Eastern Shore respectively. Do not
quietly replace the briefing's 2.5/4,500/990 figures, resize the outlines to match, or treat
the discrepancy as proof that either is an approved current boundary. Ask MAAP to reconcile
the Central Virginia draft and supply the latest COA instruments and Blackstone geometry.

The briefing reports July 2026 Aerosonde flights and September 2026 Electra EL2 flights.
Procedure submission at VTTI/Roanoke is not equated with approval. Roanoke remains temporary;
its permanent-site coordinates and ongoing availability are unresolved. No aircraft capacity
or pad dimensions are inferred from pictures. Farm acreage is not marketed as available land.

Two accepted airport baselines are exact, earlier generated descriptions confirmed in Git
at `6d9fa1b^`: Blackstone's "General Aviation Community" and Roanoke's "Air Carrier" category
labels. These permit updates from older seeds, not arbitrary staff prose.
