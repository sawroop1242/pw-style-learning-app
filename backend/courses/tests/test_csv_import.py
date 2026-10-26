"""The question CSV contract (schema v1) and the import path built on it.

These tests exist because the previous importer was a stub: `validate` fetched
nothing and `confirm_import` flipped a flag, so a "big test" could only be built
one question at a time. Each test below pins one rule that makes bulk authoring
safe — the column contract, all-or-nothing writes, and history protection.
"""

import csv
import io
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from courses import csv_import
from courses.models import (
    AttemptAnswer,
    Choice,
    Course,
    CsvImportJob,
    Question,
    Quiz,
    QuizAttempt,
)

User = get_user_model()


def csv_text(*rows, header=None):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header or csv_import.COLUMN_NAMES)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def good_row(**overrides):
    row = {
        "section": "Reasoning",
        "question_type": "single_choice",
        "question_text": "Which number completes 3, 6, 12, 24?",
        "option_a": "36",
        "option_b": "48",
        "option_c": "30",
        "option_d": "42",
        "option_e": "",
        "correct_option": "B",
        "explanation": "Each term doubles.",
        "marks": "2",
        "negative_marks": "0.5",
        "difficulty": "easy",
    }
    row.update(overrides)
    return [row[name] for name in csv_import.COLUMN_NAMES]


class ParserTests(TestCase):
    """Pure parsing: no database, no network."""

    def test_template_is_itself_valid(self):
        """The shipped template must parse cleanly, or the contract is a lie."""
        report = csv_import.parse_questions_csv(csv_import.template_csv())

        self.assertEqual(report.error_count, 0, report.errors)
        self.assertEqual(report.valid_rows, 2)
        self.assertEqual(report.questions[0].section, "Reasoning")
        self.assertEqual(report.questions[1].question_type, "multiple_choice")
        self.assertEqual(report.questions[1].correct_indexes, [0, 1])

    def test_header_can_be_a_subset_but_never_a_stranger(self):
        subset = ["question_text", "option_a", "option_b", "correct_option"]
        report = csv_import.parse_questions_csv(
            csv_text(["2 + 2?", "3", "4", "B"], header=subset)
        )
        self.assertEqual(report.valid_rows, 1)

        with self.assertRaises(csv_import.CsvImportError) as caught:
            csv_import.parse_questions_csv(
                csv_text(["2 + 2?", "3", "4", "B"], header=subset + ["answer_key"])
            )
        self.assertIn("answer_key", str(caught.exception))
        self.assertIn("Supported columns", str(caught.exception))

    def test_missing_required_column_is_rejected(self):
        with self.assertRaises(csv_import.CsvImportError) as caught:
            csv_import.parse_questions_csv(
                csv_text(["2 + 2?", "4", "B"], header=["question_text", "option_a", "correct_option"])
            )
        self.assertIn("option_b", str(caught.exception))

    def test_duplicate_column_is_rejected(self):
        with self.assertRaises(csv_import.CsvImportError):
            csv_import.parse_questions_csv(
                csv_text(
                    ["q", "a", "b", "A"],
                    header=["question_text", "option_a", "option_b", "question_text"],
                )
            )

    def test_row_errors_are_reported_with_row_numbers(self):
        report = csv_import.parse_questions_csv(
            csv_text(
                good_row(),
                good_row(question_text=""),
                good_row(correct_option="Z"),
                good_row(question_type="essay"),
                good_row(difficulty="impossible"),
                good_row(marks="lots"),
            )
        )
        self.assertEqual(report.valid_rows, 1)
        rows = sorted({problem.row for problem in report.errors})
        self.assertEqual(rows, [3, 4, 5, 6, 7])
        codes = {problem.code for problem in report.errors}
        self.assertTrue({"missing_prompt", "bad_correct_key", "bad_question_type",
                         "bad_difficulty", "bad_number"} <= codes)

    def test_correct_option_must_name_a_present_option(self):
        report = csv_import.parse_questions_csv(
            csv_text(good_row(option_c="", option_d="", correct_option="C"))
        )
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.errors[0].code, "correct_without_option")

    def test_options_must_be_contiguous(self):
        """A gap would silently shift the letters and mis-score the paper."""
        report = csv_import.parse_questions_csv(
            csv_text(good_row(option_c="", option_d="42"))
        )
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.errors[0].code, "option_gap")

    def test_single_choice_rejects_two_answers(self):
        report = csv_import.parse_questions_csv(csv_text(good_row(correct_option="A|B")))
        self.assertEqual(report.errors[0].code, "too_many_correct")

    def test_multiple_choice_accepts_pipe_and_comma(self):
        for separator in ("|", ","):
            report = csv_import.parse_questions_csv(
                csv_text(good_row(question_type="multiple_choice", correct_option=f"A{separator}C"))
            )
            self.assertEqual(report.error_count, 0, report.errors)
            self.assertEqual(report.questions[0].correct_indexes, [0, 2])

    def test_true_false_needs_exactly_two_options(self):
        report = csv_import.parse_questions_csv(
            csv_text(good_row(question_type="true_false", option_c="30", option_d="42", correct_option="A"))
        )
        self.assertTrue(any(problem.code == "true_false_options" for problem in report.errors))

    def test_duplicate_prompts_inside_one_file_are_errors(self):
        report = csv_import.parse_questions_csv(
            csv_text(good_row(), good_row(question_text="  which number completes 3, 6, 12, 24?  "))
        )
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.errors[0].code, "duplicate_prompt")
        self.assertIn("row 2", report.errors[0].message)

    def test_blank_lines_are_skipped(self):
        text = csv_text(good_row()) + "\n\n"
        report = csv_import.parse_questions_csv(text)
        self.assertEqual(report.valid_rows, 1)
        self.assertEqual(report.error_count, 0)

    def test_blank_marks_inherit_the_test_default(self):
        report = csv_import.parse_questions_csv(csv_text(good_row(marks="", negative_marks="")))
        self.assertIsNone(report.questions[0].marks)
        self.assertIsNone(report.questions[0].negative_marks)

    def test_blank_section_defaults_to_general(self):
        report = csv_import.parse_questions_csv(csv_text(good_row(section="")))
        self.assertEqual(report.questions[0].section, "General")

    def test_digest_is_stable_and_content_addressed(self):
        first = csv_import.parse_questions_csv(csv_text(good_row()))
        second = csv_import.parse_questions_csv(csv_text(good_row()))
        changed = csv_import.parse_questions_csv(csv_text(good_row(option_a="35")))

        self.assertEqual(first.digest, second.digest)
        self.assertNotEqual(first.digest, changed.digest)
        self.assertEqual(len(first.digest), 64)

    def test_size_and_row_limits_are_enforced(self):
        too_many = csv_text(*[good_row(question_text=f"Q{i}") for i in range(csv_import.MAX_ROWS + 1)])
        with self.assertRaises(csv_import.CsvImportError):
            csv_import.parse_questions_csv(too_many)

    def test_header_only_file_is_rejected(self):
        with self.assertRaises(csv_import.CsvImportError):
            csv_import.parse_questions_csv(csv_text())

    def test_error_messages_do_not_echo_whole_question_text(self):
        long_prompt = "x" * 400
        report = csv_import.parse_questions_csv(csv_text(good_row(question_text=long_prompt * 20)))
        message = report.errors[0].message
        self.assertLess(len(message), 200)


class FetchGuardTests(TestCase):
    """The CSV is untrusted input fetched from a URL staff supply."""

    def test_plain_http_is_refused(self):
        with self.assertRaises(csv_import.CsvImportError):
            csv_import.fetch_csv("http://example.com/questions.csv")

    def test_private_and_loopback_hosts_are_refused(self):
        for url in (
            "https://127.0.0.1/q.csv",
            "https://localhost/q.csv",
            "https://169.254.169.254/latest/meta-data",
            "https://10.0.0.5/q.csv",
            "https://192.168.1.10/q.csv",
        ):
            with self.subTest(url=url), self.assertRaises(csv_import.CsvImportError):
                csv_import.fetch_csv(url)

    def test_public_host_passes_validation(self):
        with mock.patch.object(
            csv_import.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]
        ):
            csv_import._assert_public_host("files.example.com")


class ImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="csv_admin", password="pw-12345!x")
        cls.staff.profile.role = Role.SUB_ADMIN
        cls.staff.profile.save(update_fields=["role"])

        cls.course = Course.objects.create(
            title="CSV batch",
            slug="csv-batch",
            subject="Reasoning",
            pricing_mode=Course.PricingMode.FREE,
            price=Decimal("0.00"),
            is_published=True,
            owner=cls.staff,
        )
        cls.quiz = Quiz.objects.create(
            title="Bulk mock",
            course=cls.course,
            timing_mode=Quiz.TimingMode.TIMED,
            duration_minutes=60,
            marks_per_question=Decimal("2.00"),
            negative_marks_per_wrong=Decimal("0.50"),
            is_published=False,
        )

    def import_rows(self, *rows, mode="append"):
        report = csv_import.parse_questions_csv(csv_text(*rows))
        return csv_import.import_questions(self.quiz, report, mode=mode)

    def test_import_writes_questions_choices_and_sections(self):
        imported = self.import_rows(
            good_row(question_text="Q1"),
            good_row(question_text="Q2", section="Quant"),
        )

        self.assertEqual(imported, 2)
        questions = list(self.quiz.questions.order_by("position"))
        self.assertEqual([q.position for q in questions], [1, 2])
        self.assertEqual([q.prompt for q in questions], ["Q1", "Q2"])
        self.assertEqual(questions[1].topic, "Quant")
        self.assertEqual(questions[0].marks, Decimal("2.00"))
        self.assertEqual(questions[0].negative_marks, Decimal("0.50"))

        choices = list(questions[0].choices.order_by("position"))
        self.assertEqual([c.text for c in choices], ["36", "48", "30", "42"])
        self.assertEqual([c.is_correct for c in choices], [False, True, False, False])
        self.assertFalse(hasattr(questions[0], "csv_blob"))

    def test_append_continues_position_numbers(self):
        self.import_rows(good_row(question_text="Q1"), good_row(question_text="Q2"))
        self.import_rows(good_row(question_text="Q3"))

        positions = list(self.quiz.questions.order_by("position").values_list("position", flat=True))
        self.assertEqual(positions, [1, 2, 3])

    def test_multiple_answers_are_stored(self):
        self.import_rows(good_row(question_type="multiple_choice", correct_option="A|D"))
        correct = list(
            self.quiz.questions.get().choices.filter(is_correct=True).values_list("text", flat=True)
        )
        self.assertEqual(sorted(correct), sorted(["36", "42"]))

    def test_nothing_is_written_when_any_row_fails(self):
        report = csv_import.parse_questions_csv(
            csv_text(good_row(question_text="fine"), good_row(correct_option="Z"))
        )
        with self.assertRaises(csv_import.ImportBlocked):
            csv_import.import_questions(self.quiz, report)

        self.assertEqual(self.quiz.questions.count(), 0)
        self.assertEqual(Choice.objects.count(), 0)

    def test_replace_is_refused_once_attempts_exist(self):
        self.import_rows(good_row(question_text="Q1"))
        question = self.quiz.questions.get()
        attempt = QuizAttempt.objects.create(user=self.staff, quiz=self.quiz)
        AttemptAnswer.objects.create(attempt=attempt, question=question)

        report = csv_import.parse_questions_csv(csv_text(good_row(question_text="New Q")))
        with self.assertRaises(csv_import.ImportBlocked) as caught:
            csv_import.import_questions(self.quiz, report, mode="replace")

        self.assertIn("already has attempts", str(caught.exception))
        self.assertEqual(self.quiz.questions.count(), 1)
        self.assertEqual(AttemptAnswer.objects.count(), 1)

    def test_replace_works_on_a_test_without_attempts(self):
        self.import_rows(good_row(question_text="Old Q"))
        self.import_rows(good_row(question_text="New Q"), mode="replace")

        self.assertEqual(
            list(self.quiz.questions.values_list("prompt", flat=True)), ["New Q"]
        )

    def test_replace_can_be_forced_explicitly(self):
        self.import_rows(good_row(question_text="Q1"))
        attempt = QuizAttempt.objects.create(user=self.staff, quiz=self.quiz)
        AttemptAnswer.objects.create(attempt=attempt, question=self.quiz.questions.get())

        report = csv_import.parse_questions_csv(csv_text(good_row(question_text="New Q")))
        csv_import.import_questions(
            self.quiz, report, mode="replace", allow_replace_with_attempts=True
        )
        self.assertEqual(self.quiz.questions.count(), 1)

    def test_export_round_trips(self):
        self.import_rows(
            good_row(question_text="Q1"),
            good_row(question_text="Q2", question_type="multiple_choice", correct_option="A|C"),
        )
        exported = csv_import.export_quiz_csv(self.quiz)
        again = csv_import.parse_questions_csv(exported)

        self.assertEqual(again.error_count, 0, again.errors)
        self.assertEqual([q.prompt for q in again.questions], ["Q1", "Q2"])
        self.assertEqual(again.questions[1].correct_indexes, [0, 2])

    def test_export_neutralises_formula_cells(self):
        Question.objects.create(
            quiz=self.quiz, prompt="=HYPERLINK(\"http://evil\")", position=1, topic="General"
        )
        exported = csv_import.export_quiz_csv(self.quiz)
        self.assertIn("'=HYPERLINK", exported)

    def test_negative_marks_are_exported_as_numbers(self):
        self.import_rows(good_row(negative_marks="0.5"))
        exported = csv_import.export_quiz_csv(self.quiz)
        # 0.50, not "'0.50": a negative penalty is a number, not a formula.
        self.assertIn("0.50", exported)
        self.assertNotIn("'", exported)


class ImportApiTests(TestCase):
    """The staff API surface: template, schema, validate, confirm."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="csv_api_admin", password="pw-12345!x")
        cls.staff.profile.role = Role.SUB_ADMIN
        cls.staff.profile.save(update_fields=["role"])
        cls.outsider = User.objects.create_user(username="csv_outsider", password="pw-12345!x")
        cls.outsider.profile.role = Role.SUB_ADMIN
        cls.outsider.profile.save(update_fields=["role"])
        cls.student = User.objects.create_user(username="csv_student", password="pw-12345!x")

        cls.course = Course.objects.create(
            title="API batch", slug="csv-api-batch", subject="Reasoning",
            pricing_mode=Course.PricingMode.FREE, price=Decimal("0.00"),
            is_published=True, owner=cls.staff,
        )
        cls.quiz = Quiz.objects.create(
            title="API mock", course=cls.course, timing_mode=Quiz.TimingMode.TIMED,
            duration_minutes=30, marks_per_question=Decimal("2.00"), is_published=False,
        )

    def client_as(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def make_job(self, url="https://files.example.com/q.csv"):
        return CsvImportJob.objects.create(
            quiz=self.quiz, source_url=url, requested_by=self.staff
        )

    # -- contract ----------------------------------------------------- #

    def test_template_downloads_with_the_exact_header(self):
        response = self.client_as(self.staff).get("/api/staff/import-jobs/template/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])

        header = response.content.decode().splitlines()[0]
        self.assertEqual(header, ",".join(csv_import.COLUMN_NAMES))

    def test_schema_endpoint_lists_every_column(self):
        payload = self.client_as(self.staff).get("/api/staff/import-jobs/schema/").json()
        self.assertEqual(payload["schema_version"], csv_import.SCHEMA_VERSION)
        self.assertEqual(
            [column["name"] for column in payload["columns"]], list(csv_import.COLUMN_NAMES)
        )
        self.assertTrue(any(column["required"] for column in payload["columns"]))

    def test_guests_cannot_read_the_contract(self):
        self.assertEqual(
            self.client.get("/api/staff/import-jobs/template/").status_code, 401
        )
        self.assertEqual(self.client.get("/api/staff/import-jobs/schema/").status_code, 401)

    # -- validate ----------------------------------------------------- #

    def test_validate_reports_a_preview_and_writes_no_questions(self):
        job = self.make_job()
        with mock.patch.object(
            csv_import, "fetch_csv", return_value=csv_text(good_row(question_text="Q1"))
        ):
            response = self.client_as(self.staff).post(
                f"/api/staff/import-jobs/{job.id}/validate/"
            )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["status"], "validated")
        self.assertEqual(payload["valid_rows"], 1)
        self.assertEqual(payload["preview"][0]["prompt"], "Q1")
        self.assertEqual(len(payload["digest"]), 64)

        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.VALIDATED)
        self.assertEqual(job.total_rows, 1)
        self.assertEqual(self.quiz.questions.count(), 0)

    def test_validate_fails_loudly_on_a_bad_file(self):
        job = self.make_job()
        with mock.patch.object(
            csv_import, "fetch_csv", return_value=csv_text(good_row(correct_option="Z"))
        ):
            response = self.client_as(self.staff).post(
                f"/api/staff/import-jobs/{job.id}/validate/"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.FAILED)
        self.assertIn("correct_option", job.error_summary)

    def test_validate_survives_a_fetch_failure(self):
        job = self.make_job()
        with mock.patch.object(
            csv_import, "fetch_csv", side_effect=csv_import.CsvImportError("CSV URL must use https://.")
        ):
            response = self.client_as(self.staff).post(
                f"/api/staff/import-jobs/{job.id}/validate/"
            )

        self.assertEqual(response.status_code, 400)
        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.FAILED)
        self.assertIn("https", job.error_summary)

    def test_another_provider_cannot_validate_someone_elses_job(self):
        job = self.make_job()
        response = self.client_as(self.outsider).post(f"/api/staff/import-jobs/{job.id}/validate/")
        self.assertIn(response.status_code, (403, 404))

    def test_students_cannot_import(self):
        job = self.make_job()
        response = self.client_as(self.student).post(f"/api/staff/import-jobs/{job.id}/validate/")
        self.assertEqual(response.status_code, 403)

    # -- confirm ------------------------------------------------------ #

    def validated(self, job, text):
        with mock.patch.object(csv_import, "fetch_csv", return_value=text):
            return self.client_as(self.staff).post(f"/api/staff/import-jobs/{job.id}/validate/")

    def confirm(self, job, **body):
        return self.client_as(self.staff).post(
            f"/api/staff/import-jobs/{job.id}/confirm_import/", body, format="json"
        )

    def test_confirm_imports_the_validated_file(self):
        job = self.make_job()
        text = csv_text(good_row(question_text="Q1"), good_row(question_text="Q2"))
        self.validated(job, text)

        with mock.patch.object(csv_import, "fetch_csv", return_value=text):
            response = self.confirm(job)

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["imported_rows"], 2)
        self.assertEqual(self.quiz.questions.count(), 2)

        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.IMPORTED)
        self.assertEqual(job.imported_rows, 2)
        self.assertIsNotNone(job.confirmed_at)

    def test_confirm_before_validate_is_refused(self):
        job = self.make_job()
        response = self.confirm(job)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.quiz.questions.count(), 0)

    def test_confirm_refuses_a_file_that_changed_after_validation(self):
        """Validate one file, swap the URL contents, import: that must not pass."""
        job = self.make_job()
        self.validated(job, csv_text(good_row(question_text="Q1")))

        with mock.patch.object(
            csv_import, "fetch_csv", return_value=csv_text(good_row(correct_option="Z"))
        ):
            response = self.confirm(job)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.quiz.questions.count(), 0)

    def test_confirm_replace_with_attempts_is_a_conflict(self):
        question = Question.objects.create(quiz=self.quiz, prompt="Old", position=1)
        attempt = QuizAttempt.objects.create(
            user=self.student, quiz=self.quiz, status=QuizAttempt.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )
        AttemptAnswer.objects.create(attempt=attempt, question=question)

        job = self.make_job()
        text = csv_text(good_row(question_text="New"))
        self.validated(job, text)

        with mock.patch.object(csv_import, "fetch_csv", return_value=text):
            response = self.confirm(job, mode="replace")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.quiz.questions.count(), 1)
        self.assertEqual(AttemptAnswer.objects.count(), 1)

    def test_confirm_rejects_an_unknown_mode(self):
        job = self.make_job()
        text = csv_text(good_row())
        self.validated(job, text)
        with mock.patch.object(csv_import, "fetch_csv", return_value=text):
            self.assertEqual(self.confirm(job, mode="overwrite").status_code, 400)

    def test_a_second_import_of_the_same_job_is_refused(self):
        job = self.make_job()
        text = csv_text(good_row())
        self.validated(job, text)
        with mock.patch.object(csv_import, "fetch_csv", return_value=text):
            self.confirm(job)
        with mock.patch.object(csv_import, "fetch_csv", return_value=text):
            response = self.confirm(job)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.quiz.questions.count(), 1)

    # -- export ------------------------------------------------------- #

    def test_export_returns_the_same_questions(self):
        Question.objects.create(quiz=self.quiz, prompt="Export me", position=1, topic="General")
        response = self.client_as(self.staff).get(
            f"/api/staff/import-jobs/export/?quiz={self.quiz.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Export me", response.content.decode())

    def test_export_requires_a_quiz_id(self):
        response = self.client_as(self.staff).get("/api/staff/import-jobs/export/")
        self.assertEqual(response.status_code, 400)


class ManagementCommandTests(TestCase):
    """`manage.py import_questions` — the path that actually builds a paper."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="cmd_admin", password="pw-12345!x")
        cls.staff.profile.role = Role.SUB_ADMIN
        cls.staff.profile.save(update_fields=["role"])
        cls.course = Course.objects.create(
            title="Command batch", slug="csv-cmd-batch", subject="Reasoning",
            pricing_mode=Course.PricingMode.FREE, price=Decimal("0.00"),
            is_published=True, owner=cls.staff,
        )
        cls.quiz = Quiz.objects.create(
            title="Command mock", course=cls.course, timing_mode=Quiz.TimingMode.TIMED,
            duration_minutes=30, marks_per_question=Decimal("2.00"), is_published=False,
        )

    def run_command(self, *args):
        out, err = io.StringIO(), io.StringIO()
        call_command("import_questions", *args, stdout=out, stderr=err)
        return out.getvalue()

    def write_csv(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return handle.name

    def test_dry_run_previews_without_writing(self):
        path = self.write_csv(csv_text(good_row(question_text="Q1")))
        output = self.run_command("--quiz", str(self.quiz.id), "--file", path, "--dry-run")

        self.assertIn("Dry run", output)
        self.assertIn("Q1", output)
        self.assertEqual(self.quiz.questions.count(), 0)

    def test_command_imports_on_success(self):
        path = self.write_csv(csv_text(good_row(question_text="Q1"), good_row(question_text="Q2")))
        self.run_command("--quiz", str(self.quiz.id), "--file", path)

        self.assertEqual(self.quiz.questions.count(), 2)
        self.assertEqual(self.quiz.questions.get(position=1).choices.count(), 4)

    def test_bad_row_imports_nothing(self):
        path = self.write_csv(csv_text(good_row(question_text="Q1"), good_row(correct_option="Z")))
        with self.assertRaises(CommandError) as caught:
            self.run_command("--quiz", str(self.quiz.id), "--file", path)

        self.assertIn("nothing was imported", str(caught.exception))
        self.assertEqual(self.quiz.questions.count(), 0)

    def test_export_then_reimport_round_trips(self):
        path = self.write_csv(csv_text(good_row(question_text="Round trip")))
        self.run_command("--quiz", str(self.quiz.id), "--file", path)

        export_path = Path(tempfile.mkdtemp()) / "export.csv"
        self.run_command("--quiz", str(self.quiz.id), "--export", str(export_path))
        self.assertIn("Round trip", export_path.read_text(encoding="utf-8"))

        other = Quiz.objects.create(
            title="Second", course=self.course, timing_mode=Quiz.TimingMode.TIMED,
            duration_minutes=30, marks_per_question=Decimal("2.00"),
        )
        self.run_command("--quiz", str(other.id), "--file", str(export_path))
        self.assertEqual(other.questions.get().prompt, "Round trip")

    def test_template_flag_prints_the_schema_header(self):
        output = self.run_command("--template")
        self.assertEqual(output.splitlines()[0], ",".join(csv_import.COLUMN_NAMES))


class AdminActionTests(TestCase):
    """`/admin/` is the only browser path: there is no staff console."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            username="csv_super", password="pw-12345!x", is_staff=True, is_superuser=True
        )
        cls.admin_user.profile.role = Role.MAIN_ADMIN
        cls.admin_user.profile.save(update_fields=["role"])
        cls.course = Course.objects.create(
            title="Admin batch", slug="csv-admin-batch", subject="Reasoning",
            pricing_mode=Course.PricingMode.FREE, price=Decimal("0.00"),
            is_published=True, owner=cls.admin_user,
        )
        cls.quiz = Quiz.objects.create(
            title="Admin mock", course=cls.course, timing_mode=Quiz.TimingMode.TIMED,
            duration_minutes=30, marks_per_question=Decimal("2.00"), is_published=False,
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def job(self):
        return CsvImportJob.objects.create(
            quiz=self.quiz, source_url="https://files.example.com/q.csv", requested_by=self.admin_user
        )

    def run_action(self, name, job):
        return self.client.post(
            "/admin/courses/csvimportjob/",
            {"action": name, "_selected_action": [str(job.id)]},
            follow=True,
        )

    def test_validate_action_stores_counts_and_digest(self):
        job = self.job()
        with mock.patch.object(
            csv_import, "fetch_csv", return_value=csv_text(good_row(question_text="Q1"))
        ):
            self.run_action("validate_selected", job)

        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.VALIDATED)
        self.assertEqual(job.total_rows, 1)
        self.assertEqual(len(job.source_sha256), 64)
        self.assertEqual(self.quiz.questions.count(), 0)

    def test_validate_action_fails_a_bad_file(self):
        job = self.job()
        with mock.patch.object(
            csv_import, "fetch_csv", return_value=csv_text(good_row(correct_option="Z"))
        ):
            self.run_action("validate_selected", job)

        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.FAILED)
        self.assertIn("correct_option", job.error_summary)

    def test_import_action_appends_questions(self):
        job = self.job()
        text = csv_text(good_row(question_text="Q1"), good_row(question_text="Q2"))
        with mock.patch.object(csv_import, "fetch_csv", return_value=text):
            self.run_action("validate_selected", job)
            self.run_action("import_selected", job)

        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.IMPORTED)
        self.assertEqual(job.imported_rows, 2)
        self.assertEqual(self.quiz.questions.count(), 2)

    def test_import_action_refuses_a_swapped_file(self):
        job = self.job()
        with mock.patch.object(csv_import, "fetch_csv", return_value=csv_text(good_row(question_text="Q1"))):
            self.run_action("validate_selected", job)

        with mock.patch.object(csv_import, "fetch_csv", return_value=csv_text(good_row(question_text="Q2"))):
            self.run_action("import_selected", job)

        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.FAILED)
        self.assertEqual(self.quiz.questions.count(), 0)

    def test_import_action_ignores_unvalidated_jobs(self):
        job = self.job()
        with mock.patch.object(csv_import, "fetch_csv", return_value=csv_text(good_row())):
            self.run_action("import_selected", job)

        job.refresh_from_db()
        self.assertEqual(job.status, CsvImportJob.Status.PENDING)
        self.assertEqual(self.quiz.questions.count(), 0)
