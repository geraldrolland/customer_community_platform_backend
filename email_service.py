"""Email delivery for account verification.

Sends the email-verification message via SMTP. When SMTP is not
configured the service falls back to logging the verification link so
development flows can still complete.
"""
import logging
import smtplib
from email.message import EmailMessage

from core.settings import settings

logger = logging.getLogger(__name__)


def send_verification_email(to_email: str, first_name: str, verification_url: str) -> None:
    """Send an email-verification message to a newly registered user.

    Args:
        to_email: Recipient email address.
        first_name: Recipient's first name, used in the greeting.
        verification_url: Signed verification link to include in the email.

    Returns:
        None. Failures are logged, never raised, so registration is not
        blocked by email delivery problems.
    """
    if not settings.SMTP_HOST:
        logger.warning(
            "SMTP not configured - verification link for %s: %s",
            to_email,
            verification_url,
        )
        return

    message = EmailMessage()
    message["Subject"] = "Verify your email address"
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = to_email
    message.set_content(
        f"Hi {first_name},\n\n"
        f"Please verify your email address by clicking the link below. "
        f"The link expires in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES} minutes.\n\n"
        f"{verification_url}\n\n"
        f"If you did not create an account, you can ignore this email."
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASS:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.send_message(message)
        logger.info("Verification email sent to %s", to_email)
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)
