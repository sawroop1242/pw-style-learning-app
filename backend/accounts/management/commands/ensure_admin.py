"""Create the first administrator from environment variables, once.

A hosted deployment has no terminal to run ``createsuperuser`` in, and a
superuser created by hand drifts from whatever the deployment believes. This
command makes the account part of the deployment instead:

    ADMIN_USERNAME=admin
    ADMIN_EMAIL=you@example.com
    ADMIN_PASSWORD=<a real password>

It is **idempotent and non-destructive**: if the account exists it is only
promoted (staff, superuser, ``main_admin`` role) and its password is left
alone, so an administrator who changes their password in the UI keeps it
across deploys. To rotate deliberately, pass ``--set-password``.

With no ``ADMIN_PASSWORD`` the command does nothing and succeeds, so a build
without the secret still completes.

Usage::

    python manage.py ensure_admin
    python manage.py ensure_admin --set-password
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile, Role

User = get_user_model()


class Command(BaseCommand):
    help = "Create or promote the main administrator from ADMIN_* env vars."

    def add_arguments(self, parser):
        parser.add_argument(
            "--set-password",
            action="store_true",
            help="Reset the password of an existing account to ADMIN_PASSWORD.",
        )

    def handle(self, *args, **options):
        username = (os.getenv("ADMIN_USERNAME") or "admin").strip()
        email = (os.getenv("ADMIN_EMAIL") or "").strip()
        password = os.getenv("ADMIN_PASSWORD") or ""

        user = User.objects.filter(username=username).first()

        if user is None:
            if not password:
                self.stdout.write(
                    "ensure_admin: ADMIN_PASSWORD is not set; no administrator was created."
                )
                return
            user = User.objects.create_user(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"ensure_admin: created administrator “{username}”."))
        elif password and options["set_password"]:
            user.set_password(password)
            self.stdout.write(f"ensure_admin: reset the password of “{username}”.")
        else:
            self.stdout.write(f"ensure_admin: “{username}” already exists; left the password alone.")

        changed = []
        for field, wanted in (("is_staff", True), ("is_superuser", True), ("is_active", True)):
            if getattr(user, field) != wanted:
                setattr(user, field, wanted)
                changed.append(field)
        if email and user.email != email:
            user.email = email
            changed.append("email")
        if changed:
            user.save(update_fields=changed)

        with transaction.atomic():
            profile, _ = Profile.objects.get_or_create(user=user)
            if profile.role != Role.MAIN_ADMIN:
                profile.role = Role.MAIN_ADMIN
                profile.save(update_fields=["role", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"ensure_admin: “{username}” can open /admin/ as a main administrator."
            )
        )
