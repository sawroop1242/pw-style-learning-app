"""Startup checks for the parts that fail silently at runtime.

A password-reset code is generated, stored and then mailed inside a single
request. If the mail transport is missing, every one of those requests still
returns the generic "a code has been sent" message — the person waits for a
mail that will never arrive and there is nothing in the response to say so.
That is how the deployment ran with no SMTP host at all: `EMAIL_HOST` defaulted
to an empty string, so Django opened a connection to localhost and the error was
caught and logged.

`manage.py check` runs on every deploy (tools/vercel-build.sh), so a warning
here lands in the build log at the moment it matters.
"""

from django.conf import settings
from django.core.checks import Warning, register

SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"


def delivery_problem():
    """Return a short sentence if reset mail cannot be delivered, else None.

    Shared with the admin console so the same finding is visible in two places:
    the deploy log (`manage.py check`) and the front page of the admin, where
    somebody about to send their first reset code will see it.
    """
    if getattr(settings, "EMAIL_BACKEND", "") == SMTP_BACKEND and not getattr(
        settings, "EMAIL_HOST", ""
    ).strip():
        return (
            "Email delivery is not configured: EMAIL_HOST is empty, so password-reset "
            "codes cannot be sent. Add EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, "
            "EMAIL_HOST_PASSWORD and DEFAULT_FROM_EMAIL, then run "
            "manage.py check_email --to you@example.com."
        )
    return None


@register()
def email_delivery_configured(app_configs, **kwargs):
    """Warn when password-reset mail cannot possibly be delivered."""
    problems = []

    if delivery_problem():
        problems.append(
            Warning(
                "EMAIL_HOST is empty, so Django will try to deliver mail through "
                "localhost:587 and every send will fail.",
                hint=(
                    "Password-reset codes are emailed, so without a host the reset "
                    "flow cannot work. Set EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, "
                    "EMAIL_HOST_PASSWORD and DEFAULT_FROM_EMAIL, then run "
                    "`python manage.py check_email --to you@example.com` to prove it."
                ),
                id="accounts.W001",
            )
        )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
    # Only meaningful when something is actually being handed to a provider: the
    # console backend used in development prints the message to the terminal and
    # does not care what the sender looks like.
    if getattr(settings, "EMAIL_BACKEND", "") == SMTP_BACKEND and (
        "@studyspace.local" in from_email or from_email.endswith(".local>")
    ):
        problems.append(
            Warning(
                f"DEFAULT_FROM_EMAIL is still the placeholder ({from_email!r}), which "
                "real mail providers reject.",
                hint="Set DEFAULT_FROM_EMAIL to a mailbox on a domain you can send from.",
                id="accounts.W002",
            )
        )

    return problems
