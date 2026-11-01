"""Test a configured R2 bucket from the command line.

    python manage.py r2_check                     # every bucket
    python manage.py r2_check --bucket course-art # one bucket, by name
    python manage.py r2_check --write             # also upload and delete a probe

The test never changes the bucket unless ``--write`` is passed, and even then it
removes what it wrote.
"""

from django.core.management.base import BaseCommand, CommandError

from objectstore.models import R2Bucket
from objectstore.services import test_bucket


class Command(BaseCommand):
    help = "Run the Cloudflare R2 connection test for configured buckets."

    def add_arguments(self, parser):
        parser.add_argument("--bucket", help="Only this bucket name.")
        parser.add_argument(
            "--write",
            action="store_true",
            help="Also upload a 17-byte probe object and delete it again.",
        )

    def handle(self, *args, **options):
        buckets = R2Bucket.objects.select_related("account", "account__owner")
        if options["bucket"]:
            buckets = buckets.filter(name=options["bucket"])
            if not buckets.exists():
                raise CommandError(f"No bucket named {options['bucket']!r} is configured.")
        if not buckets:
            raise CommandError(
                "No R2 buckets are configured. Add one in the admin under Storage."
            )

        failures = 0
        for bucket in buckets:
            verdict = test_bucket(bucket, write=options["write"])
            mark = "OK  " if verdict.ok else "FAIL"
            self.stdout.write(f"[{mark}] {bucket.account.owner} / {bucket.account.name} / {bucket.name}")
            self.stdout.write(f"        {verdict.message}")
            if not verdict.ok:
                failures += 1

        if failures:
            raise CommandError(f"{failures} bucket(s) failed the connection test.")
        self.stdout.write(self.style.SUCCESS(f"{buckets.count()} bucket(s) connected."))
