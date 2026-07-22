# Deployment and operations

Deploy with Python 3.12+, PostgreSQL, Gunicorn, and a reverse proxy or managed Django platform. Configure all values from `.env.example`; do not place credentials in the repository.

The checked-in `render.yaml` and `build.sh` define a Render web service and PostgreSQL database. Create a Blueprint from the repository to provision both. The Blueprint keeps the site behind login and prompts for `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD`. These values create the first administrator only; later builds never reset an existing account or password.

The Blueprint uses Render's free service and database plans for evaluation. The free PostgreSQL database expires after 30 days and has no backups. Upgrade or replace the database before coworkers perform work that must be retained; the repository intentionally does not select a paid plan automatically.

The build initializes the source-backed catalog only if the asset table is empty. Normal redeployments therefore preserve every staff edit. To intentionally refresh records from the checked-in catalog, back up the database, review the catalog diff, and run `python manage.py seed_real_data --prune` manually.

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Required production choices include a strong `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, PostgreSQL `DATABASE_URL`, HTTPS, and a basemap provider whose terms cover expected traffic. Run migrations as a release step before switching application traffic. Back up the database before schema changes.

Render's `RENDER_EXTERNAL_HOSTNAME` and Railway's `RAILWAY_PUBLIC_DOMAIN` are accepted automatically in production. A custom domain can be added through `DJANGO_ALLOWED_HOSTS`. The included `Procfile` supplies a portable Gunicorn start command for hosts that recognize it.

Rollback procedure:

1. Remove the failing release from traffic.
2. Restore the preceding application image or checkout.
3. Reverse only migrations documented as reversible; otherwise restore the pre-release database backup.
4. Run `/health/`, a public API request, and the browser smoke test before restoring traffic.

Operational checks should cover database backups and restore drills, stale-record review, dependency updates, failed login monitoring, static-file availability, API errors, and staff account offboarding.

`STALE_VERIFICATION_DAYS` controls the review interval used by the staff data-quality dashboard. It defaults to 180 days.
