# COSOLVE Unmanned Systems Asset Map Viewer

[![CI](https://github.com/jschwartz1313/COSOLVE-Asset-Map/actions/workflows/ci.yml/badge.svg)](https://github.com/jschwartz1313/COSOLVE-Asset-Map/actions/workflows/ci.yml)

A standalone Django and Leaflet application for maintaining, comparing, and exploring publicly releasable unmanned-systems ecosystem assets. The repository implements the database-backed MVP plus selected Phase 3 and Phase 4 capabilities from the controlling technical specification.

The checked-in catalog contains source-backed, publicly documented Virginia records. Military and federal locations are deliberately generalized and exclude operational detail. A separate demo-seed command remains available only for test and interface development.

## Included

- Normalized assets, taxonomy, sources, regions, and relationships
- Source-backed listing, review, verification, publication, and archive lifecycle
- Field-level revision history and staff rollback for assets, sources, and relationships
- Staff administration with guarded bulk publish and archive actions
- Public-safe JSON and GeoJSON APIs with server-side filtering
- Deployment-level regional scoping that can publish Hampton Roads while retaining statewide staff data
- Synchronized Leaflet map and result directory with URL-backed state
- Accessible non-map directory and public asset profiles
- Round-trip CSV review workflow with complete editable fields and multiple sources
- Regional comparison, public data methodology, and source-verification views
- Source-backed relationships connecting organizations, facilities, and programs
- Staff data-quality dashboard for stale, unsourced, unlocated, and unreviewed records
- Coverage metrics by region and asset type, saved views, and relationship explorer
- Password recovery, login throttling, optional TOTP MFA, and optional OIDC organization sign-in
- Public correction and addition submissions routed to an editor-only review queue
- 232 source-backed Virginia records spanning public-use airports, research, workforce, companies, infrastructure, programs, and generalized defense assets
- Backend, frontend state, security-boundary, and import tests

## Local setup

Python 3.12 or newer is required.

```bash
cd ~/Desktop/cosolve-uxs-map
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python manage.py migrate
python manage.py setup_staff_roles
python manage.py seed_real_data --replace-demo --prune
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Staff administration is at `http://127.0.0.1:8000/admin/`, CSV import is at `http://127.0.0.1:8000/admin/imports/preview/`, and the staff data-quality dashboard is at `http://127.0.0.1:8000/admin/imports/data-quality/`.

The role command creates cumulative `COSOLVE Viewer`, `COSOLVE Reviewer`, `COSOLVE Editor`, `COSOLVE Publisher`, and `COSOLVE Administrator` groups. Create staff accounts under **Users and roles**, enable staff status, and assign the narrowest appropriate group. Reviewers can correct and verify existing assets and sources. Editors can additionally maintain the catalog structure, import and export records, and review public update submissions. Publishers can publish and archive records. Administrators inherit all catalog capabilities and can create and maintain staff accounts without receiving Django superuser status. Website roles never grant access to the source repository or hosting account.

SQLite is the no-setup local default. Set `DATABASE_URL` to a PostgreSQL URL to use PostgreSQL. The current MVP stores WGS84 latitude and longitude in portable decimal columns; Phase 4 introduces PostGIS geometry and spatial indexes.

For Render, the repository includes a Blueprint and build script that provision PostgreSQL, apply migrations, collect static files, configure staff roles, and initialize the source-backed catalog only when the database is empty. Later deployments preserve changes made by staff. The Blueprint prompts for the initial administrator username, email, and password. Production startup fails if its database, host, secret key, or initial administrator settings are missing.

Both Render Blueprints are initially configured as Hampton Roads releases. Public pages and APIs expose only Hampton Roads records, while authenticated staff administration continues to include the complete statewide working catalog. The evaluation Blueprint remains login-protected. The production Blueprint makes the public viewer available without a site-wide login while keeping `/admin/` protected.

The default `render.yaml` is an evaluation environment. Its free PostgreSQL database expires after 30 days and has no backups. Use `render.production.yaml` for the public Hampton Roads launch and durable coworker use; it selects paid web and database services and adds a daily source-monitoring job. Cron jobs on Render have a minimum monthly charge. Configure database exports or another backup destination before treating the hosted database as the system of record.

`PUBLIC_REGION_SLUG=hampton-roads` enforces the release boundary in server-side queries, public APIs, detail pages, relationships, and navigation. Remove `PUBLIC_REGION_SLUG`, set `PUBLIC_SCOPE_NAME=Virginia`, and restore the statewide map defaults when the statewide viewer is ready for release.

Password recovery requires SMTP settings. Organization sign-in is enabled only when all three OIDC settings are present, and it accepts only active users that an administrator has already created. TOTP and recovery codes are available under **Account security**. In **Users and roles**, the **Send password setup or reset email** action provides the normal invitation workflow.

The production Blueprint intentionally leaves the basemap URL and attribution for deployment-time configuration. Use a tile service whose capacity and terms cover the expected audience; the public OpenStreetMap tile endpoint remains a local-development fallback.

The real-data catalog is generated by `scripts/build_real_asset_catalog.py`. It combines current FAA public-airport data with a curated public-source catalog and writes `data/virginia_real_assets.json`. Rebuild and review the generated diff before reseeding when source data changes.

Running `seed_real_data --prune` manually updates catalog-managed records from the checked-in file and can overwrite staff edits. Hosted builds use `--only-if-empty` so this never happens automatically.

## Quality checks

```bash
python manage.py makemigrations --check
python manage.py check
python manage.py test tests.backend
node --test tests/frontend/*.test.mjs
npm run test:browser
ruff check apps config scripts tests manage.py
python manage.py collectstatic --noinput
```

## Public API

- `GET /api/assets/`
- `GET /api/assets.geojson`
- `GET /api/assets/{slug}/`
- `GET /api/filters/`
- `GET /api/regions/{slug}/summary/`
- `GET /health/`

Asset endpoints accept `record_type`, `category`, `domain`, `capability`, `mission`, `region`, and `q`. Repeat values within one facet for OR matching; separate facets are combined with AND logic.

Example:

```text
/api/assets.geojson?category=test-and-operational-environments&domain=maritime-surface-systems&region=hampton-roads&q=test
```

## Documentation

- [Data dictionary](docs/data_dictionary.md)
- [Real-data sources and methodology](docs/data_sources.md)
- [CSV import guide](docs/import_guide.md)
- [Security and publication](docs/security_and_publication.md)
- [Deployment and operations](docs/deployment.md)
- [Browser smoke-test checklist](docs/smoke_test.md)

## Decisions required before production

- Public versus partner-only dataset boundaries
- Production basemap provider and usage terms
- Hosting platform, domain, and managed database
- Sensitive-location generalization policy
- Partner roles and access rules
- Final taxonomy ownership and change control
- External geocoding provider, if any
- Contact and personal-information retention policy

The public OpenStreetMap tile URL is suitable only for development. Configure a production tile provider before launch.
