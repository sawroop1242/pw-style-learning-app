"""Prove that this deployment can send mail, without waiting for a reset code.

`forgot-password` deliberately answers the same way whether or not the address
exists and whether or not the mail left the building, so the only place a broken
mail transport shows up is a log line nobody reads. This command closes that gap:

    python manage.py check_email                 # describe + connect only
    python manage.py check_email --to me@x.com   # connect, then really send

It prints the backend, host, port, encryption and sender, so a wrong port or a
missing password is visible immediately, and it exits non-zero when the
transport cannot be reached — which makes it usable as a post-deploy step.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Check the email transport the password-reset flow depends on."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            dest="to",
            default=None,
            help="Send a real test message to this address instead of only connecting.",
        )

    def handle(self, *args, **options):
        from accounts.checks import API_BACKENDS

        backend = getattr(settings, "EMAIL_BACKEND", "")
        host = getattr(settings, "EMAIL_HOST", "")
        port = getattr(settings, "EMAIL_PORT", "")
        use_tls = getattr(settings, "EMAIL_USE_TLS", False)
        use_ssl = getattr(settings, "EMAIL_USE_SSL", False)
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")
        timeout = getattr(settings, "EMAIL_TIMEOUT", None)

        is_smtp = "smtp" in backend
        key_name = API_BACKENDS.get(backend)
        key = (getattr(settings, key_name, "") or "").strip() if key_name else ""

        self.stdout.write(f"backend   {backend}")
        if is_smtp:
            self.stdout.write(f"host      {host or '(empty)'}:{port}")
            self.stdout.write(f"encryption {'SSL' if use_ssl else 'STARTTLS' if use_tls else 'none'}")
        if key_name:
            shown = f"set (…{key[-4:]})" if key else "(empty)"
            self.stdout.write(f"{key_name:<9} {shown}")
            self.stdout.write(
                "note      the sender address must be verified in the provider's dashboard"
            )
        self.stdout.write(f"timeout   {timeout if timeout is not None else 'unset'}")
        self.stdout.write(f"from      {from_email}")

        if is_smtp and not host.strip():
            raise CommandError(
                "EMAIL_HOST is empty: Django would connect to localhost and every "
                "send would fail. Set EMAIL_HOST/EMAIL_PORT/EMAIL_HOST_USER/"
                "EMAIL_HOST_PASSWORD/DEFAULT_FROM_EMAIL first, or set BREVO_API_KEY "
                "to send through Brevo instead."
            )
        if key_name and not key:
            raise CommandError(
                f"{key_name} is empty, so {backend.rsplit('.', 1)[-1]} cannot send "
                "anything. Create a key in the provider's dashboard and add it to "
                "the environment."
            )

        connection = get_connection(timeout=timeout)
        started = time.monotonic()
        try:
            connection.open()
        except Exception as error:  # noqa: BLE001 - any failure is the answer
            raise CommandError(
                f"could not open the mail connection ({type(error).__name__}: {error})"
            ) from error
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if key_name:
            provider = backend.rsplit(".", 1)[-1].replace("EmailBackend", "")
            self.stdout.write(
                self.style.SUCCESS(f"{provider} accepted the credentials in {elapsed_ms} ms")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"connected in {elapsed_ms} ms"))

        recipient = options.get("to")
        if not recipient:
            connection.close()
            self.stdout.write(
                "connected only. Pass --to you@example.com to send a real message."
            )
            return

        started = time.monotonic()
        try:
            send_mail(
                "StudySpace: test message",
                (
                    "This is a test message from `manage.py check_email`.\n\n"
                    "Password-reset codes travel this same path. If you can read "
                    "this, the reset flow can deliver mail."
                ),
                from_email,
                [recipient],
                fail_silently=False,
                connection=connection,
            )
        except Exception as error:  # noqa: BLE001
            raise CommandError(
                f"the connection opened but the message was refused "
                f"({type(error).__name__}: {error})"
            ) from error
        finally:
            connection.close()

        elapsed_ms = int((time.monotonic() - started) * 1000)
        if key_name:
            provider = backend.rsplit(".", 1)[-1].replace("EmailBackend", "")
            self.stdout.write(
                self.style.SUCCESS(f"{provider} accepted the message in {elapsed_ms} ms")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"message handed to the server in {elapsed_ms} ms")
            )
        self.stdout.write(
            "The server accepted it; whether it lands in the inbox is up to the "
            "provider's own logs."
        )
