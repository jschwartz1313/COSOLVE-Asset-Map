# Public names, useful contacts and location context

Review date: September 6, 2026.

## Scope and outcome

- 153 existing catalog records have explicit location context: 64 airports, 69 institution-level entries, and 20 selected organizations/facilities/programs.
- All 64 airport records have readable public names and FAA identifier aliases. Nine additional research/facility records have searchable acronyms or alternate public names.
- 12 selected profiles have improved contact routes or contact descriptions; nine additional profiles have source-linked testing and access details.
- The catalog still contains 527 records. This is a profile-quality pass, not an asset-count expansion or blanket editorial verification.
- Existing asset identifiers, canonical catalog names and public URLs remain unchanged. Historical names and FAA abbreviations remain searchable.

## Search behavior

Unquoted words can match different public fields, taxonomy labels, public source titles, or public related-asset names. Every word must match. Word order does not matter. Quoted phrases remain literal. Common drone/UAS/uncrewed terms and test/testing are expanded for unquoted searches.

Exact public/canonical names rank first, then exact aliases, name prefixes, and incidental matches. For example, `ORF` places Norfolk International Airport first, but can also find other Norfolk mentions. The directory defaults to Best match when searching; its existing alphabetical, region and type sorts remain available. Private source titles and private/out-of-release related assets do not participate.

Search is bounded to 500 characters and 16 distinct terms. An excessive query returns no results, not misleading partially filtered results.

## Contact improvements

The selected records are VMASC, VISA, ODU MASTS, H2P Solution, Xelevate Leesburg, MITRE National Range, Virginia Smart Roads, Virginia Automated Corridors, NASA FDRF, Harrowgate Drone Park, Textron's Blackstone Aerosonde center, and Newport News Shipbuilding.

Contact descriptions distinguish research inquiries, range reservations, corporate business inquiries and supplier support. A supplier or corporate number is not labeled as a direct booking line. Dedicated university-institute sites were followed from ODU's own research enterprise pages.

## Testing facts and limits

| Record | What the evidence supports | Important limit |
| --- | --- | --- |
| Kentland laboratory | 300 x 70 ft airstrip; nearby hangar | The larger farm acreage is not a flight authorization boundary. |
| Xelevate Leesburg | 66-acre campus and operator-described aircraft scope | Luray's larger range is a separate site. |
| MITRE National Range | Operator-described facilities and research/reservation contacts in its 2024 fact sheet | No confirmed public site address, mapped airspace boundary or runway length. |
| ODU MASTS | Waterfront research infrastructure, dock, utilities and crane | Crane rating does not define allowable vessel size. |
| Harrowgate Drone Park | Shared field and recreational-use conditions in county material | Specific description is archived, not confirmation of current availability. |
| Virginia Smart Roads | Controlled-road environments and operator-coordinated testing | Road mileage is not an aircraft runway length. |
| Virginia Automated Corridors | Multi-site automated-vehicle road network | Not a single drone airfield. |
| NASA FDRF | Wind-tunnel research scope and facility area | Building area is not chamber size; confirm commissioning and scheduling. |
| Textron Blackstone | Aerosonde production, testing and training facility | No unrestricted public testing or flight boundary is established. |

Primary evidence is linked in each record and in `data/profile_improvements_2026_09_06.json`. Examples: [Virginia Tech KEAS](https://autonomyandrobotics.centers.vt.edu/groups/keas.html), [Xelevate Leesburg](https://xelevateus.com/leesburg-virginia/), [MITRE range fact sheet](https://www.mitre.org/sites/default/files/2024-07/PR-24-2208-MITRE-National-Range.pdf), [ODU MASTS](https://visaatodu.org/masts/), [VTTI corridors](https://www.vtti.vt.edu/facilities/vac.html), [NASA FDRF](https://www.nasa.gov/directorates/armd/flight-dynamics-research-facility/), [Textron Blackstone](https://www.textronsystems.com/our-company/news-events/articles/inside-ts/aerosonde-uas-center-excellence).

## Location decisions

- Airport points remain their existing FAA reference coordinates, not terminal doors or drone launch points. Institution-level points identify the listed institution, not every campus or a particular UxS laboratory. These classifications retain the September 4 location-evidence review date; they are not presented as 133 newly surveyed positions.
- The AUVSI Ridge and Valley chapter and Virginia Automated Corridors remain in the inventory without a single pin. A postal address or one city-center point does not adequately represent either regional network.
- MITRE's Orange County range, H2P's Fairfax location and Magothy's Herndon office remain locality-level. Magothy's published Maryland testing facilities are not assigned to the Virginia office pin.
- The NASA FDRF and VISA records explicitly distinguish center/coordination addresses from individual research buildings. No new precise laboratory or military operating positions were inferred.
- Selected manufacturing records distinguish production sites from headquarters: Textron Blackstone, Fulcrum Newport News, Micron Manassas, Volvo New River Valley, UVision Stafford and Newport News Shipbuilding.

No point was promoted from approximate/locality to exact in this pass. Obtaining more exact operating addresses remains a separate operator-confirmation task.

## Maintenance and deployment

New public-name, alias and location-evidence fields are available to existing authorized editors and included in record history and CSV round trips. Staff CSV exports preserve the canonical `name` and include the readable `display_name`, avoiding duplicate creation on reimport. The public map and its exports use the readable name.

Location evidence that ages out enters the existing staff review queue. The migration adds fields without renaming or removing records. Dated corrections are applied in the normal deployment process only where catalog baselines still match. Staff edits, publication decisions and hidden/rejected sources are preserved. Reapplying the same corrections is a no-op.

The implementation adds no new map panels, theme changes or comparison interface. Context appears inside existing popups, profiles and directory entries, with precision labels retained.
