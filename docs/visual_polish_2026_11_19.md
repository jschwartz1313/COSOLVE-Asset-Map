# Standard Light Visual Polish

No additional appearance modes, landing pages or catalog reclassification.

- Grey is the default when a CARTO key or custom light-tile provider is configured.
  Existing saved basemap choices win. Without configuration, or after an initial
  grey-tile failure, Street remains the fallback; the picker follows that fallback.
- Consistent 42px form controls, 14px control text, clearer names, quieter secondary
  copy, neutral alternating rows and existing single directory borders.
- Map result selections and marker halos stay connected, including keyboard use,
  clustering and icon refreshes. Reduced-motion preferences disable animation.
- Profile photographs are deliberately selective. No directory imagery or stock art.

## Images and Editorial Controls

Two actual NASA facility photographs are bundled at 1024px. Sources, captions,
credits and NASA's published editorial-reuse guidance are recorded in
`data/profile_photos_2026_11_19.json`. This is not individual NASA approval,
endorsement, current equipment certification or permission to access a facility.

`SiteDiagram.image_kind` distinguishes existing diagrams from profile photographs.
Only approved photos appear in the profile overview. Staff can replace, unapprove
or delete them through the existing asset editor's Site images section. Existing
diagrams remain in Supporting details. The import's historical marker prevents
subsequent deployments from undoing those staff choices, including deletion.

The command does not change asset verification or review dates. The separate
unpublished Virginia catalog edits are not part of this release.

## Verification

Coverage includes saved basemaps, provider fallback, selection synchronization,
reduced motion, approval/deletion preservation and image loading. Responsive checks
cover 320px, 390px, 768px, 1440px and short landscape map controls. Full regression
and hosted smoke checks are required before release completion.

Local release checks passed: 591 backend tests, 40 frontend tests, and 311 browser
checks (one desktop-inapplicable mobile-drawer case skipped). Production settings,
migrations, Python lint and static-file collection also passed. Screenshots were
visually inspected, including real grey-provider tiles and the 320px staff header.
