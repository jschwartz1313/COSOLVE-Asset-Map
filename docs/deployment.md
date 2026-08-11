# Deployment and operations

Deploy with Python 3.12+, PostgreSQL, Gunicorn, and a reverse proxy or managed Django platform. Configure all values from `.env.example`; do not place credentials in the repository.

The checked-in `render.yaml` and `build.sh` define a free Render evaluation environment. Create a Blueprint from the repository to provision it. The Blueprint keeps the site behind login and prompts for `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD`. These values create the first administrator only; later builds never reset an existing account or password.

If the initial administrator credentials are lost on a free service without shell access,
set the three administrator variables to the desired recovery credentials, add
`DJANGO_SUPERUSER_RESET=true`, and choose **Save, rebuild, and deploy**. After confirming
the recovered account can sign in, remove `DJANGO_SUPERUSER_RESET` and deploy again.
Never leave the recovery switch enabled during normal operation.

The Blueprint uses Render's free service and database plans for evaluation. The free PostgreSQL database expires after 30 days and has no backups. Upgrade or replace the database before coworkers perform work that must be retained; the repository intentionally does not select a paid plan automatically.

For durable use, create the Blueprint from `render.production.yaml`. It selects a paid web service and non-expiring database, prompts for a production basemap and SMTP configuration, and adds a daily source-monitor cron job. The production viewer is public, but staff and administrative routes remain authenticated. Render cron jobs are billed separately with a minimum monthly charge. Add a scheduled database export or other tested backup before making the hosted database the system of record.

## Statewide release scope

Both Blueprints leave `PUBLIC_REGION_SLUG` empty and set `PUBLIC_SCOPE_NAME=Virginia`. Public map, directory, detail, relationship, export, and API queries can therefore return published records across the Commonwealth. The default map center and zoom frame the complete state.

To create a Hampton Roads-only release:

1. Set `PUBLIC_REGION_SLUG=hampton-roads`.
2. Set `PUBLIC_SCOPE_NAME=Hampton Roads`.
3. Set `DEFAULT_MAP_LAT=36.95`, `DEFAULT_MAP_LON=-76.35`, and `DEFAULT_MAP_ZOOM=9`.
4. Deploy and run the public API and browser smoke tests.

Setting `PUBLIC_REGION_SLUG` to another active region creates a different regional release without copying the application or database. A separate database is needed only when contractual or confidentiality requirements prohibit storing statewide working records in the same environment.

The build adds missing catalog records, applies conservative profile enrichment, applies newly checked-in editorial review decisions once, creates baseline history, and leaves later staff review decisions intact. Normal redeployments therefore preserve coworker edits and any later decision to unverify a record. To intentionally refresh catalog-managed fields from the checked-in catalog, back up the database, review the catalog diff, and run `python manage.py seed_real_data --prune` manually.

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Required production choices include a strong `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, PostgreSQL `DATABASE_URL`, HTTPS, SMTP, and a basemap provider whose terms cover expected traffic. Run migrations as a release step before switching application traffic. Back up the database before schema changes.

Set `OIDC_SERVER_URL`, `OIDC_CLIENT_ID`, and `OIDC_CLIENT_SECRET` together to enable organization sign-in. The provider must send a verified email that matches an active user created by an administrator. Leave all three unset to use password and TOTP authentication only.

Render's `RENDER_EXTERNAL_HOSTNAME` and Railway's `RAILWAY_PUBLIC_DOMAIN` are accepted automatically in production. A custom domain can be added through `DJANGO_ALLOWED_HOSTS`. The included `Procfile` supplies a portable Gunicorn start command for hosts that recognize it.

Rollback procedure:

1. Remove the failing release from traffic.
2. Restore the preceding application image or checkout.
3. Reverse only migrations documented as reversible; otherwise restore the pre-release database backup.
4. Run `/health/`, a public API request, and the browser smoke test before restoring traffic.

Operational checks should cover database backups and restore drills, stale-record review, dependency updates, failed login monitoring, static-file availability, API errors, and staff account offboarding.

`STALE_VERIFICATION_DAYS` controls the review interval used by the staff data-quality dashboard. It defaults to 180 days.
