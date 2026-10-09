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

For a new database, set `FASTPRIZE_ADMIN_EMAIL` and `FASTPRIZE_ADMIN_PASSWORD` before the first start. The password must be at least 12 characters. These values are used only to create the first admin when the database has no admin accounts; they are not recreated or changed on later starts. If the database already exists without an admin, create one locally with `uv run fastprize-admin create you@example.com`.

Signed sessions last 7 days. Set `FASTPRIZE_SESSION_SECRET` to a stable, private signing secret (at least 32 characters) when deploying or running multiple workers. For HTTPS reverse-proxy deployments, set `FASTPRIZE_COOKIE_SECURE=true`, configure Uvicorn's `FORWARDED_ALLOW_IPS` to the exact proxy address(es), and configure the proxy to overwrite forwarded headers. Secure-cookie mode refuses to start without the explicit signing secret. Do not expose the app's upstream port directly to the Internet. Login throttling uses the submitted email and does not trust forwarded client-IP headers.

Admins can create, disable, delete, and reset other admin accounts from **Admins**. The disable confirmation dialog also offers permanent deletion. The last enabled admin cannot be disabled or deleted. Deleting your own account signs you out. If all admins are locked out, run `uv run fastprize-admin reset-password you@example.com` on the machine with database access. A CLI password reset also re-enables the account and invalidates its existing sessions; password resets in the web UI leave the enabled state unchanged. Password entry is hidden in the terminal.

Anyone with a projector display URL can view that event's current winner and draw details. Treat the URL as public information.

## CSV Imports

Entrant CSV files require a `name` column and may include an `organization` column. Prize CSV files require a `prize_name` column and may include `sponsor` and `number` columns (`prize_number` is also accepted). Prize numbers are stored as text, preserving leading zeros. UTF-8 CSV files are supported. Blank rows are ignored; rows without a name are reported. Entrants with the same case-insensitive name and organization are imported only once per event. Duplicate prize rows are kept as separate awards.

## Draws

Open an event workspace, then select Draw beside an available prize. The app records each result and updates entrant eligibility using the event setting. Use **Live display** to open that event's separate live screen; it checks for new results automatically. The winner's name and draw details remain on screen for three minutes, then a technology quote appears and changes every three minutes. Quotes are stored in `src/fastprize/quotes.txt`. The display's bottom-right theme control switches between light and dark modes and opens the color palette.

## Draw History

Draw timestamps are stored in UTC. The Draw history page displays them in the selected time zone, defaulting to the browser's local zone; the selection is saved in that browser.

The app uses local admin accounts but does not include audit-grade draw verification.

