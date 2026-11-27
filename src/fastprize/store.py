import csv
import hashlib
import hmac
import io
import json
import os
import secrets
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apsw import ConstraintError
from fastlite import database

from fastprize.slug import public_event_slug

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "fastprize.sqlite3"
PASSWORD_RESET_TTL = timedelta(minutes=30)
DEMO_EVENT_NAME = "Demo event"


def sha256_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SetupClaimError(Exception):
    """The setup token is missing, wrong, or already spent."""


class _TokenRejected(Exception):
    """A password-reset token cannot be spent."""


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
            """CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS instance_setup (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                token_hash TEXT,
                claimed_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY,
                admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
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
        self.db.q(
            """UPDATE password_reset_tokens
               SET used_at = ?
               WHERE admin_id = ? AND used_at IS NULL""",
            (datetime.now(UTC).isoformat(timespec="seconds"), admin_id),
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
        with self.db.conn:
            self.db.t.draw_previews.delete_where("event_id = ?", (event_id,))
            self.db.t.draws.delete_where("event_id = ?", (event_id,))
            self.db.t.prizes.delete_where("event_id = ?", (event_id,))
            self.db.t.entrants.delete_where("event_id = ?", (event_id,))
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

    def clear_history(self, event_id: int) -> int:
        draws = self.draw_history(event_id)
        self.db.t.draws.delete_where(
            "event_id = ?",
            (event_id,),
        )
        return len(draws)

    def clear_event_data(
        self,
        event_id: int,
        *,
        entrants: bool = False,
        prizes: bool = False,
        history: bool = False,
    ) -> None:
        with self.db.conn:
            if history:
                self.clear_history(event_id)
            if entrants:
                self.clear_entrants(event_id)
            if prizes:
                self.db.t.draw_previews.delete_where(
                    "event_id = ?",
                    (event_id,),
                )
                self.clear_prizes(event_id)

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

    @contextmanager
    def _immediate(self):
        conn = self.db.conn
        if conn.in_transaction:
            yield
            return
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        else:
            if conn.in_transaction:
                conn.execute("COMMIT")

    def database_ready(self) -> bool:
        rows = self.db.q("SELECT 1 AS ready")
        return bool(rows and rows[0]["ready"] == 1)

    def get_meta(self, key: str) -> str | None:
        rows = self.db.q("SELECT value FROM app_meta WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def set_meta(self, key: str, value: str) -> None:
        self.db.q(
            """INSERT INTO app_meta (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value),
        )

    def _setup_row(self) -> dict | None:
        rows = self.db.q(
            "SELECT id, token_hash, claimed_at FROM instance_setup WHERE id = 1"
        )
        return rows[0] if rows else None

    def setup_is_pending(self) -> bool:
        row = self._setup_row()
        return bool(
            row
            and row["token_hash"]
            and not row["claimed_at"]
            and self.admin_count() == 0
        )

    def setup_status(self) -> str:
        row = self._setup_row()
        if row and row["claimed_at"]:
            return "claimed"
        if self.setup_is_pending():
            return "pending"
        return "inactive"

    def ensure_pending_setup(self, token_hash: str) -> None:
        with self._immediate():
            row = self._setup_row()
            if row is None:
                self.db.q(
                    """INSERT INTO instance_setup (id, token_hash, claimed_at)
                       VALUES (1, ?, NULL)""",
                    (token_hash,),
                )
                return
            if row["claimed_at"]:
                return
            current = row["token_hash"] or ""
            if len(current) == len(token_hash) and hmac.compare_digest(
                current, token_hash
            ):
                return
            self.db.q(
                """UPDATE instance_setup
                   SET token_hash = ?
                   WHERE id = 1 AND claimed_at IS NULL""",
                (token_hash,),
            )

    def retire_unclaimed_setup(self) -> None:
        row = self._setup_row()
        if row is None or row["claimed_at"]:
            return
        self.db.q(
            """UPDATE instance_setup
               SET token_hash = NULL, claimed_at = ?
               WHERE id = 1 AND claimed_at IS NULL""",
            (datetime.now(UTC).isoformat(timespec="seconds"),),
        )

    def claim_setup(self, token: str, email: str, password_hash: str) -> dict:
        presented = sha256_token(token.strip())
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self._immediate():
            row = self._setup_row()
            current = (row or {}).get("token_hash") or ""
            if (
                row is None
                or row["claimed_at"]
                or self.admin_count()
                or not current
                or len(current) != len(presented)
                or not hmac.compare_digest(current, presented)
            ):
                raise SetupClaimError
            admin = self.create_admin(email, password_hash)
            self.db.q(
                """UPDATE instance_setup
                   SET token_hash = NULL, claimed_at = ?
                   WHERE id = 1 AND claimed_at IS NULL AND token_hash = ?""",
                (now, current),
            )
            if self.db.conn.changes() != 1:
                raise SetupClaimError
            return admin

    @staticmethod
    def _reset_subject(email: str) -> str:
        return "password-reset:" + PrizeDrawStore.normalize_admin_email(email)

    def password_reset_is_limited(self, email: str, now: float) -> bool:
        return self.admin_login_is_limited(self._reset_subject(email), now)

    def record_password_reset_attempt(self, email: str, now: float) -> None:
        self.record_admin_login_failure(self._reset_subject(email), now)

    def issue_password_reset(self, admin_id: int, now: datetime | None = None) -> tuple[str, str]:
        moment = now or datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        digest = sha256_token(token)
        created = moment.isoformat(timespec="seconds")
        expires = (moment + PASSWORD_RESET_TTL).isoformat(timespec="seconds")
        with self._immediate():
            self.db.q(
                """UPDATE password_reset_tokens
                   SET used_at = ?
                   WHERE admin_id = ? AND used_at IS NULL""",
                (created, admin_id),
            )
            self.db.q(
                """INSERT INTO password_reset_tokens
                   (admin_id, token_hash, expires_at, created_at)
                   VALUES (?, ?, ?, ?)""",
                (admin_id, digest, expires, created),
            )
            token_id = self.db.q("SELECT last_insert_rowid() AS id")[0]["id"]
        return token, f"password-reset/{token_id}"

    def reset_password_with_token(self, token: str, password_hash: str) -> bool:
        presented = sha256_token(token.strip())
        now = datetime.now(UTC)
        stamp = now.isoformat(timespec="seconds")
        try:
            with self._immediate():
                rows = self.db.q(
                    """SELECT id, admin_id, expires_at, used_at
                       FROM password_reset_tokens
                       WHERE token_hash = ?""",
                    (presented,),
                )
                if len(rows) != 1 or rows[0]["used_at"]:
                    raise _TokenRejected
                expires = datetime.fromisoformat(rows[0]["expires_at"])
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=UTC)
                if expires <= now:
                    raise _TokenRejected
                self.db.q(
                    """UPDATE password_reset_tokens
                       SET used_at = ?
                       WHERE id = ? AND used_at IS NULL""",
                    (stamp, rows[0]["id"]),
                )
                if self.db.conn.changes() != 1:
                    raise _TokenRejected
                if not self.update_admin_password(rows[0]["admin_id"], password_hash):
                    raise _TokenRejected
        except _TokenRejected:
            return False
        return True

    def seed_demo_event(self, entrants_csv: str, prizes_csv: str) -> bool:
        """Import demo entrants and prizes once. Return True when a new event is created."""
        if self.get_meta("dummy_data_seeded"):
            return False
        with self._immediate():
            if self.get_meta("dummy_data_seeded"):
                return False
            if self.list_events():
                self.set_meta("dummy_data_seeded", "skipped")
                return False
            event_id = self.create_event(DEMO_EVENT_NAME)
            entrants = self.import_entrants(event_id, entrants_csv)
            prizes = self.import_prizes(event_id, prizes_csv)
            if entrants.errors or prizes.errors or entrants.added == 0 or prizes.added == 0:
                raise RuntimeError("Dummy data import failed")
            self.set_meta(
                "dummy_data_seeded",
                datetime.now(UTC).isoformat(timespec="seconds"),
            )
        return True
