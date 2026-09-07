# Airport Website Review - September 6, 2026

Reviewed all 64 public-airport records. Previously every primary website pointed to the
same DOAV airport directory.

## Changes

- Replaced 54 primary links with airport websites or relevant official operator pages.
- Updated their public contact links to those same airport/operator entry points.
- Added each destination as a source while retaining FAA and DOAV evidence.
- Corrected retired URLs, including Accomack, Brookneal-Campbell, Front Royal,
  Franklin, Lee County, New Kent, Tappahannock-Essex, Virginia Tech, and Williamsburg.
- Followed Norfolk's official redirect to flyorf.com and Louisa's redirect to its county page.
- Preserved asset verification status, source-review status, contacts, coordinates,
  classifications, and all unrelated records. Website review is not operational verification.

The [DOAV directory](https://doav.virginia.gov/airport-directory/) was matched by FAA identifier,
not just similar airport names. Destination pages were inspected; an HTTP 200 response alone
was not accepted as proof of a relevant website. Airport sites that block automated checks
were cross-checked against the public directory and indexed official-page content.

## Exceptions

The 10 records below retain their existing government reference links and specific FAA source
records. A suitable current airport website was not confirmed. This is not a claim that no
website exists or that the airport is closed.

| Airport | Identifier | Outstanding issue |
| --- | --- | --- |
| Chase City Municipal | CXE | Town information found, but no dedicated airport page confirmed. |
| Falwell | W24 | Historical operator references must not be confused with its LYH operations. |
| Lake Anna | 7W4 | No suitable operator site confirmed. |
| Lake Country Regional | W63 | Published domain displays a hosting placeholder. |
| Mc Laughlin Seaplane Base | 2G6 | No suitable operator site confirmed. |
| Middle Peninsula Regional | FYJ | Published domain responds with an invalid-site message. |
| New London | W90 | Published domain redirects to an error page. |
| New Market | 8W2 | Directory operator link leads to a separate balloon business. |
| Smith Mountain Lake | W91 | Flight-school site found; airport-operator ownership not established. |
| Tangier Island | TGI | No suitable airport-specific operator page confirmed. |

Campbell Field's operator website is reachable over HTTP only and contains historical material.
It identifies the facility but must not be used to infer current availability or operating rules.
Ingalls Field uses Bath County's airport-authority page because the former airport domain now
contains unrelated travel content. Bridgewater uses its operator's facility/visit page. Brunswick
uses the county's aviation page covering its two airports, not an invented standalone site.

## Deployment

The checked-in catalog and rebuild script retain these links for new installations. Render's
build applies the dated correction manifest to existing catalog-managed records only when both
old URLs still match. Staff-managed records, changed URLs, and rejected or hidden destination
sources are preserved. Repeated deployments do not duplicate sources or review-log entries.

The full changes and outstanding decisions are recorded in
`data/airport_website_corrections_2026_09_06.json`.
