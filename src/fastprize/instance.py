import os
import secrets
from pathlib import Path

from fastprize.auth import hash_password
from fastprize.config import env_flag
from fastprize.store import PrizeDrawStore, sha256_token

_SETUP_HASH_LENGTH = 64
_SETUP_HASH_ALPHABET = frozenset("0123456789abcdef")


def dummy_data_directory() -> Path:
    packaged = Path(__file__).resolve().parents[2] / "dummy_data"
    if (packaged / "entrants.csv").is_file():
        return packaged
    return Path.cwd() / "dummy_data"


def _setup_token_hash() -> str | None:
    token = os.environ.get("SETUP_TOKEN", "").strip()
    token_hash = os.environ.get("SETUP_TOKEN_HASH", "").strip().lower()
    if token and token_hash:
        raise RuntimeError("Set only one of SETUP_TOKEN or SETUP_TOKEN_HASH")
    if token.casefold() == "generate":
        return "generate"
    if token:
        return sha256_token(token)
    if not token_hash:
        return None
    if len(token_hash) != _SETUP_HASH_LENGTH or any(
        character not in _SETUP_HASH_ALPHABET for character in token_hash
    ):
        raise RuntimeError("SETUP_TOKEN_HASH must be a 64-character sha256 hex digest")
    return token_hash


def _bootstrap_admin(store: PrizeDrawStore) -> None:
    email = os.environ.get("FASTPRIZE_ADMIN_EMAIL", "").strip()
    password = os.environ.get("FASTPRIZE_ADMIN_PASSWORD", "")
    if bool(email) != bool(password):
        raise RuntimeError(
            "Set both FASTPRIZE_ADMIN_EMAIL and FASTPRIZE_ADMIN_PASSWORD to bootstrap an admin"
        )
    if email and not store.admin_count():
        store.bootstrap_admin(email, hash_password(password))


def configure_admin_access(store: PrizeDrawStore) -> None:
    email = os.environ.get("FASTPRIZE_ADMIN_EMAIL", "").strip()
    password = os.environ.get("FASTPRIZE_ADMIN_PASSWORD", "")
    digest = _setup_token_hash()
    if digest and (email or password):
        raise RuntimeError(
            "Setup token claim cannot be combined with "
            "FASTPRIZE_ADMIN_EMAIL and FASTPRIZE_ADMIN_PASSWORD"
        )
    if digest is None:
        _bootstrap_admin(store)
        return
    if store.admin_count():
        return
    if digest == "generate":
        if store.setup_is_pending():
            print(
                "FastPrize setup token was already issued. "
                "Use the original token to claim this instance.",
                flush=True,
            )
            return
        generated = secrets.token_urlsafe(32)
        store.ensure_pending_setup(sha256_token(generated))
        print(f"FastPrize setup token: {generated}", flush=True)
        print(
            "Claim this instance at /setup with this token. It works once.",
            flush=True,
        )
        return
    store.ensure_pending_setup(digest)


def seed_dummy_data(store: PrizeDrawStore, directory: Path | None = None) -> bool:
    folder = directory or dummy_data_directory()
    entrants_path = folder / "entrants.csv"
    prizes_path = folder / "prizes.csv"
    if not entrants_path.is_file() or not prizes_path.is_file():
        raise RuntimeError(
            f"SEED_DUMMY_DATA is set but dummy data was not found in {folder}"
        )
    return store.seed_demo_event(
        entrants_path.read_text(encoding="utf-8"),
        prizes_path.read_text(encoding="utf-8"),
    )


def prepare_instance(store: PrizeDrawStore) -> None:
    configure_admin_access(store)
    if store.admin_count():
        store.retire_unclaimed_setup()
    if env_flag("SEED_DUMMY_DATA"):
        seed_dummy_data(store)
