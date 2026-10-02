import csv
import io
import json
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class ImportReport:
    added: int
    duplicates: int
    errors: tuple[str, ...]


class PrizeDrawStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    remove_winners INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS entrants (
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    organization TEXT NOT NULL DEFAULT '',
                    identity_key TEXT NOT NULL,
                    eligible INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(event_id, identity_key)
                );
                CREATE TABLE IF NOT EXISTS prizes (
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    sponsor TEXT NOT NULL DEFAULT '',
                    drawn INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS draws (
                    id INTEGER PRIMARY KEY,
                    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    entrant_id INTEGER REFERENCES entrants(id) ON DELETE SET NULL,
                    prize_id INTEGER REFERENCES prizes(id) ON DELETE SET NULL,
                    entrant_name TEXT NOT NULL,
                    organization TEXT NOT NULL,
                    prize_name TEXT NOT NULL,
                    sponsor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _normalized(value: str) -> str:
        return " ".join(value.split()).casefold()

    @classmethod
    def _identity_key(cls, name: str, organization: str) -> str:
        return json.dumps(
            [cls._normalized(name), cls._normalized(organization)],
            ensure_ascii=False,
        )

    def create_event(self, name: str, remove_winners: bool = True) -> int:
        name = " ".join(name.split())
        if not name:
            raise ValueError("Event name is required")
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO events (name, remove_winners) VALUES (?, ?)",
                (name, int(remove_winners)),
            )
            return int(cursor.lastrowid)

    def list_events(self) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM events ORDER BY id DESC")
            return [dict(row) for row in rows]

    def get_event(self, event_id: int) -> dict | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_remove_winners(self, event_id: int, remove_winners: bool) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE events SET remove_winners = ? WHERE id = ?",
                (int(remove_winners), event_id),
            )

    def add_entrant(self, event_id: int, name: str, organization: str = "") -> bool:
        name = " ".join(name.split())
        organization = " ".join(organization.split())
        if not name:
            raise ValueError("Entrant name is required")
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO entrants
                   (event_id, name, organization, identity_key)
                   VALUES (?, ?, ?, ?)""",
                (event_id, name, organization, self._identity_key(name, organization)),
            )
            return cursor.rowcount == 1

    def add_prize(self, event_id: int, name: str, sponsor: str = "") -> int:
        name = " ".join(name.split())
        sponsor = " ".join(sponsor.split())
        if not name:
            raise ValueError("Prize name is required")
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO prizes (event_id, name, sponsor) VALUES (?, ?, ?)",
                (event_id, name, sponsor),
            )
            return int(cursor.lastrowid)

    def update_entrant(
        self, event_id: int, entrant_id: int, name: str, organization: str = ""
    ) -> bool:
        name = " ".join(name.split())
        organization = " ".join(organization.split())
        if not name:
            raise ValueError("Entrant name is required")
        try:
            with closing(self._connect()) as connection:
                cursor = connection.execute(
                    """UPDATE entrants SET name = ?, organization = ?, identity_key = ?
                       WHERE event_id = ? AND id = ?""",
                    (
                        name,
                        organization,
                        self._identity_key(name, organization),
                        event_id,
                        entrant_id,
                    ),
                )
                return cursor.rowcount == 1
        except sqlite3.IntegrityError as error:
            raise ValueError(
                "An entrant with that name and organization already exists"
            ) from error

    def update_prize(
        self, event_id: int, prize_id: int, name: str, sponsor: str = ""
    ) -> bool:
        name = " ".join(name.split())
        sponsor = " ".join(sponsor.split())
        if not name:
            raise ValueError("Prize name is required")
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """UPDATE prizes SET name = ?, sponsor = ?
                   WHERE event_id = ? AND id = ? AND drawn = 0""",
                (name, sponsor, event_id, prize_id),
            )
            return cursor.rowcount == 1

    def import_entrants(self, event_id: int, content: str) -> ImportReport:
        return self._import_csv(event_id, content, "organization", entrants=True)

    def import_prizes(self, event_id: int, content: str) -> ImportReport:
        return self._import_csv(event_id, content, "sponsor", entrants=False)

    def _import_csv(
        self, event_id: int, content: str, optional_column: str, entrants: bool
    ) -> ImportReport:
        try:
            reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
            headers = {
                header.strip().casefold() for header in (reader.fieldnames or [])
            }
            if "name" not in headers:
                return ImportReport(0, 0, ("CSV must include a name column.",))

            added = 0
            duplicates = 0
            errors = []
            for line_number, row in enumerate(reader, start=2):
                values = {
                    (key or "").strip().casefold(): (value or "").strip()
                    for key, value in row.items()
                }
                name = values.get("name", "")
                optional_value = values.get(optional_column, "")
                if not any(values.values()):
                    continue
                if not name:
                    errors.append(f"Row {line_number}: name is required.")
                    continue
                if entrants:
                    if self.add_entrant(event_id, name, optional_value):
                        added += 1
                    else:
                        duplicates += 1
                else:
                    self.add_prize(event_id, name, optional_value)
                    added += 1
            return ImportReport(added, duplicates, tuple(errors))
        except csv.Error as error:
            return ImportReport(0, 0, (f"Could not read CSV: {error}",))

    def entrants(self, event_id: int) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM entrants WHERE event_id = ? ORDER BY name COLLATE NOCASE",
                (event_id,),
            )
            return [dict(row) for row in rows]

    def prizes(self, event_id: int) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM prizes WHERE event_id = ? ORDER BY drawn, id",
                (event_id,),
            )
            return [dict(row) for row in rows]

    def remove_entrant(self, event_id: int, entrant_id: int) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM entrants WHERE event_id = ? AND id = ?",
                (event_id, entrant_id),
            )
            return cursor.rowcount == 1

    def remove_prize(self, event_id: int, prize_id: int) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM prizes WHERE event_id = ? AND id = ? AND drawn = 0",
                (event_id, prize_id),
            )
            return cursor.rowcount == 1

    def draw(
        self,
        event_id: int,
        prize_id: int,
        chooser: Callable[[list[dict]], dict] = secrets.choice,
    ) -> dict:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            event = connection.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            prize = connection.execute(
                "SELECT * FROM prizes WHERE id = ? AND event_id = ? AND drawn = 0",
                (prize_id, event_id),
            ).fetchone()
            entrants = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM entrants WHERE event_id = ? AND eligible = 1",
                    (event_id,),
                )
            ]
            if event is None:
                raise ValueError("Event not found")
            if prize is None:
                raise ValueError("Prize is not available for this event")
            if not entrants:
                raise ValueError("There are no eligible entrants")

            winner = chooser(entrants)
            created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            cursor = connection.execute(
                """INSERT INTO draws
                   (event_id, entrant_id, prize_id, entrant_name, organization,
                    prize_name, sponsor, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    winner["id"],
                    prize_id,
                    winner["name"],
                    winner["organization"],
                    prize["name"],
                    prize["sponsor"],
                    created_at,
                ),
            )
            connection.execute("UPDATE prizes SET drawn = 1 WHERE id = ?", (prize_id,))
            if event["remove_winners"]:
                connection.execute(
                    "UPDATE entrants SET eligible = 0 WHERE id = ?", (winner["id"],)
                )
            draw = connection.execute(
                "SELECT * FROM draws WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            connection.commit()
            return dict(draw)

    def draw_history(self, event_id: int) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM draws WHERE event_id = ? ORDER BY id DESC", (event_id,)
            )
            return [dict(row) for row in rows]

    def latest_draw(self, event_id: int) -> dict | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM draws WHERE event_id = ? ORDER BY id DESC LIMIT 1",
                (event_id,),
            ).fetchone()
            return dict(row) if row else None
