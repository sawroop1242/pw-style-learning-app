"""The deployment bootstrap: one administrator, created once, never clobbered.

A hosted build has no terminal, so the account that opens ``/admin/`` has to
come from the environment. These tests pin the two properties that matter: it
creates the account with the right role, and a redeploy does not undo an
administrator's password change.
"""

import os
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from accounts.models import Role

User = get_user_model()


def run(**env):
    out = StringIO()
    with mock.patch.dict(os.environ, env, clear=False):
        call_command("ensure_admin", stdout=out)
    return out.getvalue()


class EnsureAdminTests(TestCase):
    def test_creates_a_main_admin(self):
        run(ADMIN_USERNAME="deploy_admin", ADMIN_EMAIL="d@example.com", ADMIN_PASSWORD="Deploy-pass-123!")

        user = User.objects.get(username="deploy_admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "d@example.com")
        self.assertEqual(user.profile.role, Role.MAIN_ADMIN)
        self.assertTrue(user.check_password("Deploy-pass-123!"))

    def test_without_a_password_it_does_nothing(self):
        with mock.patch.dict(os.environ, {"ADMIN_PASSWORD": ""}, clear=False):
            run(ADMIN_USERNAME="no_password_admin")

        self.assertFalse(User.objects.filter(username="no_password_admin").exists())

    def test_a_redeploy_does_not_reset_the_password(self):
        run(ADMIN_USERNAME="kept_admin", ADMIN_PASSWORD="First-pass-123!")

        # The administrator changed their password in the UI; the next build
        # runs with the old secret still in the environment.
        User.objects.filter(username="kept_admin").update()
        user = User.objects.get(username="kept_admin")
        user.set_password("Changed-in-ui-9!")
        user.save()

        run(ADMIN_USERNAME="kept_admin", ADMIN_PASSWORD="First-pass-123!")

        user.refresh_from_db()
        self.assertTrue(user.check_password("Changed-in-ui-9!"))

    def test_promotes_an_existing_account(self):
        User.objects.create_user(username="promote_me", password="Whatever-123!")

        run(ADMIN_USERNAME="promote_me")

        user = User.objects.get(username="promote_me")
        self.assertTrue(user.is_staff and user.is_superuser)
        self.assertEqual(user.profile.role, Role.MAIN_ADMIN)
