# FastPrize Local Admin Authentication

## Decisions
- Local admins sign in with email and password. No external identity provider, email delivery, or public self-registration.
- All enabled admins have equal authority to create, disable, and reset other admin accounts.
- The first account is bootstrapped from environment variables, then managed in the app.
- Management pages and mutations require login.
- Projector display HTML and its read-only result endpoints remain public. The display-link dialog is protected.
- Remote administration is supported behind a trusted HTTPS reverse proxy.
- All-admin lockout recovery is a machine-local CLI command.

## Implemented
- SQLite `admins` records store normalized unique email, Argon2id hash, enabled state, creation time, and auth version.
- SQLite login-attempt records throttle repeated failures per normalized email.
- `FASTPRIZE_ADMIN_EMAIL` and `FASTPRIZE_ADMIN_PASSWORD` bootstrap one admin only when the database has no admins. Supplying only one is a startup error. Existing databases without an admin can use the local CLI.
- FastHTML signed sessions last 12 hours. Resetting a password or disabling an account increments its auth version and invalidates existing sessions.
- `FASTPRIZE_COOKIE_SECURE=true` requires `FASTPRIZE_SESSION_SECRET` with at least 32 characters. Session cookies are HttpOnly and SameSite=Lax.
- Central beforeware protects management routes, performs same-origin/CSRF checks for unsafe methods, and allows only login, static assets, and projector display/result routes anonymously.
- HTMX requests send the session CSRF token from the response meta tag.
- Login errors are generic. After five failures in a 15-minute window, login is blocked for 15 minutes.
- Admins can create, enable/disable, and reset accounts. The final enabled admin cannot be disabled.
- `uv run fastprize-admin create EMAIL` and `uv run fastprize-admin reset-password EMAIL` prompt without echoing password input.

## Deployment
- Configure a stable private `FASTPRIZE_SESSION_SECRET`, at least 32 characters, for deployments and multiple workers.
- For HTTPS reverse-proxy deployments, set `FASTPRIZE_COOKIE_SECURE=true` and configure `FORWARDED_ALLOW_IPS` to the exact trusted proxy address or addresses. Configure the proxy to overwrite forwarded headers and do not expose the upstream app port directly to the Internet.
- Projector links intentionally expose that event's current winner and draw details to anyone who has the URL.

## Validation
- Focused tests cover email normalization, hash/version reset, throttle persistence, final-admin protection, login/logout, route boundaries, public projector access, bootstrap-once behavior, cross-origin POST rejection, and secure-cookie configuration.
- Full validation commands: `uv run pytest` and `uv run ruff check src tests`.

## Follow-up
- The full test suite has one known pre-existing failure: `test_workspace_contains_combined_csv_import_form` expects two backdrop-enabled dialogs but the rendered page contains three. Update that unrelated expectation separately if desired.
