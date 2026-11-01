"""Rotate the key that encrypts stored R2 credentials.

Usage::

    python manage.py r2_rotate_key                 # dry run: say what would change
    python manage.py r2_rotate_key --new-key       # print a fresh key, change nothing
    python manage.py r2_rotate_key --apply         # re-encrypt every stored secret

The safe order is: run ``--new-key``, put the printed key at the *front* of
``R2_CREDENTIAL_KEYS`` (the old key stays after it), deploy, run ``--apply``,
then remove the old key. Until ``--apply`` has finished, values written with
the old key still decrypt because it is still in the list.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from objectstore import crypto
from objectstore.models import R2Account


class Command(BaseCommand):
    help = "Re-encrypt stored Cloudflare R2 credentials with the active key."

    def add_arguments(self, parser):
        parser.add_argument(
            "--new-key",
            action="store_true",
            help="Print a new key to put at the front of R2_CREDENTIAL_KEYS, then exit.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually rewrite the stored credentials (default is a dry run).",
        )

    def handle(self, *args, **options):
        if options["new_key"]:
            self.stdout.write(crypto.generate_key())
            self.stdout.write(
                "Add that string first in R2_CREDENTIAL_KEYS, redeploy, then run "
                "this command with --apply."
            )
            return

        accounts = R2Account.objects.exclude(access_key_id_enc="")
        if not accounts:
            self.stdout.write("No stored credentials — nothing to rotate.")
            return

        rotated = failed = 0
        for account in accounts:
            try:
                access = crypto.decrypt(account.access_key_id_enc)
                secret = crypto.decrypt(account.secret_access_key_enc)
            except crypto.CredentialError:
                failed += 1
                self.stderr.write(
                    f"{account.name}: cannot decrypt with the configured keys — "
                    "re-enter its API token in the admin."
                )
                continue

            if not options["apply"]:
                rotated += 1
                continue

            with transaction.atomic():
                account.access_key_id_enc = crypto.encrypt(access)
                account.secret_access_key_enc = crypto.encrypt(secret)
                account.save(update_fields=["access_key_id_enc", "secret_access_key_enc", "updated_at"])
            rotated += 1

        verb = "re-encrypted" if options["apply"] else "would be re-encrypted"
        self.stdout.write(f"{rotated} account(s) {verb}; {failed} could not be read.")
        if not options["apply"]:
            self.stdout.write("Dry run. Add --apply to write the new ciphertext.")
