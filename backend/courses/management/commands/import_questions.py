"""Create or update a whole test from one CSV file.

This is the practical way to build a full-length paper: the staff API creates
one question per request, which is fine for a demo and useless for a 100
question mock.

Usage::

    # print the template (the same bytes the API serves)
    python manage.py import_questions --template

    # check a file without writing anything
    python manage.py import_questions --quiz 12 --file questions.csv --dry-run

    # import it, appending after the existing questions
    python manage.py import_questions --quiz 12 --file questions.csv

    # replace a test that has no attempts yet
    python manage.py import_questions --quiz 12 --file questions.csv --mode replace

    # export an existing test back to CSV (round-trips)
    python manage.py import_questions --quiz 12 --export questions.csv

The command prints the same row-level errors the API returns, and imports
nothing at all if any row is invalid.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from courses import csv_import
from courses.models import Quiz


class Command(BaseCommand):
    help = "Validate and import a question CSV into a test (schema v1)."

    def add_arguments(self, parser):
        parser.add_argument("--quiz", type=int, help="Target test (Quiz) id.")
        parser.add_argument("--file", type=Path, help="Local CSV path.")
        parser.add_argument("--url", help="HTTPS URL of the CSV (SSRF-guarded fetch).")
        parser.add_argument(
            "--mode",
            choices=("append", "replace"),
            default="append",
            help="append (default) keeps existing questions; replace deletes them first.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and print the preview without writing anything.",
        )
        parser.add_argument(
            "--allow-replace-with-attempts",
            action="store_true",
            help="DESTRUCTIVE: allow replace on a test that already has attempts.",
        )
        parser.add_argument("--template", action="store_true", help="Print the CSV template and exit.")
        parser.add_argument("--export", type=Path, help="Write this test's questions to a CSV file and exit.")

    def handle(self, *args, **options):
        if options["template"]:
            self.stdout.write(csv_import.template_csv(), ending="")
            return

        quiz_id = options.get("quiz")
        if not quiz_id:
            raise CommandError("Pass --quiz <id> (or --template to print the template).")
        try:
            quiz = Quiz.objects.get(pk=quiz_id)
        except Quiz.DoesNotExist as error:
            raise CommandError(f"No test with id {quiz_id}.") from error

        if options.get("export"):
            path = options["export"]
            path.write_text(csv_import.export_quiz_csv(quiz), encoding="utf-8")
            self.stdout.write(
                self.style.SUCCESS(f"Wrote {quiz.questions.count()} questions to {path}.")
            )
            return

        source_file = options.get("file")
        source_url = options.get("url")
        if bool(source_file) == bool(source_url):
            raise CommandError("Pass exactly one of --file or --url.")

        try:
            if source_file:
                try:
                    text = source_file.read_text(encoding="utf-8-sig")
                except OSError as error:
                    raise CommandError(f"Could not read {source_file}: {error}") from error
            else:
                text = csv_import.fetch_csv(source_url)
            report = csv_import.parse_questions_csv(text)
        except csv_import.CsvImportError as error:
            raise CommandError(str(error)) from error

        self._print_report(quiz, report, options["mode"])

        if report.errors:
            raise CommandError(
                f"{report.error_count} row error(s); nothing was imported. Fix the file and run again."
            )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: nothing was written."))
            return

        try:
            imported = csv_import.import_questions(
                quiz,
                report,
                mode=options["mode"],
                allow_replace_with_attempts=options["allow_replace_with_attempts"],
            )
        except csv_import.ImportBlocked as error:
            raise CommandError(str(error)) from error

        total = quiz.questions.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported} question(s) into '{quiz.title}' ({options['mode']}); "
                f"the test now has {total}."
            )
        )

    # ------------------------------------------------------------------ #

    def _print_report(self, quiz, report, mode):
        self.stdout.write(f"Test: {quiz.title} (id={quiz.id}) — mode: {mode}")
        self.stdout.write(
            f"Schema v{csv_import.SCHEMA_VERSION} · {report.total_rows} data row(s) · "
            f"{report.valid_rows} valid · {report.error_count} error(s) · "
            f"{len(report.warnings)} warning(s)"
        )

        for warning in report.warnings[:10]:
            self.stdout.write(self.style.WARNING(f"  row {warning.row}: {warning.message}"))

        if report.errors:
            self.stdout.write(self.style.ERROR("Errors:"))
            for problem in report.errors[:50]:
                where = f" ({problem.column})" if problem.column else ""
                self.stdout.write(self.style.ERROR(f"  row {problem.row}{where}: {problem.message}"))
            if report.error_count > 50:
                self.stdout.write(self.style.ERROR(f"  … and {report.error_count - 50} more"))
            return

        self.stdout.write("Preview (first 10):")
        for row in report.preview(limit=10):
            prompt = row["prompt"] if len(row["prompt"]) <= 70 else row["prompt"][:67] + "…"
            self.stdout.write(
                f"  {row['row']:>4}  {row['section'][:14]:<14} {row['correct_option']:<4} {prompt}"
            )
