# Deployment and operations

Deploy with Python 3.12+, PostgreSQL, Gunicorn, and a reverse proxy or managed Django platform. Configure all values from `.env.example`; do not place credentials in the repository.

The checked-in `render.yaml` matches the existing deployment: a free Render web service and a paid `basic-256mb` PostgreSQL database. The database was already on that paid plan when checked on September 21, 2026; this configuration does not upgrade the existing service. Creating a new Blueprint will incur the database charge. Both Blueprints keep the site behind login and prompt for `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and `DJANGO_SUPERUSER_PASSWORD`. Automated releases create the first administrator only and never reset an existing account or password.

Use the website's password-reset email once delivery is configured, or have another administrator reset the account. For emergency recovery, a trusted operator can run `python manage.py changepassword USERNAME` against the correct database. The `ensure_admin_user` command still supports an explicit recovery when invoked manually with `DJANGO_SUPERUSER_RESET=true`, but automated releases pass `--skip-recovery` and ignore that flag. On a free service without shell access, use a trusted local environment with the database's external connection URL, never a URL committed to GitHub. Remove temporary recovery variables after use.

The free web service can sleep when idle and does not support dedicated pre-deploy commands or outbound SMTP on ports 25, 465, or 587. Do not downgrade the database to the free plan: free PostgreSQL expires after 30 days and has no managed recovery.

The separate `render.production.yaml` is a template for a paid web service and database, with a daily source-monitor cron job and a dedicated pre-deploy step. It creates separate resources; do not apply it to upgrade the current service unless a separate environment is intended. Cron jobs are billed separately. To upgrade the existing service, approve its costs, change its plan, set the pre-deploy command to `python manage.py release_database`, and use the Gunicorn start command shown below. Both templates and production settings default to private access. Set `REQUIRE_SITE_LOGIN=false` only for an explicitly approved public launch.

## Build and release safety

`build.sh` only installs dependencies and collects static files. It does not migrate, seed, change accounts, or write to the database. A failed build therefore leaves the live database untouched.

`release_database` runs `release.sh` to perform migrations, conservative catalog updates, staff-role setup, history initialization, and first-administrator creation. It records success in the database against Render's commit SHA, so waking or restarting the same version does not repeat the data updates. A PostgreSQL advisory lock serializes overlapping releases. Failed releases are not recorded and can be retried. The paid template runs this command in Render's pre-deploy phase. The current free service uses `bash start.sh`, which runs it after a successful build and only starts Gunicorn on success. A new release can take several minutes on the free instance; an ordinary wake-up only checks its completion record. Render's own idle-start delay still applies.

For intentional reapplication of the same version, run `python manage.py release_database --force`. Without `RENDER_GIT_COMMIT` (for example, a manual local deployment), the command runs every time without storing a version marker. Do not run `release.sh` directly against production because that bypasses release locking and completion tracking.

Release steps are not a single transaction and code rollback does not undo migrations or data corrections. Keep migrations backward-compatible with the previous running version and export a backup before schema or bulk-data changes. All automated release jobs must use the locking command.

## Statewide release scope

Both Blueprints leave `PUBLIC_REGION_SLUG` empty and set `PUBLIC_SCOPE_NAME=Virginia`. Public map, directory, detail, relationship, export, and API queries can therefore return published records across the Commonwealth. The default map center and zoom frame the complete state.

To create a Hampton Roads-only release:

1. Set `PUBLIC_REGION_SLUG=hampton-roads`.
2. Set `PUBLIC_SCOPE_NAME=Hampton Roads`.
3. Set `DEFAULT_MAP_LAT=36.95`, `DEFAULT_MAP_LON=-76.35`, and `DEFAULT_MAP_ZOOM=9`.
4. Deploy and run the public API and browser smoke tests.

Setting `PUBLIC_REGION_SLUG` to another active region creates a different regional release without copying the application or database. A separate database is needed only when contractual or confidentiality requirements prohibit storing statewide working records in the same environment.

The release adds missing catalog records, applies conservative profile enrichment, applies newly checked-in editorial review decisions once, creates baseline history, and leaves later staff review decisions intact. Normal redeployments therefore preserve coworker edits and any later decision to unverify a record. To intentionally refresh catalog-managed fields from the checked-in catalog, back up the database, review the catalog diff, and run `python manage.py seed_real_data --prune` manually.

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
bash build.sh
python manage.py release_database
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Required production choices include a strong `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, PostgreSQL `DATABASE_URL`, HTTPS, a working email provider, and a basemap provider whose terms cover expected traffic. Run migrations as a release step before switching application traffic. Back up the database before schema changes.

## Password-reset delivery

As of September 21, the hosted site has no mail-provider configuration. The reset page now explains that delivery is unavailable rather than promising an email or raising a server error. Signing in and existing passwords are unaffected. No `DJANGO_SUPERUSER_RESET` variable remains on the hosted service.

Choose an approved sender service and verify a sender/domain with its owner. Configure `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `EMAIL_USE_TLS` for SMTP on a supported hosting plan. `EMAIL_TIMEOUT` defaults to ten seconds. The free Render web service blocks the usual SMTP ports; staying on that plan requires a supported HTTPS email backend and its provider credentials instead. `EMAIL_BACKEND` is configurable in production, but a provider-specific backend must be installed and configured before enabling it.

Use `python manage.py sendtestemail jake@letscosolve.com` only after delivery is configured. Provider acceptance is not proof of inbox delivery: confirm receipt, then request a real password-reset email, open its HTTPS link, and verify expiration/single-use behavior. Do not log reset links or send test account secrets. Automated tests cover generating an email, resetting through its link, rejecting reuse, and handling missing configuration for both known and unknown addresses.

## Backups and restore drills

The current database's **Recovery** page was checked on September 21, 2026: point-in-time recovery covers the last **three days**. This is a rolling recovery window, not an indefinite archive. Render retains logical exports for at least seven days. See [Render's backup documentation](https://render.com/docs/postgresql-backups).

Before schema changes or bulk edits, use **Database > Recovery > Create export** and download the completed archive to a private location outside the repository. Keep a dated monthly export and a pre-release export according to VIPC's retention policy; assign an owner to this task. Longer-term off-device archive storage and retention automation are not configured by this repository. Backups contain user records, password hashes, and potentially private submissions: restrict access and never commit or share them as ordinary asset exports.

Test recovery into a **new, empty local database**, never the live database. Use PostgreSQL tools at least as new as the source server (currently PostgreSQL 18). For a Render directory-format export, extract its archive and run:

```bash
createdb -h /PRIVATE/LOCAL/SOCKET -p 55439 cosolve_restore_check
pg_restore --exit-on-error --no-owner --no-acl \
  --host=/PRIVATE/LOCAL/SOCKET --port=55439 \
  --dbname=cosolve_restore_check /PRIVATE/BACKUP/EXTRACTED_DIRECTORY
```

Point an isolated local test process at that database; disable outgoing email and external integrations. Check migration state, asset/source/user counts, foreign-key restoration, private-page redirects, an authenticated search, and a representative asset page. Record the archive date, checksum, results, and any limitations. Stop the isolated database when finished. A restore drill does not prove that a future backup is valid, so repeat it quarterly and before handover.

September 21 verification: a complete hosted logical export was created at 14:57 UTC. Both the automated link and Chrome's native Save Link As workflow were tried; Chrome rejected the download with **Blocked by your organization**. An approved download route is needed before restoring that **hosted** export. Separately, a local PostgreSQL 18 backup was restored into a fresh test database: 527 assets, 1,711 sources, and one test administrator were present; the anonymous map redirected to login, and authenticated map/search/detail requests succeeded. This validates the local restore procedure, not the untested hosted archive. No live database was overwritten.

Set `OIDC_SERVER_URL`, `OIDC_CLIENT_ID`, and `OIDC_CLIENT_SECRET` together to enable organization sign-in. The provider must send a verified email that matches an active user created by an administrator. Leave all three unset to use password and TOTP authentication only.

Render's `RENDER_EXTERNAL_HOSTNAME` and Railway's `RAILWAY_PUBLIC_DOMAIN` are accepted automatically in production. A custom domain can be added through `DJANGO_ALLOWED_HOSTS`. The included `Procfile` supplies a portable Gunicorn start command for hosts that recognize it.

Rollback procedure:

1. Remove the failing release from traffic.
2. Restore the preceding application image or checkout.
3. Reverse only migrations documented as reversible. Otherwise restore the pre-release database backup into a separate database, check it, and deliberately switch the application connection. Identify and preserve any staff edits made since the backup before switching; do not overwrite the live database blindly.
4. Run `/health/`, a public API request, and the browser smoke test before restoring traffic.

Operational checks should cover database backups and restore drills, stale-record review, dependency updates, failed login monitoring, static-file availability, API errors, and staff account offboarding.

`STALE_VERIFICATION_DAYS` controls the review interval used by the staff data-quality dashboard. It defaults to 180 days.
