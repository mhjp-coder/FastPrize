# FastPrize

FastPrize is a local FastHTML app for managing conference prize draws. Create separate events, add or import entrants and prizes, choose whether winners stay eligible, and open a dedicated live display for a projector.

## Run

```sh
uv sync
uv run fastprize
```

Open http://localhost:5001 for the landing page, then choose **Events** to create or select an event. The app and admin CLI both default to `fastprize.sqlite3` in the project root, regardless of the current working directory. Set `FASTPRIZE_DB_PATH` to use another location; relative overrides are resolved from the current working directory.

## Admin Accounts

FastPrize requires a local admin account for event management. The projector display and its read-only result polling URL remain public so they can be opened on a separate screen. The display-link dialog and all management routes require sign-in.

For a new local or self-hosted database, set `FASTPRIZE_ADMIN_EMAIL` and `FASTPRIZE_ADMIN_PASSWORD` before the first start. The password must be at least 12 characters. These values are used only to create the first admin when the database has no admin accounts; they are not recreated or changed on later starts. If the database already exists without an admin, create one locally with `uv run fastprize-admin create you@example.com`. Leave `SETUP_TOKEN` and `SETUP_TOKEN_HASH` unset for this path. There is no built-in default password.

Hosted instances skip the static bootstrap password. Set one of `SETUP_TOKEN` (the secret itself), `SETUP_TOKEN=generate` (print a secret to the container log on first boot), or `SETUP_TOKEN_HASH` (the sha256 hex digest of the secret). Do not set `FASTPRIZE_ADMIN_EMAIL` or `FASTPRIZE_ADMIN_PASSWORD` in that mode. The new tenant opens `/setup?token=...` once, chooses their own admin email and password, and the token is deleted in the same database transaction. Restarts keep the env var but cannot spend the token again. Until that claim, management and sign-in routes stay on the setup page. After claim, or on a self-hosted database, `/setup` does not create another admin. A machine with the database file can still use `fastprize-admin` if the token was lost before claim.

Forgot-password mail uses the Resend REST API. Set `RESEND_API_KEY`, optional `RESEND_FROM` (default `FastPrize <hello@fastprize.net>`), and `APP_BASE_URL` to the public `https` origin (`http` is accepted only for localhost). When `APP_BASE_URL` is unset, a same-origin `Origin` header is used for the link. Reset links expire after 30 minutes and work once. The forgot-password response is the same whether or not the email matches an account. If `RESEND_API_KEY` is unset, the page explains that email reset is unavailable and points at `fastprize-admin reset-password` instead of calling Resend. `GET /health` is unauthenticated and returns `{"status": "ok"}` when the app can read the database, for provisioner checks. Set `SEED_DUMMY_DATA` to `true`, `1`, or `yes` to import `dummy_data/` into a "Demo event" on first boot; later starts do not add another copy. The admin panel links to billing at `BILLING_URL`, which defaults to `https://fastprize.net/billing`.

Signed sessions last 7 days. Set `FASTPRIZE_SESSION_SECRET` to a stable, private signing secret (at least 32 characters) when deploying or running multiple workers. For HTTPS reverse-proxy deployments, set `FASTPRIZE_COOKIE_SECURE=true`, configure Uvicorn's `FORWARDED_ALLOW_IPS` to the exact proxy address(es), and configure the proxy to overwrite forwarded headers. Secure-cookie mode refuses to start without the explicit signing secret. Do not expose the app's upstream port directly to the Internet. Login throttling uses the submitted email and does not trust forwarded client-IP headers.

## Docker Deployment

The production image runs one Uvicorn worker as an unprivileged user. SQLite lives in the Compose-managed `fastprize-data` volume; rebuilding or replacing the container does not remove it. Compose publishes only on `127.0.0.1`, for an HTTPS reverse proxy on the same host. Keep the app as a single instance because it uses SQLite. The image health check calls `GET /health`. Demo data files are included so `SEED_DUMMY_DATA` can seed a fresh volume.

For a local image, copy `.env.example` to `.env`, set `FASTPRIZE_SESSION_SECRET` to a randomly generated value of at least 32 characters (for example, `openssl rand -hex 32`), then run:

```sh
docker compose up -d --build
docker compose logs -f app
```

Releases are built on loki from a clean `main` checkout: `git fetch origin --tags && git checkout main && git merge --ff-only origin/main && scripts/build-image`. That pushes `ghcr.io/mhjp-coder/fastprize:<YY-MM.N>` and updates `:latest`. Production pins the numbered tag with `IMAGE_TAG` and never sets `IMAGE_TAG=latest`. Set `FASTPRIZE_IMAGE` to `ghcr.io/mhjp-coder/fastprize:<YY-MM.N>`, authenticate Docker to `ghcr.io` if the package is private, then run `docker compose pull` and `docker compose up -d --no-build`. GitHub Actions only tests and builds the image. It does not publish. See [DEPLOY.md](DEPLOY.md).

Configure the reverse proxy to replace, not append untrusted values to, `X-Forwarded-For` and `X-Forwarded-Proto`. Set `FORWARDED_ALLOW_IPS` to the exact proxy source IP address(es) as seen by the app container; do not use `*` on a network reachable by untrusted clients. Keep `FASTPRIZE_COOKIE_SECURE=true` when HTTPS terminates at the proxy. The public projector display and its read-only result polling URL remain accessible to anyone with their URL.

Hosted containers set `SETUP_TOKEN` (or `SETUP_TOKEN_HASH`) and let the tenant claim `/setup` instead of baking in a password. For a self-hosted container, create the first admin from the persistent database without putting a password in shell history or `.env`:

```sh
docker compose exec app fastprize-admin create you@example.com
```

If locked out, reset and re-enable the account the same way:

```sh
docker compose exec app fastprize-admin reset-password you@example.com
```

Back up SQLite using its online backup API, which includes a consistent snapshot while the app is running:

```sh
mkdir -p backups
docker compose exec -T app python -c 'import sqlite3; source = sqlite3.connect("/data/fastprize.sqlite3"); target = sqlite3.connect("/tmp/fastprize-backup.sqlite3"); source.backup(target); target.close(); source.close()'
docker compose cp app:/tmp/fastprize-backup.sqlite3 backups/fastprize.sqlite3
```

Store backups outside the Compose volume and protect them as sensitive event data. Keep the same session secret across updates so deployments do not sign out every admin. Do not remove the named volume during routine upgrades (`docker compose down -v` deletes the database).

Admins can create, disable, delete, and reset other admin accounts from **Admins**. The disable confirmation dialog also offers permanent deletion. The last enabled admin cannot be disabled or deleted. Deleting your own account signs you out. If all admins are locked out, run `uv run fastprize-admin reset-password you@example.com` on the machine with database access. A CLI password reset also re-enables the account and invalidates its existing sessions; password resets in the web UI leave the enabled state unchanged. Password entry is hidden in the terminal.

Anyone with a projector display URL can view that event's current winner and draw details. Treat the URL as public information.

## CSV Imports

Entrant CSV files require a `name` column and may include an `organization` column. Prize CSV files require a `prize_name` column and may include `sponsor` and `number` columns (`prize_number` is also accepted). Prize numbers are stored as text, preserving leading zeros. UTF-8 CSV files are supported. Blank rows are ignored; rows without a name are reported. Entrants with the same case-insensitive name and organization are imported only once per event. Duplicate prize rows are kept as separate awards.

## Draws

Open an event workspace, then select Draw beside an available prize. The app records each result and updates entrant eligibility using the event setting. Use **Live display** to open that event's separate live screen; it checks for new results automatically. The winner's name and draw details remain on screen for three minutes, then a technology quote appears and changes every three minutes. Quotes are stored in `src/fastprize/quotes.txt`. The display's bottom-right theme control switches between light and dark modes and opens the color palette.

## Draw History

Draw timestamps are stored in UTC and displayed in each viewer's local time zone.

The app uses local admin accounts but does not include audit-grade draw verification.

