import hmac
import logging
import time
from urllib.parse import quote

from fasthtml.common import A, Div, Form, Label, P, RedirectResponse, Request, Span
from monsterui.franken import (
    H1,
    Button,
    ButtonT,
    Card,
    CodeSpan,
    FlexT,
    Grid,
    Input,
    Switch,
    TextT,
    UkIcon,
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
from fastprize.config import resend_api_key, resolve_public_base_url
from fastprize.mail import send_password_reset_email
from fastprize.store import PASSWORD_RESET_TTL, SetupClaimError
from fastprize.ui import (
    billing_anchor,
    brand_mark,
    document,
    emphasized,
    hstack,
    page_header,
    status_banner,
)
from fastprize.views.events import _selected_event

logger = logging.getLogger(__name__)
_RESET_MINUTES = int(PASSWORD_RESET_TTL.total_seconds() // 60)
_SETUP_REJECTED = "This setup link is invalid or has already been used."
_RESET_SENT = (
    "If an account exists for that email, we sent a password reset link. "
    f"It expires in {_RESET_MINUTES} minutes and works once."
)
_RESET_UNAVAILABLE = (
    "Email password reset is not configured. On the server, run "
    "fastprize-admin reset-password you@example.com."
)
_RESET_REJECTED = "This reset link is invalid or has expired."


def _login_brand():
    return Div(brand_mark(), Span("FastPrize"), cls="brand login-brand")


def _csrf_matches(req: Request, supplied: str) -> bool:
    session_token = req.session.get("csrf_token", "")
    return bool(
        session_token
        and supplied
        and len(session_token) == len(supplied)
        and hmac.compare_digest(session_token, supplied)
    )


def _login_page(
    req: Request,
    message: str = "",
    next_path: str = "/",
    tone: str = "error",
):
    if not req.app.state.store.admin_count():
        content = Card(
            H1("Admin setup required"),
            P("Create the first admin locally on the server:"),
            P(CodeSpan("uv run fastprize-admin create you@example.com")),
            P("Then sign in here. Admin accounts can be managed in the app afterward."),
            cls="w-full max-w-md",
        )
    else:
        content = Card(
            H1("Admin sign in"),
            status_banner(message, tone),
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
                Button("Sign in", type="submit", cls=(ButtonT.primary, "self-start")),
                method="post",
                action="/login",
                cls=(FlexT.block, FlexT.column, "gap-6"),
            ),
            A("Forgot password?", href="/forgot-password"),
            cls="w-full max-w-md",
        )
    return document(
        "Admin sign in | FastPrize",
        Div(_login_brand(), content, cls="login-intro"),
        login_page=True,
    )


def _accounts_page(req: Request, message: str = "", tone: str = "info"):
    store = req.app.state.store
    selected_event = _selected_event(req, store)
    admins = store.list_admins()
    enabled_count = sum(bool(admin["enabled"]) for admin in admins)
    rows = []
    for admin in admins:
        rows.append(
            Card(
                P(admin["email"], cls=TextT.bold),
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
                    hstack(
                        Button("Reset password", type="submit", cls=ButtonT.secondary),
                        Button(
                            UkIcon("trash-2"),
                            type="button",
                            cls=(ButtonT.destructive, ButtonT.icon, "icon-btn"),
                            aria_label="Delete",
                            data_confirm=(
                                f"Delete {emphasized(admin['email'])} permanently? This cannot be undone."
                            ),
                            data_confirm_action=f"/admin/accounts/{admin['id']}/delete",
                            data_confirm_label="Delete",
                            onclick="confirmDelete(this)",
                        )
                        if not admin["enabled"] or enabled_count > 1
                        else "",
                    ),
                    method="post",
                    action=f"/admin/accounts/{admin['id']}/password",
                    cls=(FlexT.block, FlexT.column, "gap-6"),
                ),
                Form(
                    Input(type="hidden", name="enabled", value="0"),
                    Label(
                        Switch(
                            name="enabled",
                            value="1",
                            checked=bool(admin["enabled"]) or None,
                            id=f"admin-enabled-{admin['id']}",
                            onchange="this.form.requestSubmit()",
                        ),
                        Span("Enabled" if admin["enabled"] else "Disabled"),
                        fr=f"admin-enabled-{admin['id']}",
                        cls=(FlexT.inline, FlexT.middle, "w-fit cursor-pointer gap-3"),
                    ),
                    method="post",
                    action=f"/admin/accounts/{admin['id']}/enabled",
                ),
            )
        )
    return document(
        "Admin accounts | FastPrize",
        page_header("Admins"),
        P(billing_anchor(), "Manage billing for this FastPrize."),
        status_banner(message, tone),
        Card(
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
                Button("Add admin", type="submit", cls=(ButtonT.primary, "self-start")),
                method="post",
                action="/admin/accounts",
                cls=(FlexT.block, FlexT.column, "gap-6"),
                id="admin-add-form",
            ),
        ),
        Grid(*rows, cols_sm=1, cols_md=2, cols_lg=2, cols_xl=2, cls="gap-8"),
        event_id=selected_event["id"] if selected_event else None,
        event_name=selected_event["name"] if selected_event else None,
        active_link="accounts",
    )


def _password_fields(prefix: str):
    return (
        Input(
            id=f"{prefix}-password",
            name="password",
            type="password",
            autocomplete="new-password",
            required=True,
            minlength="12",
            placeholder="Password",
            aria_label="Password",
        ),
        Input(
            id=f"{prefix}-confirmation",
            name="confirmation",
            type="password",
            autocomplete="new-password",
            required=True,
            minlength="12",
            placeholder="Confirm password",
            aria_label="Confirm password",
        ),
    )


def _setup_page(
    req: Request,
    message: str = "",
    token: str = "",
    email: str = "",
):
    if token:
        token_input = Input(type="hidden", name="token", value=token)
    else:
        token_input = Input(
            id="setup-token",
            name="token",
            required=True,
            autocomplete="off",
            placeholder="Setup token",
            aria_label="Setup token",
        )
    return document(
        "Claim FastPrize",
        Div(
            _login_brand(),
            Card(
                H1("Claim this FastPrize"),
                P(
                    "Choose the admin email and password for this instance. "
                    "This setup link works once."
                ),
                status_banner(message, "error"),
                Form(
                    Input(type="hidden", name="csrf", value=csrf_token(req)),
                    token_input,
                    Input(
                        id="setup-email",
                        name="email",
                        type="email",
                        autocomplete="username",
                        required=True,
                        value=email or None,
                        placeholder="Email",
                        aria_label="Email",
                    ),
                    *_password_fields("setup"),
                    Button(
                        "Save admin",
                        type="submit",
                        cls=(ButtonT.primary, "self-start"),
                    ),
                    method="post",
                    action="/setup",
                    cls=(FlexT.block, FlexT.column, "gap-6"),
                ),
                cls="w-full max-w-md",
            ),
            cls="login-intro",
        ),
        login_page=True,
    )


def _setup_closed_page(req: Request, message: str = ""):
    return document(
        "FastPrize setup",
        Div(
            _login_brand(),
            Card(
                H1("This FastPrize is already set up"),
                status_banner(message, "error"),
                P(A("Sign in", href="/login"), " with the admin account for this instance."),
                cls="w-full max-w-md",
            ),
            cls="login-intro",
        ),
        login_page=True,
    )


def _forgot_page(req: Request, message: str = "", tone: str = "info"):
    if resend_api_key():
        body = (
            status_banner(message, tone),
            Form(
                Input(type="hidden", name="csrf", value=csrf_token(req)),
                Input(
                    id="reset-email",
                    name="email",
                    type="email",
                    autocomplete="username",
                    required=True,
                    placeholder="Email",
                    aria_label="Email",
                ),
                Button(
                    "Send reset link",
                    type="submit",
                    cls=(ButtonT.primary, "self-start"),
                ),
                method="post",
                action="/forgot-password",
                cls=(FlexT.block, FlexT.column, "gap-6"),
            ),
        )
    else:
        body = (P(_RESET_UNAVAILABLE),)
    return document(
        "Reset password | FastPrize",
        Div(
            _login_brand(),
            Card(
                H1("Reset password"),
                *body,
                A("Back to sign in", href="/login"),
                cls="w-full max-w-md",
            ),
            cls="login-intro",
        ),
        login_page=True,
    )


def _reset_page(req: Request, message: str = "", token: str = ""):
    form = ""
    if token:
        form = Form(
            Input(type="hidden", name="csrf", value=csrf_token(req)),
            Input(type="hidden", name="token", value=token),
            *_password_fields("reset"),
            Button(
                "Update password",
                type="submit",
                cls=(ButtonT.primary, "self-start"),
            ),
            method="post",
            action="/reset-password",
            cls=(FlexT.block, FlexT.column, "gap-6"),
        )
    return document(
        "Choose a new password | FastPrize",
        Div(
            _login_brand(),
            Card(
                H1("Choose a new password"),
                status_banner(message, "error"),
                form,
                cls="w-full max-w-md",
            ),
            cls="login-intro",
        ),
        login_page=True,
    )


def _deliver_password_reset(store, req: Request, email: str) -> None:
    if "@" not in login_rate_subject(email):
        return
    now = time.time()
    if store.password_reset_is_limited(email, now):
        return
    store.record_password_reset_attempt(email, now)
    admin = store.get_admin_by_email(email)
    if admin is None or not admin["enabled"]:
        return
    base = resolve_public_base_url(req)
    if not base:
        logger.warning(
            "Password reset email skipped; no safe public base URL is configured"
        )
        return
    token, idempotency_key = store.issue_password_reset(admin["id"])
    send_password_reset_email(
        to=admin["email"],
        reset_url=f"{base}/reset-password?token={quote(token)}",
        idempotency_key=idempotency_key,
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
            if req.query_params.get("reset") == "1":
                return _login_page(
                    req,
                    "Password updated. Sign in with your new password.",
                    is_safe_return_path(next),
                    tone="info",
                )
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
            return _accounts_page(req, str(error), "error")
        return _accounts_page(req, "Admin account created.")

    @rt("/admin/accounts/{admin_id}/enabled", methods=["POST"])
    async def account_set_enabled(req: Request, admin_id: int):
        form = await req.form()
        enabled = "1" in {str(value) for value in form.getlist("enabled")}
        updated = store.set_admin_enabled(admin_id, enabled)
        if not updated:
            return _accounts_page(
                req, "The final enabled admin cannot be disabled.", "error"
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
                return _accounts_page(req, "Admin account not found.", "error")
            return _accounts_page(
                req, "The final enabled admin cannot be deleted.", "error"
            )
        if current and current["id"] == admin_id:
            clear_session(req.session)
            return RedirectResponse("/login", status_code=303)
        return _accounts_page(req, "Admin account deleted.")

    @rt("/admin/accounts/{admin_id}/password", methods=["POST"])
    def account_reset_password(req: Request, admin_id: int, password: str):
        try:
            password_hash = hash_password(password)
        except ValueError as error:
            return _accounts_page(req, str(error), "error")
        if not store.update_admin_password(admin_id, password_hash):
            return _accounts_page(req, "Admin account not found.", "error")
        return _accounts_page(req, "Password reset. That account must sign in again.")

    @rt("/setup", methods=["GET", "POST"])
    def setup_claim(
        req: Request,
        token: str = "",
        email: str = "",
        password: str = "",
        confirmation: str = "",
        csrf: str = "",
    ):
        if store.setup_status() != "pending":
            if store.admin_count() == 0:
                return RedirectResponse("/login", status_code=303)
            if req.method == "POST":
                return _setup_closed_page(req, _SETUP_REJECTED)
            return _setup_closed_page(req)
        if req.method == "GET":
            return _setup_page(req, token=token)
        if not _csrf_matches(req, csrf):
            return _setup_page(
                req,
                "Could not claim this instance. Try again.",
                token=token,
                email=email,
            )
        if password != confirmation:
            return _setup_page(
                req,
                "Passwords did not match.",
                token=token,
                email=email,
            )
        try:
            password_hash = hash_password(password)
        except ValueError as error:
            return _setup_page(req, str(error), token=token, email=email)
        try:
            admin = store.claim_setup(token, email, password_hash)
        except SetupClaimError:
            return _setup_page(req, _SETUP_REJECTED, token=token, email=email)
        except ValueError as error:
            return _setup_page(req, str(error), token=token, email=email)
        establish_session(req.session, admin)
        return RedirectResponse("/", status_code=303)

    @rt("/forgot-password", methods=["GET", "POST"])
    def forgot_password(req: Request, email: str = "", csrf: str = ""):
        if req.method == "GET" or not resend_api_key():
            return _forgot_page(req)
        if not _csrf_matches(req, csrf):
            return _forgot_page(
                req,
                "Could not send a reset link. Try again.",
                "error",
            )
        _deliver_password_reset(store, req, email)
        return _forgot_page(req, _RESET_SENT)

    @rt("/reset-password", methods=["GET", "POST"])
    def reset_password(
        req: Request,
        token: str = "",
        password: str = "",
        confirmation: str = "",
        csrf: str = "",
    ):
        if req.method == "GET":
            if not token:
                return _reset_page(req, _RESET_REJECTED)
            return _reset_page(req, token=token)
        if not _csrf_matches(req, csrf):
            return _reset_page(
                req,
                "Could not update the password. Try again.",
                token=token,
            )
        if password != confirmation:
            return _reset_page(req, "Passwords did not match.", token=token)
        try:
            password_hash = hash_password(password)
        except ValueError as error:
            return _reset_page(req, str(error), token=token)
        if not store.reset_password_with_token(token, password_hash):
            return _reset_page(req, _RESET_REJECTED)
        return RedirectResponse("/login?reset=1", status_code=303)
