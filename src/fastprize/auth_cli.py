import argparse
import getpass

from fastprize.auth import hash_password
from fastprize.store import PrizeDrawStore, get_database_path


def main() -> None:
    parser = argparse.ArgumentParser(prog="fastprize-admin")
    parser.add_argument("action", choices=("create", "reset-password"))
    parser.add_argument("email")
    args = parser.parse_args()

    store = PrizeDrawStore(get_database_path())
    password = getpass.getpass("New admin password (12+ characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords did not match")
    try:
        password_hash = hash_password(password)
        if args.action == "create":
            store.create_admin(args.email, password_hash)
            print("Admin account created.")
            return
        admin = store.get_admin_by_email(args.email)
        if admin is None:
            parser.error("No account exists for that email")
        with store.db.conn:
            store.update_admin_password(admin["id"], password_hash)
            store.set_admin_enabled(admin["id"], True)
        print("Admin password reset. Account enabled.")
    except ValueError as error:
        parser.error(str(error))
