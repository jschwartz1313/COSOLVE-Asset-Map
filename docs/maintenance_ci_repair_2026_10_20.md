# CI GIS dependency repair — October 20, 2026

The reviewed nineteen-file maintenance candidate was pushed once at
`e7c9c491aebcb06082db449cbada66f2244ba544` with `[skip render]`.
Its isolated Mac checks passed 374 backend, 30 frontend and 145 browser checks
with one expected skip. No deployment was requested.

[GitHub CI run 39450863294](https://github.com/jschwartz1313/COSOLVE-Asset-Map/actions/runs/39450863294)
failed after 816.817 seconds in its backend step. The 357 reported cases include
three module-import error placeholders; 354 actual cases produced no assertion
failure. All three imports fail because GDAL is unavailable to GeoDjango:
`test_drone_airspace_layers`, `test_layer_freshness` and `test_maap_integration`.
The later frontend/browser steps were skipped, so that run is not a CI pass.

This follow-up explicitly installs `binutils libproj-dev gdal-bin` on the
ephemeral Ubuntu CI runner, following the
[Django 5.2 installation guidance](https://docs.djangoproject.com/en/5.2/ref/contrib/gis/install/geolibs/).
An early GDAL/GEOS import and point-construction check fails before the long test
suite if the native runtime is unavailable. Workflow permissions, PostgreSQL
service settings, application code, deployment configuration and access remain
unchanged. No test is skipped or weakened.

The exact preflight passes against the existing Mac native runtime. The workflow
structure and diff are validated locally; Ubuntu package installation and the
complete PostgreSQL/browser CI result require the new pushed run. The existing
application tests need no repeat for this workflow-only change. Preserve the
first failed log at `tmp/maintenance-2026-10-20/github-ci-failed.log` and record the
follow-up SHA/CI outcome in the local October 20 delivery receipt.

Deployment and complete hosted QA remain pending supported Chrome control on
the connected Mac. This follow-up also uses `[skip render]`.
