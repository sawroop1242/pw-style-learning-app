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

# backend path -> the setting that must hold its key
API_BACKENDS = {
    "accounts.mail_backends.BrevoEmailBackend": "BREVO_API_KEY",
    "accounts.mail_backends.ResendEmailBackend": "RESEND_API_KEY",
}

# The console (development) and the test backends print or collect the message
# locally; they never hand anything to a provider, so provider rules do not
# apply to them.
LOCAL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
}


def backend_label(backend):
    """`django.core.mail.backends.console.EmailBackend` -> `console`.

    Django's own backends are all named `<module>.EmailBackend`, so the class
    name carries no information there; the module does.
    """
    parts = backend.split(".")
    name = parts[-1]
    if name.endswith("EmailBackend"):
        name = name[: -len("EmailBackend")]
    if not name and len(parts) > 1:
        name = parts[-2]
    return name.lower()


def delivery_problem():
    """Return a short sentence if reset mail cannot be delivered, else None.

    Shared with the admin console so the same finding is visible in two places:
    the deploy log (`manage.py check`) and the front page of the admin, where
    somebody about to send their first reset code will see it.
    """
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if backend == SMTP_BACKEND and not getattr(settings, "EMAIL_HOST", "").strip():
        return (
            "Email delivery is not configured: EMAIL_HOST is empty, so password-reset "
            "codes cannot be sent. Add EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, "
            "EMAIL_HOST_PASSWORD and DEFAULT_FROM_EMAIL — or set BREVO_API_KEY to "
            "send through Brevo instead — then run "
            "manage.py check_email --to you@example.com."
        )
    if backend in API_BACKENDS:
        key_name = API_BACKENDS[backend]
        if not (getattr(settings, key_name, "") or "").strip():
            return (
                f"Email delivery is not configured: {key_name} is empty, so "
                "password-reset codes cannot be sent. Add the key in the hosting "
                "environment, then run manage.py check_email --to you@example.com."
            )
    if (
        backend in LOCAL_BACKENDS
        and getattr(settings, "ENVIRONMENT", "development") in {"production", "staging"}
    ):
        # A deployed app on a backend that only prints or collects messages
        # accepts every reset request and delivers none of them.
        short = backend_label(backend)
        return (
            f"Email delivery is not configured: EMAIL_BACKEND is the {short} backend, which sends "
            "nothing outside this machine, so password-reset codes never leave the "
            "app. Set BREVO_API_KEY (or the SMTP settings) in the hosting environment."
        )
    return None


@register()
def email_delivery_configured(app_configs, **kwargs):
    """Warn when password-reset mail cannot possibly be delivered."""
    backend = getattr(settings, "EMAIL_BACKEND", "")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or ""
    problems = []

    if backend == SMTP_BACKEND and not getattr(settings, "EMAIL_HOST", "").strip():
        problems.append(
            Warning(
                "EMAIL_HOST is empty, so Django will try to deliver mail through "
                "localhost:587 and every send will fail.",
                hint=(
                    "Password-reset codes are emailed, so without a host the reset "
                    "flow cannot work. Set EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, "
                    "EMAIL_HOST_PASSWORD and DEFAULT_FROM_EMAIL — or set BREVO_API_KEY "
                    "and let the HTTPS backend do it — then run "
                    "`python manage.py check_email --to you@example.com` to prove it."
                ),
                id="accounts.W001",
            )
        )

    if backend in API_BACKENDS:
        key_name = API_BACKENDS[backend]
        if not (getattr(settings, key_name, "") or "").strip():
            problems.append(
                Warning(
                    f"{backend.rsplit('.', 1)[-1]} is selected but {key_name} is empty, "
                    "so every password-reset email will fail.",
                    hint=(
                        f"Add {key_name} to the hosting environment. `manage.py "
                        "check_email` explains which provider it belongs to."
                    ),
                    id="accounts.W003",
                )
            )

    # Only meaningful when something is handed to a real provider: the console
    # backend prints the letter to the terminal and does not care what the
    # sender looks like.
    if backend not in LOCAL_BACKENDS and (
        "@studyspace.local" in from_email or from_email.endswith(".local>")
    ):
        problems.append(
            Warning(
                f"DEFAULT_FROM_EMAIL is still the placeholder ({from_email!r}), which "
                "real mail providers reject.",
                hint=(
                    "Set DEFAULT_FROM_EMAIL to a mailbox the provider has verified — "
                    "for Brevo that is the address you confirmed in its dashboard; for "
                    "Resend it must be on a verified domain."
                ),
                id="accounts.W002",
            )
        )

    if (
        backend in LOCAL_BACKENDS
        and getattr(settings, "ENVIRONMENT", "development") in {"production", "staging"}
    ):
        problems.append(
            Warning(
                f"EMAIL_BACKEND is the {backend_label(backend)} backend in a deployed "
                "environment, so password-reset mail is never sent.",
                hint=(
                    "Set BREVO_API_KEY (simplest) or the EMAIL_HOST/EMAIL_HOST_USER/"
                    "EMAIL_HOST_PASSWORD trio in the hosting environment."
                ),
                id="accounts.W004",
            )
        )

    return problems


@register()
def shared_cache_configured(app_configs, **kwargs):
    """Warn when throttles are counted in per-process memory.

    A limit enforced in one worker's memory is not a limit: two workers, or two
    serverless instances, each grant the full allowance. The app checks stay as
    they are — they are cheap and catch a single hot client — but they cannot
    be the only defence in a deployment with more than one process.
    """
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if "locmem" not in backend.lower():
        return []

    if getattr(settings, "ENVIRONMENT", "development") not in {"production", "staging"}:
        return []

    return [
        Warning(
            "Throttle counters live in this process's memory (locmem cache), so "
            "each worker or serverless instance grants the full rate limit again.",
            hint=(
                "Set REDIS_URL (or CACHE_URL) to a shared Redis instance — Upstash "
                "works and is a single environment variable — then redeploy. "
                "Login, OTP, registration and attempt-start limits all count "
                "through this cache."
            ),
            id="accounts.W005",
        )
    ]
