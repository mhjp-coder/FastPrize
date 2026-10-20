import csv
import io
import json
import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from apsw import ConstraintError
from fastlite import database

from fastprize.slug import public_event_slug

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "fastprize.sqlite3"


def get_database_path() -> Path:
    return Path(os.environ.get("FASTPRIZE_DB_PATH") or DEFAULT_DATABASE_PATH)


@dataclass(frozen=True)
class ImportReport:
    added: int
    duplicates: int
    errors: tuple[str, ...]


class InvalidPrizeNumber(ValueError):
    pass


class PrizeDrawStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.db = database(self.db_path)
        self.db.q("PRAGMA foreign_keys = ON")
        self.initialize()

    def initialize(self) -> None:
        statements = (
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                remove_winners INTEGER NOT NULL DEFAULT 1
            )""",
            """CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL,
                email_normalized TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                auth_version INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS admin_login_attempts (
                subject TEXT PRIMARY KEY,
                window_started REAL NOT NULL,
                failures INTEGER NOT NULL,
                blocked_until REAL NOT NULL DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS entrants (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                organization TEXT NOT NULL DEFAULT '',
                identity_key TEXT NOT NULL,
                eligible INTEGER NOT NULL DEFAULT 1,
                UNIQUE(event_id, identity_key)
            )""",
            """CREATE TABLE IF NOT EXISTS prizes (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                prize_name TEXT NOT NULL,
                sponsor TEXT NOT NULL DEFAULT '',
                prize_number INTEGER,
                drawn INTEGER NOT NULL DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS draws (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                entrant_id INTEGER REFERENCES entrants(id) ON DELETE SET NULL,
                prize_id INTEGER REFERENCES prizes(id) ON DELETE SET NULL,
                entrant_name TEXT NOT NULL,
                organization TEXT NOT NULL,
                prize_name TEXT NOT NULL,
                sponsor TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS draw_previews (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                prize_id INTEGER REFERENCES prizes(id) ON DELETE CASCADE,
                entrant_id INTEGER REFERENCES entrants(id) ON DELETE SET NULL,
                entrant_name TEXT NOT NULL,
                organization TEXT NOT NULL,
                prize_name TEXT NOT NULL,
                sponsor TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(event_id, prize_id)
            )""",
        )
        for statement in statements:
            self.db.q(statement)
        self._migrate_prizes_schema()

    def _migrate_prizes_schema(self) -> None:
        columns = self.db.t.prizes.columns_dict
        if "prize_name" not in columns and "name" in columns:
            self.db.q("ALTER TABLE prizes RENAME COLUMN name TO prize_name")
            columns = self.db.t.prizes.columns_dict
        if "prize_number" not in columns:
            self.db.q("ALTER TABLE prizes ADD COLUMN prize_number INTEGER")

    @staticmethod
    def _one(table, where: str, where_args: tuple) -> dict | None:
        rows = table(
            where=where,
            where_args=where_args,
            limit=1,
            as_cls=False,
        )
        return rows[0] if rows else None

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
        event = self.db.t.events.insert(
            {"name": name, "remove_winners": int(remove_winners)}
        )
        return event["id"]

    def list_events(self) -> list[dict]:
        return self.db.t.events(order_by="id DESC", as_cls=False)

    def get_event(self, event_id: int) -> dict | None:
        return self._one(self.db.t.events, "id = ?", (event_id,))

    def display_slug(self, event: dict) -> str:
        return public_event_slug(event, self.list_events())

    def get_event_by_slug(self, slug: str) -> dict | None:
        events = self.list_events()
        folded = slug.casefold()
        for event in events:
            if public_event_slug(event, events).casefold() == folded:
                return event
        return None

    @staticmethod
    def normalize_admin_email(email: str) -> str:
        return email.strip().casefold()

    def admin_count(self, enabled_only: bool = False) -> int:
        rows = self.db.t.admins(
            where="enabled = 1" if enabled_only else None,
            as_cls=False,
        )
        return len(rows)

    def get_admin(self, admin_id: int) -> dict | None:
        return self._one(self.db.t.admins, "id = ?", (admin_id,))

    def get_admin_by_email(self, email: str) -> dict | None:
        normalized = self.normalize_admin_email(email)
        return self._one(
            self.db.t.admins,
            "email_normalized = ?",
            (normalized,),
        )

    def list_admins(self) -> list[dict]:
        return self.db.t.admins(
            order_by="email_normalized",
            select="id,email,enabled,created_at",
            as_cls=False,
        )

    def create_admin(self, email: str, password_hash: str) -> dict:
        normalized = self.normalize_admin_email(email)
        if not normalized or "@" not in normalized:
            raise ValueError("A valid email address is required")
        try:
            return self.db.t.admins.insert(
                {
                    "email": email.strip(),
                    "email_normalized": normalized,
                    "password_hash": password_hash,
                    "auth_version": secrets.randbits(62),
                    "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                }
            )
        except ConstraintError as error:
            raise ValueError("An account with that email already exists") from error

    def bootstrap_admin(self, email: str, password_hash: str) -> dict | None:
        with self.db.conn:
            if self.admin_count():
                return None
            return self.create_admin(email, password_hash)

    def update_admin_password(self, admin_id: int, password_hash: str) -> bool:
        admin = self.get_admin(admin_id)
        if admin is None:
            return False
        self.db.t.admins.update(
            {
                "id": admin_id,
                "password_hash": password_hash,
                "auth_version": admin["auth_version"] + 1,
            }
        )
        return True

    def set_admin_enabled(self, admin_id: int, enabled: bool) -> bool:
        admin = self.get_admin(admin_id)
        if admin is None:
            return False
        if bool(admin["enabled"]) == enabled:
            return True
        with self.db.conn:
            if not enabled and self.admin_count(enabled_only=True) <= 1:
                return False
            self.db.t.admins.update(
                {
                    "id": admin_id,
                    "enabled": int(enabled),
                    "auth_version": admin["auth_version"] + 1,
                }
            )
        return True

    def delete_admin(self, admin_id: int) -> bool:
        with self.db.conn:
            admin = self.get_admin(admin_id)
            if admin is None:
                return False
            if admin["enabled"] and self.admin_count(enabled_only=True) <= 1:
                return False
            self.db.t.admins.delete(admin_id)
        return True

    def admin_login_is_limited(self, subject: str, now: float) -> bool:
        attempt = self._one(
            self.db.t.admin_login_attempts,
            "subject = ?",
            (subject,),
        )
        if attempt is None:
            return False
        if attempt["blocked_until"] > now:
            return True
        if attempt["window_started"] <= now - 900:
            self.db.t.admin_login_attempts.delete(subject)
        return False

    def record_admin_login_failure(self, subject: str, now: float) -> None:
        with self.db.conn:
            self.db.t.admin_login_attempts.delete_where(
                "window_started <= ?",
                (now - 86400,),
            )
            attempt = self._one(
                self.db.t.admin_login_attempts,
                "subject = ?",
                (subject,),
            )
            if attempt is None or attempt["window_started"] <= now - 900:
                self.db.t.admin_login_attempts.insert(
                    {
                        "subject": subject,
                        "window_started": now,
                        "failures": 1,
                    }
                )
                return
            failures = attempt["failures"] + 1
            self.db.t.admin_login_attempts.update(
                {
                    "subject": subject,
                    "failures": failures,
                    "blocked_until": now + 900 if failures >= 5 else 0,
                }
            )

    def clear_admin_login_failures(self, subject: str) -> None:
        self.db.t.admin_login_attempts.delete_where("subject = ?", (subject,))

    def delete_event(self, event_id: int) -> bool:
        if self.get_event(event_id) is None:
            return False
        self.db.t.events.delete(event_id)
        return True

    def set_remove_winners(self, event_id: int, remove_winners: bool) -> None:
        self.db.t.events.update({"id": event_id, "remove_winners": int(remove_winners)})

    def add_entrant(self, event_id: int, name: str, organization: str = "") -> bool:
        name = " ".join(name.split())
        organization = " ".join(organization.split())
        if not name:
            raise ValueError("Entrant name is required")
        entrant = self.db.t.entrants.insert(
            {
                "event_id": event_id,
                "name": name,
                "organization": organization,
                "identity_key": self._identity_key(name, organization),
            },
            ignore=True,
        )
        return bool(entrant)

    @staticmethod
    def _prize_number(value: str | int | None) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            if value < 0:
                raise InvalidPrizeNumber("Prize number must be a whole number.")
            return value
        text = " ".join(str(value).split())
        if not text:
            return None
        if not text.isdigit():
            raise InvalidPrizeNumber("Prize number must be a whole number.")
        return int(text)

    def add_prize(
        self,
        event_id: int,
        name: str,
        sponsor: str = "",
        prize_number: str | int | None = None,
    ) -> int:
        name = " ".join(name.split())
        sponsor = " ".join(sponsor.split())
        number = self._prize_number(prize_number)
        if not name:
            raise ValueError("Prize name is required")
        prize = {
            "event_id": event_id,
            "prize_name": name,
            "sponsor": sponsor,
        }
        if number is not None:
            prize["prize_number"] = number
        return self.db.t.prizes.insert(prize)["id"]

    def update_entrant(
        self, event_id: int, entrant_id: int, name: str, organization: str = ""
    ) -> bool:
        name = " ".join(name.split())
        organization = " ".join(organization.split())
        if not name:
            raise ValueError("Entrant name is required")
        try:
            entrant = self._one(
                self.db.t.entrants,
                "event_id = ? AND id = ?",
                (event_id, entrant_id),
            )
            if entrant is None:
                return False
            entrant.update(
                name=name,
                organization=organization,
                identity_key=self._identity_key(name, organization),
            )
            self.db.t.entrants.update(entrant)
            return True
        except ConstraintError as error:
            raise ValueError(
                "An entrant with that name and organization already exists"
            ) from error

    def set_entrant_eligible(self, event_id: int, entrant_id: int, eligible: bool) -> bool:
        entrant = self._one(
            self.db.t.entrants,
            "event_id = ? AND id = ?",
            (event_id, entrant_id),
        )
        if entrant is None:
            return False
        self.db.t.entrants.update({"id": entrant_id, "eligible": int(eligible)})
        return True

    def update_prize(
        self,
        event_id: int,
        prize_id: int,
        name: str,
        sponsor: str = "",
        prize_number: str | int | None = None,
    ) -> bool:
        name = " ".join(name.split())
        sponsor = " ".join(sponsor.split())
        number = self._prize_number(prize_number)
        if not name:
            raise ValueError("Prize name is required")
        prize = self._one(
            self.db.t.prizes,
            "event_id = ? AND id = ? AND drawn = 0",
            (event_id, prize_id),
        )
        if prize is None:
            return False
        prize.update(prize_name=name, sponsor=sponsor, prize_number=number)
        self.db.t.prizes.update(prize)
        return True

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
            required_header = "name" if entrants else "prize_name"
            if required_header not in headers:
                label = "name" if entrants else "prize_name"
                return ImportReport(0, 0, (f"CSV must include a {label} column.",))

            added = 0
            duplicates = 0
            errors = []
            for line_number, row in enumerate(reader, start=2):
                values = {
                    (key or "").strip().casefold(): (value or "").strip()
                    for key, value in row.items()
                }
                name = values.get(required_header, "")
                optional_value = values.get(optional_column, "")
                if not any(values.values()):
                    continue
                if not name:
                    errors.append(f"Row {line_number}: {required_header} is required.")
                    continue
                if entrants:
                    if self.add_entrant(event_id, name, optional_value):
                        added += 1
                    else:
                        duplicates += 1
                else:
                    try:
                        prize_number = self._imported_prize_number(values)
                    except InvalidPrizeNumber:
                        errors.append(
                            f"Row {line_number}: prize number must be a whole number."
                        )
                        continue
                    self.add_prize(event_id, name, optional_value, prize_number)
                    added += 1
            return ImportReport(added, duplicates, tuple(errors))
        except csv.Error as error:
            return ImportReport(0, 0, (f"Could not read CSV: {error}",))

    def entrants(self, event_id: int) -> list[dict]:
        return self.db.t.entrants(
            where="event_id = ?",
            where_args=(event_id,),
            order_by="name COLLATE NOCASE",
            as_cls=False,
        )

    @staticmethod
    def _imported_prize_number(values: dict[str, str]) -> int | None:
        for key in ("prize_number", "prize #", "prize#", "prize number", "number"):
            if key in values:
                return PrizeDrawStore._prize_number(values[key])
        return None

    def prizes(self, event_id: int) -> list[dict]:
        return self.db.t.prizes(
            where="event_id = ?",
            where_args=(event_id,),
            order_by="drawn, prize_number IS NULL, prize_number, id",
            as_cls=False,
        )

    def remove_entrant(self, event_id: int, entrant_id: int) -> bool:
        entrant = self._one(
            self.db.t.entrants,
            "event_id = ? AND id = ?",
            (event_id, entrant_id),
        )
        if entrant is None:
            return False
        self.db.t.entrants.delete(entrant_id)
        return True

    def undo_award(self, event_id: int, prize_id: int) -> bool:
        prize = self._one(
            self.db.t.prizes,
            "event_id = ? AND id = ? AND drawn = 1",
            (event_id, prize_id),
        )
        if prize is None:
            return False
        draws = self.db.t.draws(
            where="event_id = ? AND prize_id = ?",
            where_args=(event_id, prize_id),
            as_cls=False,
        )
        with self.db.conn:
            for draw in draws:
                entrant_id = draw["entrant_id"]
                if entrant_id is not None and self._one(
                    self.db.t.entrants,
                    "event_id = ? AND id = ?",
                    (event_id, entrant_id),
                ):
                    self.db.t.entrants.update({"id": entrant_id, "eligible": 1})
                self.db.t.draws.delete(draw["id"])
            self.db.t.draw_previews.delete_where(
                "event_id = ? AND prize_id = ?",
                (event_id, prize_id),
            )
            self.db.t.prizes.update({"id": prize_id, "drawn": 0})
        return True

    def remove_prize(self, event_id: int, prize_id: int) -> bool:
        prize = self._one(
            self.db.t.prizes,
            "event_id = ? AND id = ? AND drawn = 0",
            (event_id, prize_id),
        )
        if prize is None:
            return False
        self.db.t.prizes.delete(prize_id)
        return True

    def clear_entrants(self, event_id: int) -> int:
        entrants = self.entrants(event_id)
        self.db.t.entrants.delete_where(
            "event_id = ?",
            (event_id,),
        )
        return len(entrants)

    def clear_prizes(self, event_id: int) -> int:
        prizes = self.prizes(event_id)
        self.db.t.prizes.delete_where(
            "event_id = ?",
            (event_id,),
        )
        return len(prizes)

    def clear_all_event_data(self, event_id: int) -> tuple[int, int]:
        self.db.t.draw_previews.delete_where(
            "event_id = ?",
            (event_id,),
        )
        return self.clear_entrants(event_id), self.clear_prizes(event_id)

    def preview_draw(
        self,
        event_id: int,
        prize_id: int,
        chooser: Callable[[list[dict]], dict] = secrets.choice,
    ) -> dict:
        event = self.get_event(event_id)
        prize = self._one(
            self.db.t.prizes,
            "id = ? AND event_id = ? AND drawn = 0",
            (prize_id, event_id),
        )
        entrants = self.db.t.entrants(
            where="event_id = ? AND eligible = 1",
            where_args=(event_id,),
            as_cls=False,
        )
        if event is None:
            raise ValueError("Event not found")
        if prize is None:
            raise ValueError("Prize is not available for this event")
        if not entrants:
            raise ValueError("There are no eligible entrants")
        winner = chooser(entrants)
        return {"winner": winner, "prize": prize}

    def draw(
        self,
        event_id: int,
        prize_id: int,
        chooser: Callable[[list[dict]], dict] = secrets.choice,
    ) -> dict:
        preview = self.preview_draw(event_id, prize_id, chooser)
        winner = preview["winner"]
        prize = preview["prize"]
        with self.db.conn:
            event = self.get_event(event_id)
            if event is None:
                raise ValueError("Event not found")
            available_prize = self._one(
                self.db.t.prizes,
                "id = ? AND event_id = ? AND drawn = 0",
                (prize_id, event_id),
            )
            if available_prize is None:
                raise ValueError("Prize is not available for this event")
            created_at = datetime.now(UTC).isoformat(timespec="microseconds")
            draw = self.db.t.draws.insert(
                {
                    "event_id": event_id,
                    "entrant_id": winner["id"],
                    "prize_id": prize_id,
                    "entrant_name": winner["name"],
                    "organization": winner["organization"],
                    "prize_name": prize["prize_name"],
                    "sponsor": prize["sponsor"],
                    "created_at": created_at,
                }
            )
            self.db.t.draw_previews.delete_where(
                "event_id = ? AND prize_id = ?",
                (event_id, prize_id),
            )
            self.db.t.prizes.update({"id": prize_id, "drawn": 1})
            if event["remove_winners"]:
                self.db.t.entrants.update({"id": winner["id"], "eligible": 0})
            return draw

    def draw_history(self, event_id: int) -> list[dict]:
        return self.db.t.draws(
            where="event_id = ?",
            where_args=(event_id,),
            order_by="id DESC",
            as_cls=False,
        )

    def latest_draw(self, event_id: int) -> dict | None:
        draws = self.db.t.draws(
            where="event_id = ?",
            where_args=(event_id,),
            order_by="id DESC",
            limit=1,
            as_cls=False,
        )
        return draws[0] if draws else None

    def save_preview(
        self, event_id: int, prize_id: int, winner: dict, prize: dict
    ) -> dict:
        created_at = datetime.now(UTC).isoformat(timespec="microseconds")
        preview = self._one(
            self.db.t.draw_previews,
            "event_id = ? AND prize_id = ?",
            (event_id, prize_id),
        )
        row = {
            "event_id": event_id,
            "prize_id": prize_id,
            "entrant_id": winner["id"],
            "entrant_name": winner["name"],
            "organization": winner["organization"],
            "prize_name": prize["prize_name"],
            "sponsor": prize["sponsor"],
            "created_at": created_at,
        }
        if preview is None:
            return self.db.t.draw_previews.insert(row)
        preview.update(row)
        return self.db.t.draw_previews.update(preview)

    def latest_preview(self, event_id: int) -> dict | None:
        previews = self.db.t.draw_previews(
            where="event_id = ?",
            where_args=(event_id,),
            order_by="id DESC",
            limit=1,
            as_cls=False,
        )
        return previews[0] if previews else None
