# COSOLVE Unmanned Systems Asset Map Viewer

A standalone Django and Leaflet application for maintaining and exploring publicly releasable unmanned-systems ecosystem assets. This repository implements Phases 0 through 2 of the controlling technical specification.

All bundled records are clearly fictional development fixtures. They do not make factual claims about real organizations, facilities, programs, or defense activities.

## Included

- Normalized assets, taxonomy, sources, regions, and relationships
- Draft, review, verification, publication, and archive lifecycle
- Staff administration with guarded bulk publish and archive actions
- Public-safe JSON and GeoJSON APIs with server-side filtering
- Synchronized Leaflet map and result directory with URL-backed state
- Accessible non-map directory and public asset profiles
- CSV validation preview, draft import, and filtered export
- Twenty fictional Virginia demo records
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
python manage.py seed_demo_data
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Staff administration is at `http://127.0.0.1:8000/admin/` and CSV import is at `http://127.0.0.1:8000/admin/imports/preview/`.

SQLite is the no-setup local default. Set `DATABASE_URL` to a PostgreSQL URL to use PostgreSQL. The current MVP stores WGS84 latitude and longitude in portable decimal columns; Phase 4 introduces PostGIS geometry and spatial indexes.

## Quality checks

```bash
python manage.py makemigrations --check
python manage.py check
python manage.py test tests.backend
node --test tests/frontend/*.test.mjs
ruff check apps config tests manage.py
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

