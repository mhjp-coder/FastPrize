import hmac
import time

from fasthtml.common import (
    H1,
    H2,
    Article,
    Button,
    Details,
    Dialog,
    Div,
    Form,
    I,
    Input,
    Label,
    Nav,
    P,
    RedirectResponse,
    Request,
    Small,
    Span,
    Strong,
    Summary,
)

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
from fastprize.ui import document
from fastprize.views.events import _selected_event


def _login_page(req: Request, message: str = "", next_path: str = "/"):
    if not req.app.state.store.admin_count():
        content = Article(
            H1("Admin setup required", cls="large-text bottom-margin"),
            P("Create the first admin locally on the server:"),
            P("uv run fastprize-admin create you@example.com", cls="primary-text"),
            P("Then sign in here. Admin accounts can be managed in the app afterward."),
            cls="large-padding surface-container small-round",
        )
    else:
        content = Article(
            H1("Admin sign in", cls="large-text bottom-margin"),
            P(message, cls="error-text", role="alert") if message else "",
            Form(
                Input(type="hidden", name="csrf", value=csrf_token(req)),
                Input(type="hidden", name="next", value=next_path),
                Div(
                    Input(
                        id="email",
                        name="email",
                        type="email",
                        autocomplete="username",
                        required=True,
                        autofocus=True,
                        placeholder=" ",
                    ),
                    Label("Email", fr="email"),
                    cls="field label border round large bottom-margin",
                ),
                Div(
                    Input(
                        id="password",
                        name="password",
                        type="password",
                        autocomplete="current-password",
                        required=True,
                        placeholder=" ",
                    ),
                    Label("Password", fr="password"),
                    cls="field label border round large bottom-margin",
                ),
                Button(
                    I("login"),
                    Span("Sign in"),
                    type="submit",
                    cls="responsive large primary",
                ),
                method="post",
                action="/login",
            ),
            cls="large-padding surface-container small-round",
        )
    return document("Admin sign in | FastPrize", content, login_page=True)


def _accounts_page(req: Request, message: str = ""):
    store = req.app.state.store
    selected_event = _selected_event(req, store)
    admins = store.list_admins()
    rows = []
    for admin in admins:
        enabled_form = Form(
            Input(type="hidden", name="csrf", value=csrf_token(req)),
            Input(
                type="hidden",
                name="enabled",
                value="0" if admin["enabled"] else "1",
            ),
            Button(
                I("person_off" if admin["enabled"] else "person_check"),
                Span("Disable" if admin["enabled"] else "Enable"),
                type="submit",
                cls="error" if admin["enabled"] else "primary",
            ),
            method="post",
            action=f"/admin/accounts/{admin['id']}/enabled",
        )
        if admin["enabled"]:
            dialog_id = f"disable-admin-dialog-{admin['id']}"
            enabled_control = Div(
                Button(
                    I("person_off"),
                    Span("Disable"),
                    type="button",
                    aria_haspopup="dialog",
                    aria_controls=dialog_id,
                    data_ui=f"#{dialog_id}",
                    cls="error",
                ),
                Dialog(
                    H2("Disable admin?", cls="small"),
                    P("Disable ", Strong(admin["email"]), "?"),
                    P(
                        "This account will no longer be able to sign in, and its existing sessions will end."
                    ),
                    P(
                        "Delete permanently removes the account instead of disabling it. This cannot be undone."
                    ),
                    Nav(
                        Button(
                            "Cancel",
                            type="button",
                            data_ui=f"#{dialog_id}",
                            cls="text",
                        ),
                        enabled_form,
                        Form(
                            Input(type="hidden", name="csrf", value=csrf_token(req)),
                            Button(
                                I("delete"),
                                Span("Delete"),
                                type="submit",
                                cls="border error",
                            ),
                            method="post",
                            action=f"/admin/accounts/{admin['id']}/delete",
                        ),
                        cls="horizontal wrap right-align",
                    ),
                    id=dialog_id,
                    aria_label=f"Confirm disabling {admin['email']}",
                    data_close_on_backdrop="true",
                    cls="modal padding medium-width left-align",
                ),
            )
        else:
            enabled_control = enabled_form
        rows.append(
            Article(
                Div(
                    Strong(admin["email"]),
                    Small(
                        "Enabled" if admin["enabled"] else "Disabled",
                        cls="primary-text" if admin["enabled"] else "secondary-text",
                    ),
                    cls="vertical",
                ),
                Form(
                    Input(type="hidden", name="csrf", value=csrf_token(req)),
                    Div(
                        Input(
                            id=f"reset-password-{admin['id']}",
                            type="password",
                            name="password",
                            placeholder=" ",
                            autocomplete="new-password",
                            minlength=12,
                            required=True,
                        ),
                        Label("New password", fr=f"reset-password-{admin['id']}"),
                        cls="field label border fill round extra",
                    ),
                    Button(
                        I("lock_reset"),
                        Span("Reset password"),
                        type="submit",
                        cls="border responsive",
                    ),
                    method="post",
                    action=f"/admin/accounts/{admin['id']}/password",
                    cls="top-margin bottom-margin",
                ),
                Div(
                    enabled_control,
                    cls="horizontal middle-align small-space right-align bottom-margin",
                ),
                cls="s12 m6 l6 card padding tertiary-container small-round vertical",
                id=f"admin-row-{admin['id']}",
            )
        )
    return document(
        "Admin accounts | FastPrize",
        Article(
            Div(
                H1("Admins", cls="small max"),
                Form(
                    Input(type="hidden", name="csrf", value=csrf_token(req)),
                    Button(
                        I("logout"),
                        Span("Sign out"),
                        type="submit",
                        cls="secondary large",
                    ),
                    method="post",
                    action="/logout",
                ),
                cls="horizontal wrap middle-align",
            ),
            P(
                f"{len(admins)} total | {sum(bool(admin['enabled']) for admin in admins)} enabled",
                id="admin-counts",
            ),
            cls="card padding primary-container small-round vertical bottom-margin",
        ),
        P(message, cls="tertiary-container padding", role="status") if message else "",
        Details(
            Summary(
                I("expand_more", data_add_expansion_chevron=True),
                Span("Add admin"),
                cls="button primary responsive none",
                aria_expanded="false",
            ),
            Article(
                Form(
                    Input(type="hidden", name="csrf", value=csrf_token(req)),
                    Div(
                        Input(
                            id="new-email",
                            name="email",
                            type="email",
                            autocomplete="off",
                            placeholder=" ",
                            required=True,
                        ),
                        Label("Email", fr="new-email"),
                        cls="s6 m6 l6 field label border fill round extra",
                    ),
                    Div(
                        Input(
                            id="new-password",
                            name="password",
                            type="password",
                            autocomplete="new-password",
                            placeholder=" ",
                            minlength=12,
                            required=True,
                        ),
                        Label("Initial password", fr="new-password"),
                        cls="s6 m6 l6 field label border fill round extra",
                    ),
                    Button(
                        I("person_add"),
                        Span("Add admin"),
                        type="submit",
                        cls="s12 responsive extra primary",
                    ),
                    method="post",
                    action="/admin/accounts",
                    cls="grid small-space bottom-padding",
                ),
                cls="card padding secondary-container small-round vertical bottom-padding",
            ),
            id="admin-add-expansion",
            data_add_expansion="true",
            cls="vertical bottom-margin",
        ),
        Div(*rows, cls="grid small-space", id="admin-list"),
        event_id=selected_event["id"] if selected_event else None,
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
        changed = store.set_admin_enabled(admin_id, bool(enabled))
        message = (
            "Admin account updated."
            if changed
            else "The final enabled admin cannot be disabled."
        )
        return _accounts_page(req, message)

    @rt("/admin/accounts/{admin_id}/delete", methods=["POST"])
    def account_delete(req: Request, admin_id: int):
        current_admin = admin_from_request(req)
        if store.get_admin(admin_id) is None:
            return _accounts_page(req, "Admin account not found.")
        if not store.delete_admin(admin_id):
            return _accounts_page(req, "The final enabled admin cannot be deleted.")
        if current_admin is not None and current_admin["id"] == admin_id:
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
