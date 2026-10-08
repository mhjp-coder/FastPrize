# FastPrize

FastPrize is a local FastHTML app for managing conference prize draws. Create separate events, add or import entrants and prizes, choose whether winners stay eligible, and open a dedicated live display for a projector.

## Run

```sh
uv sync
uv run fastprize
```

Open http://localhost:5001 for the landing page, then choose **Events** to create or select an event. The default SQLite database is `fastprize.sqlite3` in the current working directory. Set `FASTPRIZE_DB_PATH` to use another location.

## CSV Imports

Entrant CSV files require a `name` column and may include an `organization` column. Prize CSV files require a `prize_name` column and may include `sponsor` and `number` columns (`prize_number` is also accepted). Prize numbers are stored as text, preserving leading zeros. UTF-8 CSV files are supported. Blank rows are ignored; rows without a name are reported. Entrants with the same case-insensitive name and organization are imported only once per event. Duplicate prize rows are kept as separate awards.

## Draws

Open an event workspace, then select Draw beside an available prize. The app records each result and updates entrant eligibility using the event setting. Use **Live display** to open that event's separate live screen; it checks for new results automatically.

The app is intended for a trusted local operator and does not include user accounts or audit-grade draw verification.
