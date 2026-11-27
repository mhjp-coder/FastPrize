import hashlib
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fasthtml.common import Client

from fastprize.app import create_app
from fastprize.auth import hash_password, verify_password
from fastprize.config import env_flag
from fastprize.store import PASSWORD_RESET_TTL, sha256_token


def _client(app, *, follow: bool = True):
    client = Client(app)
    client.cli.follow_redirects = follow
    client.cli.headers.update({"Origin": "http://testserver"})
    return client


def _csrf(html: str) -> str:
    marker = 'name="csrf" value="'
    if marker in html:
        return html.split(marker, 1)[1].split('"', 1)[0]
    return html.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]


def _claim(client, token: str, email: str, password: str, *, confirmation: str | None = None):
    page = client.get(f"/setup?token={token}")
    csrf = _csrf(page.text) if 'name="csrf" value="' in page.text else ""
    return client.post(
        "/setup",
        data={
            "token": token,
            "email": email,
            "password": password,
            "confirmation": password if confirmation is None else confirmation,
            "csrf": csrf,
        },
    )


class _Mailbox:
    def __init__(self):
        self.messages = []

    def urlopen(self, request, timeout=10):
        self.messages.append(
            {
                "url": request.full_url,
                "headers": {key.lower(): value for key, value in request.header_items()},
                "body": json.loads(request.data.decode()),
                "timeout": timeout,
            }
        )
        return self

    def read(self):
        return b'{"id":"email_test"}'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def status(self):
        return 200


def _install_mailbox(monkeypatch):
    mailbox = _Mailbox()
    monkeypatch.setattr("fastprize.mail.urllib.request.urlopen", mailbox.urlopen)
    return mailbox


def _reset_link(message: dict) -> str:
    return message["body"]["text"].split("works once:\n", 1)[1].split("\n", 1)[0].strip()


def test_setup_token_claim_is_single_use(tmp_path, monkeypatch):
    monkeypatch.setenv("SETUP_TOKEN", "example-setup-token")
    database = tmp_path / "setup.sqlite3"
    app, store = create_app(database)
    stored = store.db.q("SELECT token_hash, claimed_at FROM instance_setup")[0]
    assert stored["claimed_at"] is None
    assert stored["token_hash"] == sha256_token("example-setup-token")
    assert stored["token_hash"] != "example-setup-token"
    assert store.admin_count() == 0

    client = _client(app)
    blocked = _client(app, follow=False).get("/admin/accounts")
    assert blocked.status_code == 303
    assert urlsplit(blocked.headers["location"]).path == "/setup"
    login = _client(app, follow=False).get("/login")
    assert login.status_code == 303
    assert urlsplit(login.headers["location"]).path == "/setup"

    rejected = _claim(
        client,
        "wrong-token",
        "owner@example.test",
        "correct-horse-battery",
    )
    assert "invalid or has already been used" in rejected.text
    assert store.admin_count() == 0

    short = _claim(client, "example-setup-token", "owner@example.test", "short-pass")
    assert "at least 12 characters" in short.text
    assert store.admin_count() == 0
    assert store.setup_is_pending()

    claimed = _claim(
        client,
        "example-setup-token",
        "owner@example.test",
        "correct-horse-battery",
    )
    assert claimed.status_code == 200
    assert "Claim this FastPrize" not in claimed.text
    assert store.admin_count() == 1
    admin = store.get_admin_by_email("owner@example.test")
    assert admin is not None
    assert verify_password(admin["password_hash"], "correct-horse-battery")
    accounts = client.get("/admin/accounts")
    assert accounts.status_code == 200
    assert "owner@example.test" in accounts.text

    reused = _claim(
        client,
        "example-setup-token",
        "other@example.test",
        "another-password-1",
    )
    assert "invalid or has already been used" in reused.text
    assert store.get_admin_by_email("other@example.test") is None

    restarted, again = create_app(database)
    assert not again.setup_is_pending()
    guest = _client(restarted)
    second = _claim(
        guest,
        "example-setup-token",
        "third@example.test",
        "another-password-1",
    )
    assert "already set up" in second.text
    assert again.admin_count() == 1
    spent = again.db.q("SELECT token_hash, claimed_at FROM instance_setup")[0]
    assert spent["token_hash"] is None
    assert spent["claimed_at"]


def test_setup_token_hash_accepts_the_plaintext_secret(tmp_path, monkeypatch):
    secret = "hashed-setup-secret"
    monkeypatch.setenv("SETUP_TOKEN_HASH", hashlib.sha256(secret.encode()).hexdigest())
    app, store = create_app(tmp_path / "hash.sqlite3")
    client = _client(app)
    claimed = _claim(client, secret, "hash-owner@example.test", "hash-password-123")
    assert "Claim this FastPrize" not in claimed.text
    assert store.get_admin_by_email("hash-owner@example.test") is not None
    assert not store.setup_is_pending()


def test_generated_setup_token_is_issued_once(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SETUP_TOKEN", "generate")
    database = tmp_path / "generated.sqlite3"
    app, store = create_app(database)
    token = capsys.readouterr().out.split("FastPrize setup token: ", 1)[1].splitlines()[0]
    assert token
    assert store.setup_is_pending()

    create_app(database)
    again = capsys.readouterr().out
    assert "FastPrize setup token:" not in again
    assert "already issued" in again

    claimed = _claim(
        _client(app),
        token,
        "generated@example.test",
        "generated-password-1",
    )
    assert store.get_admin_by_email("generated@example.test") is not None
    assert "Claim this FastPrize" not in claimed.text

    create_app(database)
    assert "FastPrize setup token:" not in capsys.readouterr().out
    assert not store.setup_is_pending()


def test_setup_token_conflicts_with_bootstrap_password(tmp_path, monkeypatch):
    monkeypatch.setenv("SETUP_TOKEN", "example-setup-token")
    monkeypatch.setenv("FASTPRIZE_ADMIN_EMAIL", "local@example.test")
    monkeypatch.setenv("FASTPRIZE_ADMIN_PASSWORD", "local-password-123")
    with pytest.raises(RuntimeError, match="cannot be combined"):
        create_app(tmp_path / "conflict.sqlite3")


def test_local_bootstrap_still_creates_one_admin(tmp_path, monkeypatch):
    monkeypatch.delenv("SETUP_TOKEN", raising=False)
    monkeypatch.delenv("SETUP_TOKEN_HASH", raising=False)
    monkeypatch.setenv("FASTPRIZE_ADMIN_EMAIL", "local@example.test")
    monkeypatch.setenv("FASTPRIZE_ADMIN_PASSWORD", "local-password-123")
    database = tmp_path / "local.sqlite3"
    app, store = create_app(database)
    admin = store.get_admin_by_email("local@example.test")
    assert admin is not None
    assert verify_password(admin["password_hash"], "local-password-123")
    assert not store.setup_is_pending()

    create_app(database)
    assert store.admin_count() == 1
    assert verify_password(
        store.get_admin_by_email("local@example.test")["password_hash"],
        "local-password-123",
    )

    client = _client(app)
    login = client.get("/login")
    assert "Admin sign in" in login.text
    assert "Forgot password?" in login.text
    closed = client.get("/setup")
    assert "already set up" in closed.text
    assert store.admin_count() == 1


def test_unconfigured_instance_keeps_the_local_admin_cli(tmp_path, monkeypatch):
    monkeypatch.delenv("SETUP_TOKEN", raising=False)
    monkeypatch.delenv("SETUP_TOKEN_HASH", raising=False)
    monkeypatch.delenv("FASTPRIZE_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("FASTPRIZE_ADMIN_PASSWORD", raising=False)
    app, store = create_app(tmp_path / "cli.sqlite3")
    page = _client(app).get("/login")
    assert "Admin setup required" in page.text
    assert "uv run fastprize-admin create you@example.com" in page.text
    setup = _client(app).get("/setup")
    assert "Admin setup required" in setup.text
    assert store.admin_count() == 0


def test_partial_bootstrap_env_is_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("SETUP_TOKEN", raising=False)
    monkeypatch.delenv("SETUP_TOKEN_HASH", raising=False)
    monkeypatch.setenv("FASTPRIZE_ADMIN_EMAIL", "local@example.test")
    monkeypatch.delenv("FASTPRIZE_ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="Set both FASTPRIZE_ADMIN_EMAIL"):
        create_app(tmp_path / "partial.sqlite3")


def test_password_reset_token_lifecycle_and_resend_send(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("APP_BASE_URL", "https://demo.fastprize.test")
    monkeypatch.delenv("RESEND_FROM", raising=False)
    app, store = create_app(tmp_path / "reset.sqlite3")
    store.create_admin("owner@example.test", hash_password("original-password-1"))
    mailbox = _install_mailbox(monkeypatch)
    client = _client(app)

    forgot = client.get("/forgot-password")
    unknown = client.post(
        "/forgot-password",
        data={"email": "missing@example.test", "csrf": _csrf(forgot.text)},
    )
    assert "If an account exists" in unknown.text
    assert mailbox.messages == []

    known = client.post(
        "/forgot-password",
        data={"email": "owner@example.test", "csrf": _csrf(unknown.text)},
    )
    assert known.text.count("If an account exists") == unknown.text.count(
        "If an account exists"
    )
    assert len(mailbox.messages) == 1
    message = mailbox.messages[0]
    assert message["url"] == "https://api.resend.com/emails"
    assert message["headers"]["authorization"] == "Bearer re_test_key"
    assert message["headers"]["idempotency-key"].startswith("password-reset/")
    assert message["body"]["from"] == "FastPrize <hello@fastprize.net>"
    assert message["body"]["to"] == ["owner@example.test"]
    assert message["body"]["subject"] == "Reset your FastPrize password"
    first_link = _reset_link(message)
    assert first_link.startswith("https://demo.fastprize.test/reset-password?token=")
    first_token = parse_qs(urlsplit(first_link).query)["token"][0]
    stored = store.db.q("SELECT token_hash, used_at FROM password_reset_tokens")
    assert stored[0]["used_at"] is None
    assert stored[0]["token_hash"] == sha256_token(first_token)
    assert first_token not in stored[0]["token_hash"]

    client.post(
        "/forgot-password",
        data={"email": "owner@example.test", "csrf": _csrf(known.text)},
    )
    assert len(mailbox.messages) == 2
    second_token = parse_qs(urlsplit(_reset_link(mailbox.messages[1])).query)["token"][0]
    stale = client.post(
        "/reset-password",
        data={
            "token": first_token,
            "password": "replacement-password",
            "confirmation": "replacement-password",
            "csrf": _csrf(client.get(f"/reset-password?token={first_token}").text),
        },
    )
    assert "invalid or has expired" in stale.text
    assert verify_password(
        store.get_admin_by_email("owner@example.test")["password_hash"],
        "original-password-1",
    )

    form = client.get(f"/reset-password?token={second_token}")
    mismatched = client.post(
        "/reset-password",
        data={
            "token": second_token,
            "password": "replacement-password",
            "confirmation": "different-password-1",
            "csrf": _csrf(form.text),
        },
    )
    assert "did not match" in mismatched.text
    updated = client.post(
        "/reset-password",
        data={
            "token": second_token,
            "password": "replacement-password",
            "confirmation": "replacement-password",
            "csrf": _csrf(mismatched.text),
        },
    )
    assert "Password updated" in updated.text
    admin = store.get_admin_by_email("owner@example.test")
    assert verify_password(admin["password_hash"], "replacement-password")
    assert not verify_password(admin["password_hash"], "original-password-1")

    reused = client.post(
        "/reset-password",
        data={
            "token": second_token,
            "password": "third-password-123",
            "confirmation": "third-password-123",
            "csrf": _csrf(client.get("/forgot-password").text),
        },
    )
    assert "invalid or has expired" in reused.text
    assert verify_password(
        store.get_admin_by_email("owner@example.test")["password_hash"],
        "replacement-password",
    )
    signed_in = client.post(
        "/login",
        data={
            "email": "owner@example.test",
            "password": "replacement-password",
            "csrf": _csrf(updated.text),
        },
    )
    assert "Admin sign in" not in signed_in.text


def test_password_reset_rejects_expired_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("APP_BASE_URL", "https://demo.fastprize.test")
    app, store = create_app(tmp_path / "expired.sqlite3")
    store.create_admin("owner@example.test", hash_password("original-password-1"))
    mailbox = _install_mailbox(monkeypatch)
    client = _client(app)
    page = client.get("/forgot-password")
    client.post(
        "/forgot-password",
        data={"email": "owner@example.test", "csrf": _csrf(page.text)},
    )
    token = parse_qs(urlsplit(_reset_link(mailbox.messages[0])).query)["token"][0]
    expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat(timespec="seconds")
    store.db.q(
        "UPDATE password_reset_tokens SET expires_at = ?",
        (expired,),
    )
    form = client.get(f"/reset-password?token={token}")
    rejected = client.post(
        "/reset-password",
        data={
            "token": token,
            "password": "replacement-password",
            "confirmation": "replacement-password",
            "csrf": _csrf(form.text),
        },
    )
    assert "invalid or has expired" in rejected.text
    assert verify_password(
        store.get_admin_by_email("owner@example.test")["password_hash"],
        "original-password-1",
    )
    assert PASSWORD_RESET_TTL == timedelta(minutes=30)


def test_password_reset_uses_a_validated_origin_and_custom_from(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    monkeypatch.setenv("RESEND_FROM", "Prize Desk <hello@fastprize.net>")
    app, store = create_app(tmp_path / "origin.sqlite3")
    store.create_admin("owner@example.test", hash_password("original-password-1"))
    mailbox = _install_mailbox(monkeypatch)
    client = _client(app)
    page = client.get("/forgot-password")
    client.post(
        "/forgot-password",
        data={"email": "owner@example.test", "csrf": _csrf(page.text)},
    )
    link = _reset_link(mailbox.messages[0])
    assert link.startswith("http://testserver/reset-password?token=")
    assert mailbox.messages[0]["body"]["from"] == "Prize Desk <hello@fastprize.net>"

    monkeypatch.setenv("APP_BASE_URL", "javascript:alert(1)")
    client.cli.headers.pop("Origin")
    client.post(
        "/forgot-password",
        data={"email": "owner@example.test", "csrf": _csrf(page.text)},
    )
    assert len(mailbox.messages) == 1


def test_forgot_password_without_resend_does_not_send(tmp_path, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    app, store = create_app(tmp_path / "no-mail.sqlite3")
    store.create_admin("owner@example.test", hash_password("original-password-1"))
    mailbox = _install_mailbox(monkeypatch)
    client = _client(app)
    page = client.post("/forgot-password", data={"email": "owner@example.test"})
    assert "not configured" in page.text
    assert "fastprize-admin reset-password" in page.text
    assert mailbox.messages == []
    assert store.db.q("SELECT id FROM password_reset_tokens") == []


def test_health_is_public_and_reports_database_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("SETUP_TOKEN", "example-setup-token")
    app, store = create_app(tmp_path / "health.sqlite3")
    client = _client(app, follow=False)
    healthy = client.get("/health")
    assert healthy.status_code == 200
    assert healthy.json() == {"status": "ok"}
    assert store.setup_is_pending()

    def unavailable(*args, **kwargs):
        raise RuntimeError("database offline")

    monkeypatch.setattr(store.db, "q", unavailable)
    outage = client.get("/health")
    assert outage.status_code == 503
    assert outage.json() == {"status": "unavailable"}


def test_dummy_data_seed_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("SEED_DUMMY_DATA", "true")
    database = tmp_path / "demo.sqlite3"
    _app, store = create_app(database)
    events = store.list_events()
    assert [event["name"] for event in events] == ["Demo event"]
    event_id = events[0]["id"]
    assert any(entrant["name"] == "Ava Thompson" for entrant in store.entrants(event_id))
    assert any(
        prize["prize_name"] == "Wireless Noise-Canceling Headphones"
        for prize in store.prizes(event_id)
    )
    entrant_count = len(store.entrants(event_id))
    prize_count = len(store.prizes(event_id))
    assert entrant_count > 1
    assert prize_count > 1

    _restarted, again = create_app(database)
    events = again.list_events()
    assert [event["name"] for event in events] == ["Demo event"]
    assert len(again.entrants(event_id)) == entrant_count
    assert len(again.prizes(event_id)) == prize_count

    from fastprize.store import PrizeDrawStore

    occupied = tmp_path / "occupied.sqlite3"
    existing = PrizeDrawStore(occupied)
    existing.create_event("Real event")
    monkeypatch.setenv("SEED_DUMMY_DATA", "1")
    create_app(occupied)
    names = [event["name"] for event in existing.list_events()]
    assert names == ["Real event"]
    assert existing.get_meta("dummy_data_seeded") == "skipped"
    create_app(occupied)
    assert [event["name"] for event in existing.list_events()] == ["Real event"]


def test_seed_flag_parser(monkeypatch):
    monkeypatch.setenv("SEED_DUMMY_DATA", "yes")
    assert env_flag("SEED_DUMMY_DATA")
    monkeypatch.setenv("SEED_DUMMY_DATA", "false")
    assert not env_flag("SEED_DUMMY_DATA")
    monkeypatch.delenv("SEED_DUMMY_DATA", raising=False)
    assert not env_flag("SEED_DUMMY_DATA")


def test_admin_billing_link_defaults_and_can_be_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("BILLING_URL", raising=False)
    app, store = create_app(tmp_path / "billing.sqlite3")
    store.create_admin("owner@example.test", hash_password("original-password-1"))
    client = _client(app)
    login = client.get("/login")
    client.post(
        "/login",
        data={
            "email": "owner@example.test",
            "password": "original-password-1",
            "csrf": _csrf(login.text),
        },
    )
    page = client.get("/admin/accounts")
    assert 'href="https://fastprize.net/billing"' in page.text
    assert 'class="billing-link"' in page.text
    assert 'target="_blank"' in page.text
    assert 'rel="noopener noreferrer"' in page.text

    monkeypatch.setenv("BILLING_URL", "https://billing.example.test/account")
    custom = client.get("/admin/accounts")
    assert 'href="https://billing.example.test/account"' in custom.text
    assert "https://fastprize.net/billing" not in custom.text

    monkeypatch.setenv("BILLING_URL", "javascript:alert(1)")
    fallback = client.get("/admin/accounts")
    assert "javascript:" not in fallback.text
    assert 'href="https://fastprize.net/billing"' in fallback.text
