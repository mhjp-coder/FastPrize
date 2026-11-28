import json
import logging
import urllib.error
import urllib.request
from html import escape

from fastprize.config import resend_api_key, resend_from
from fastprize.store import PASSWORD_RESET_TTL

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"


def send_resend_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    idempotency_key: str,
) -> bool:
    api_key = resend_api_key()
    if not api_key:
        return False
    payload = {
        "from": resend_from(),
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    request = urllib.request.Request(
        RESEND_EMAILS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "User-Agent": "fastprize",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
            return 200 <= response.status < 300
    except urllib.error.HTTPError as error:
        error.read()
        logger.warning("Resend rejected a password reset email (%s)", error.code)
        return False
    except urllib.error.URLError:
        logger.warning("Resend could not be reached for a password reset email")
        return False


def send_password_reset_email(*, to: str, reset_url: str, idempotency_key: str) -> bool:
    safe_url = escape(reset_url, quote=True)
    minutes = int(PASSWORD_RESET_TTL.total_seconds() // 60)
    text = (
        "A password reset was requested for your FastPrize admin account.\n\n"
        "Reset your password. This link expires in "
        f"{minutes} minutes and works once:\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html = (
        "<p>A password reset was requested for your FastPrize admin account.</p>"
        f'<p><a href="{safe_url}">Reset your password</a></p>'
        f"<p>This link expires in {minutes} minutes and works once. "
        "If you did not request this, you can ignore this email.</p>"
    )
    return send_resend_email(
        to=to,
        subject="Reset your FastPrize password",
        html=html,
        text=text,
        idempotency_key=idempotency_key,
    )
