import hmac
import time

from fasthtml.common import Form, P, RedirectResponse, Request
from monsterui.franken import Button, ButtonT, Card, H1, Input

from fastprize.auth import (
    admin_from_request,
    clear_session,
    csrf_token,
    establish_session,
    hash_password,
    is_safe_return_path,
    login_rate_subject,
    verify_password,
    verify_unknown_password,
)
from fastprize.ui import document, page_header, status_banner
from fastprize.views.events import _selected_event


def _login_page(req: Request, message: str = "", next_path: str = "/"):
    if not req.app.state.store.admin_count():
        content = Card(
            H1("Admin setup required"),
            P("Create the first admin locally on the server:"),
            P("uv run fastprize-admin create you@example.com", cls="login-command"),
            P("Then sign in here. Admin accounts can be managed in the app afterward."),
        )
    else:
        content = Card(
            H1("Admin sign in"),
            P(message, cls="status-banner", role="alert") if message else "",
            Form(
                Input(type="hidden", name="csrf", value=csrf_token(req)),
                Input(type="hidden", name="next", value=next_path),
                Input(
                    id="email",
                    name="email",
                    type="email",
                    autocomplete="username",
                    required=True,
                    autofocus=True,
                    placeholder="Email",
                    aria_label="Email",
                ),
                Input(
                    id="password",
                    name="password",
                    type="password",
                    autocomplete="current-password",
                    required=True,
                    placeholder="Password",
                    aria_label="Password",
                ),
                Button("Sign in", type="submit", cls=ButtonT.primary),
                method="post",
                action="/login",
                cls="stack",
            ),
        )
    return document("Admin sign in | FastPrize", content, login_page=True)


def _accounts_page(req: Request, message: str = ""):
    store = req.app.state.store
    selected_event = _selected_event(req, store)
    admins = store.list_admins()
    enabled_count = sum(bool(admin["enabled"]) for admin in admins)
    rows = []
    for admin in admins:
        rows.append(
            Card(
                P(admin["email"], cls="admin-email"),
                P("Enabled" if admin["enabled"] else "Disabled"),
                Form(
                    Input(
                        id=f"reset-password-{admin['id']}",
                        type="password",
                        name="password",
                        placeholder="New password",
                        aria_label=f"New password for {admin['email']}",
                        autocomplete="new-password",
                        minlength="12",
                        required=True,
                    ),
                    Button("Reset password", type="submit", cls=ButtonT.secondary),
                    method="post",
                    action=f"/admin/accounts/{admin['id']}/password",
                    cls="stack",
                ),
                Button(
                    "Disable" if admin["enabled"] else "Enable",
                    type="button",
                    cls=ButtonT.destructive if admin["enabled"] else ButtonT.primary,
                    data_confirm=(
                        f"Disable {admin['email']}? This account will no longer be able to sign in."
                        if admin["enabled"]
                        else f"Enable {admin['email']}?"
                    ),
                    data_confirm_action=f"/admin/accounts/{admin['id']}/enabled",
                    data_confirm_label="Disable" if admin["enabled"] else "Enable",
                    data_confirm_field="enabled",
                    data_confirm_value="0" if admin["enabled"] else "1",
                    onclick="confirmDelete(this)",
                ),
                Button(
                    "Delete",
                    type="button",
                    cls=ButtonT.destructive,
                    data_confirm=(
                        f"Delete {admin['email']} permanently? This cannot be undone."
                    ),
                    data_confirm_action=f"/admin/accounts/{admin['id']}/delete",
                    data_confirm_label="Delete",
                    onclick="confirmDelete(this)",
                )
                if not admin["enabled"] or enabled_count > 1
                else "",
                cls="admin-card",
            )
        )
    return document(
        "Admin accounts | FastPrize",
        page_header("Access", "Admins"),
        status_banner(message),
        Card(
            P(f"{len(admins)} total, {enabled_count} enabled", id="admin-counts"),
            Form(
                Input(
                    id="new-email",
                    name="email",
                    type="email",
                    autocomplete="off",
                    placeholder="Email",
                    aria_label="New admin email",
                    required=True,
                ),
                Input(
                    id="new-password",
                    name="password",
                    type="password",
                    autocomplete="new-password",
                    placeholder="Initial password",
                    aria_label="Initial password",
                    minlength="12",
                    required=True,
                ),
                Button("Add admin", type="submit", cls=ButtonT.primary),
                method="post",
                action="/admin/accounts",
                cls="stack",
                id="admin-add-form",
            ),
        ),
        *rows,
        event_id=selected_event["id"] if selected_event else None,
        event_name=selected_event["name"] if selected_event else None,
        active_link="accounts",
    )


def register_routes(rt, store):
    @rt("/login", methods=["GET", "POST"])
    def login(
        req: Request,
        email: str = "",
        password: str = "",
        csrf: str = "",
        next: str = "/",
    ):
        if req.method == "GET":
            if admin_from_request(req):
                return RedirectResponse("/", status_code=303)
            return _login_page(req, next_path=is_safe_return_path(next))

        session_token = req.session.get("csrf_token", "")
        if not session_token or not hmac.compare_digest(session_token, csrf):
            return _login_page(
                req,
                "Sign-in failed. Check your email and password.",
                is_safe_return_path(next),
            )

        subject = login_rate_subject(email)
        now = time.time()
        if store.admin_login_is_limited(subject, now):
            verify_unknown_password(password)
            return _login_page(
                req,
                "Sign-in failed. Check your email and password.",
                is_safe_return_path(next),
            )

        admin = store.get_admin_by_email(email)
        if admin is None:
            verify_unknown_password(password)
            password_ok = False
        else:
            password_ok = verify_password(admin["password_hash"], password)
        if admin is None or not admin["enabled"] or not password_ok:
            store.record_admin_login_failure(subject, now)
            return _login_page(
                req,
                "Sign-in failed. Check your email and password.",
                is_safe_return_path(next),
            )

        store.clear_admin_login_failures(subject)
        establish_session(req.session, admin)
        return RedirectResponse(is_safe_return_path(next), status_code=303)

    @rt("/logout", methods=["POST"])
    def logout(req: Request):
        clear_session(req.session)
        return RedirectResponse("/login", status_code=303)

    @rt("/admin/accounts", methods=["GET"])
    def account_list(req: Request):
        return _accounts_page(req)

    @rt("/admin/accounts", methods=["POST"])
    def account_create(req: Request, email: str, password: str):
        try:
            store.create_admin(email, hash_password(password))
        except ValueError as error:
            return _accounts_page(req, str(error))
        return _accounts_page(req, "Admin account created.")

    @rt("/admin/accounts/{admin_id}/enabled", methods=["POST"])
    def account_set_enabled(req: Request, admin_id: int, enabled: int):
        updated = store.set_admin_enabled(admin_id, bool(enabled))
        if not updated:
            return _accounts_page(
                req, "The final enabled admin cannot be disabled."
            )
        return _accounts_page(
            req,
            "Admin account enabled." if enabled else "Admin account disabled.",
        )

    @rt("/admin/accounts/{admin_id}/delete", methods=["POST"])
    def account_delete(req: Request, admin_id: int):
        current = admin_from_request(req)
        removed = store.delete_admin(admin_id)
        if not removed:
            if store.get_admin(admin_id) is None:
                return _accounts_page(req, "Admin account not found.")
            return _accounts_page(req, "The final enabled admin cannot be deleted.")
        if current and current["id"] == admin_id:
            clear_session(req.session)
            return RedirectResponse("/login", status_code=303)
        return _accounts_page(req, "Admin account deleted.")

    @rt("/admin/accounts/{admin_id}/password", methods=["POST"])
    def account_reset_password(req: Request, admin_id: int, password: str):
        try:
            password_hash = hash_password(password)
        except ValueError as error:
            return _accounts_page(req, str(error))
        if not store.update_admin_password(admin_id, password_hash):
            return _accounts_page(req, "Admin account not found.")
        return _accounts_page(req, "Password reset. That account must sign in again.")
