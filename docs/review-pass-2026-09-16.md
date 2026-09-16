# Public-source review: September 16, 2026

## Scope and standard

This pass covers all 71 previously pending editorial reviews, 34 locality-level
locations, eight regional activities and eight outstanding airport website searches.
It is a public-source desk review, not a site visit, independent product test, flight
authorization or assurance that every underlying assertion is correct.

The complete record-by-record findings and source links are in
`data/asset_review_pass_2026_09_16.json`. Deployment changes are baseline-guarded:
staff edits, explicit unverification and unresolved editorial warnings are not
overwritten. Research candidates do not become reviewed merely because a URL responds.

Applied locally: 54 additional asset reviews and 118 source reviews, bringing the
527-record public catalog to 510 reviewed records and 17 unresolved reviews. Location
precision is now 141 exact, 350 site/campus, 28 locality-level and eight regional.
These totals describe the catalog; protected staff-edited records on another
deployment may be intentionally skipped.

## Location changes

Six locality references now use corroborated public contact addresses or a named-site
reference. They are labeled **Site or campus**, not **Exact**:

| Record | New reference | Qualification |
| --- | --- | --- |
| TurbineOne | 14120 Sullyfield Circle, Suite J, Chantilly | Company-published headquarters; T1 Edgeworks opening not established |
| Manassas police drone program | 9608 Grant Avenue, Manassas | Police contact building, not launch/storage location or proof of 2026 grant recipient |
| Marine Corps Warfighting Laboratory | 2084 South Street, Quantico | Public administrative address, not experimental operating area |
| NSWC Dahlgren Division | 6149 Welsh Road, Suite 203, Dahlgren | Public affairs/contact address, not range boundary |
| Surface Combat Systems Center | 30 Battle Group Way, Wallops Island | Public command contact, not operational test location |
| Pentagon | Named Pentagon headquarters site | Replaces Arlington locality center; no internal offices or entrances mapped |

Census coordinates are address-range estimates. Esri address/POI matches are reference
positions, not surveys. An official source establishes the organization's published
address; the geocoder only positions it. Unmatched candidates, including Fort Walker's
visitor address, are not promoted from postal/locality results to building precision.

All eight regional activities remain without a single pin. Heven's Dulles office is
not substituted for its Winchester campus. Magothy's Maryland water-testing sites are
not assigned to its Virginia office. MITRE's Orange County range and MARS's dedicated
airfield remain approximate until the operator publishes an appropriate site reference.
Public administrative addresses do not supersede the policy of generalizing sensitive
military operations, facilities and testing areas.

## Editorial findings

54 records have selected official evidence supporting completion of the catalog desk
review. Their individual findings preserve qualifications about planned facilities,
historical trials, developmental products and company-published capabilities. Review
status does not upgrade a locality pin to an exact location.

17 records remain follow-ups:

- Ten jurisdiction-level first-responder entries still lack a confirmed operating agency.
- Manassas police drone use is documented, but current program details and the link to
  the jurisdiction-level 2026 award remain unresolved. Its name and location are improved
  without silently clearing the pre-existing review flag.
- Blue Ridge Defense Works: current operating presence is not corroborated.
- Bihrle: federal records support address/history; current operator pages failed TLS
  retrieval. Indexed text alone is not used to certify current activity.
- Liquid Robotics: Herndon contact persists alongside the announced Maryland relocation.
- PerimeterAI: Haymarket and development role are supported; operating address unresolved.
- Mare Custos: official Alliance announcement supports Norfolk presence; current exact
  IDEA Lab occupancy needs confirmation.
- Trident: public contact page lists the facility but also contains unrelated spam;
  seek clean corroboration before accepting that source as current verified evidence.

## Airport searches

The eight airports retain the official state-directory website fallback because a
reliable current airport-specific operator website was not established: Chase City,
Lake Anna, Lake Country, Mc Laughlin Seaplane Base, New London, New Market, Smith Mountain
Lake and Tangier Island. Existing airport-specific FAA sources remain available.

Seven receive current published manager/sponsor contacts from the Virginia DOAV
airport-sponsor table. Mc Laughlin is a seaplane base and is not relabeled an airport.
Sponsor mailing addresses are not substituted for FAA airport reference coordinates.

The old `smlairport.com` domain was rejected because its current content describes an
unrelated Alpine airport with placeholder details. The former Lake Country airport
domain was not reliably accessible; Clarksville's current facilities listing is useful
corroboration but not a dedicated airport website. Tenants and flight schools are not
silently substituted for airport operators.

## Follow-up needed

Ask each unresolved operator for a publishable operating address (or confirmation that
only a locality should be shown), current capability/program status and a preferred
public contact. Ask localities which department operates their UAS program and whether
the named agency received the 2026 replacement award. Contact is not initiated by this
research pass, and no non-public address or personal information is inferred.

## Deployment safeguards

The new correction and review manifests are included in the deployment build.
Asset-specific findings are saved with review comments, including limitations that
prevent a desk review from implying a precise pin or a currently open program.
Repeated corrections and reviews are idempotent. Five older location corrections
also recognize the exact new catalog values on a fresh installation, so replaying
the older steps does not create false conflicts before the latest step runs.
Staff edits and explicit unverification still take precedence.

Validation: 241 backend tests passed, followed by 59 focused tests covering the final
deployment/data safeguards. The complete catalog passes generator validation, Django
reports no configuration issues, and repeat local application produces no changes or
conflicts. Changed detail pages and the map-data response passed local smoke checks.
