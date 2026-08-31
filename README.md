# COSOLVE Unmanned Systems Asset Map Viewer

[![CI](https://github.com/jschwartz1313/COSOLVE-Asset-Map/actions/workflows/ci.yml/badge.svg)](https://github.com/jschwartz1313/COSOLVE-Asset-Map/actions/workflows/ci.yml)

A standalone Django and Leaflet application for maintaining, comparing, and exploring publicly releasable unmanned-systems ecosystem assets. The repository implements the database-backed MVP plus selected Phase 3 and Phase 4 capabilities from the controlling technical specification.

The checked-in catalog contains source-backed, publicly documented Virginia records. Military and federal locations are deliberately generalized and exclude operational detail. A separate demo-seed command remains available only for test and interface development.

## Included

- Normalized assets, taxonomy, sources, regions, and relationships
- Source-backed listing, review, verification, publication, and archive lifecycle
- Field-level revision history and staff rollback for assets, sources, and relationships
- Staff administration with assignments, due dates, internal comments, and guarded bulk actions
- Public-safe JSON and GeoJSON APIs with server-side filtering
- Deployment-level regional scoping that can publish Hampton Roads while retaining statewide staff data
- Synchronized Leaflet map and result directory with URL-backed state
- Four persistent presentation modes: the current interface, a geometry-matched dark mode, and dark or light image-led showcase modes
- Saved rectangle and polygon analyses that reopen with the same geometry and selected records
- Accessible non-map directory and public asset profiles
- Source-dated current activity, collaboration routes, and economic-development site-readiness fields
- Round-trip CSV review workflow with complete editable fields and multiple sources
- Regional comparison with inventory mix, leading capabilities, and data-confidence measures
- Source-backed relationships connecting organizations, facilities, and programs
- Staff review workspace with coverage gaps, duplicate candidates, source health, and workload
- Consolidated audit log for asset, source, reviewer-comment, and duplicate-decision history
- Filter- and analysis-aware CSV export plus a printable map and asset report
- Coverage metrics by region and asset type, saved views, and relationship explorer
- Optional planning layer for potential Maritime Prosperity Zone census tracts, explicitly
  distinguished from any future federal designations
- Optional FAA-recorded private-use heliport reference layer with access and authorization warnings
- Password recovery, login throttling, optional TOTP MFA, and optional OIDC organization sign-in
- Public correction and addition submissions routed to an editor-only review queue
- 497 source-backed Virginia records spanning public-use airports, relevant higher education, research, workforce, companies, infrastructure, programs, and generalized defense assets
- A dedicated `Manufacturing facilities` strategic category covering 21 documented Virginia production, assembly, fabrication, and component-manufacturing sites
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

The staff **Review workspace** at `/admin/imports/data-quality/` is the operational queue. It shows assigned, overdue, and unassigned reviews; source-link health; documented coverage gaps; and likely duplicate pairs. Asset records hold the reviewer, priority, due date, and internal comment thread. The Assets admin provides bulk assignment and scheduling actions, while the audit log records human changes. Run `python manage.py scan_asset_duplicates` to refresh duplicate candidates and `python manage.py check_source_links --all` to refresh source health manually.

SQLite is the no-setup local default. Set `DATABASE_URL` to a PostgreSQL URL to use PostgreSQL. The current MVP stores WGS84 latitude and longitude in portable decimal columns; Phase 4 introduces PostGIS geometry and spatial indexes.

For Render, the repository includes a Blueprint and build script that provision PostgreSQL, apply migrations, collect static files, configure staff roles, and initialize the source-backed catalog only when the database is empty. Later deployments preserve changes made by staff. The Blueprint prompts for the initial administrator username, email, and password. Production startup fails if its database, host, secret key, or initial administrator settings are missing.

Both Render Blueprints are configured as statewide Virginia releases. Public pages and APIs expose the complete published Virginia catalog. The evaluation Blueprint remains login-protected. The production Blueprint makes the public viewer available without a site-wide login while keeping `/admin/` protected.

The default `render.yaml` is an evaluation environment. Its free PostgreSQL database expires after 30 days and has no backups. Use `render.production.yaml` for the public statewide launch and durable coworker use; it selects paid web and database services and adds a daily source-monitoring job. Cron jobs on Render have a minimum monthly charge. Configure database exports or another backup destination before treating the hosted database as the system of record.

The statewide deployment leaves `PUBLIC_REGION_SLUG` empty and sets `PUBLIC_SCOPE_NAME=Virginia`. Setting `PUBLIC_REGION_SLUG=hampton-roads` creates a regional release boundary while retaining the complete statewide catalog for staff administration.

Password recovery requires SMTP settings. Organization sign-in is enabled only when all three OIDC settings are present, and it accepts only active users that an administrator has already created. TOTP and recovery codes are available under **Account security**. In **Users and roles**, the **Send password setup or reset email** action provides the normal invitation workflow.

The production Blueprint intentionally leaves the basemap URL and attribution for deployment-time configuration. Use a tile service whose capacity and terms cover the expected audience; the public OpenStreetMap tile endpoint remains a local-development fallback.

The real-data catalog is generated by `scripts/build_real_asset_catalog.py`. It combines current FAA public-airport data, NCES institution contact data, Virginia airport sponsor contacts, and a curated public-source catalog. `scripts/build_contact_enrichment.py` follows conservative same-host public contact routes from those sources. Rebuild, regenerate contact enrichment, rebuild once more, and review the generated diff before reseeding when source data changes.

Running `seed_real_data --prune` manually updates catalog-managed records from the checked-in file and can overwrite staff edits. Hosted builds use `--add-missing`, which inserts new catalog records without replacing existing staff edits.

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
