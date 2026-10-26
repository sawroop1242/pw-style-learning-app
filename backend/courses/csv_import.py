"""Question-bank CSV import and export — schema **v1**.

Why this module exists
----------------------
Writing a 100-question mock through the staff API means 100 questions and 400
choices, one request at a time. CSV is the only practical way to author a
full-length paper, so the import is a first-class, validated path rather than a
flag that flips to "imported".

The rules this module enforces
------------------------------
* **One column, one meaning.** Every column maps to exactly one stored field.
  ``section`` is stored in ``Question.topic`` because that is the field the exam
  window groups by; there is no second ``topic`` column to disagree with it.
* **All or nothing.** A file is parsed and validated completely before a single
  row is written. A file with one bad row imports nothing, so a paper is never
  half-created.
* **Nothing is stored.** The CSV body is never persisted. Only the source URL,
  a SHA-256 of the exact bytes that were validated, counts and capped errors.
* **Validate what you import.** The digest recorded at validation must still
  match at confirmation, so the file cannot be swapped in between.
* **History is protected.** ``replace`` is refused on a test that already has
  attempts; answers reference questions with ``ON DELETE CASCADE``, so deleting
  questions would quietly destroy submitted answer sheets.

The schema is versioned (``SCHEMA_VERSION``); a template and this importer are
generated from the same constant list, so they cannot drift.
"""

from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.db import transaction
from django.db.models import Max

from .models import Choice, Question, Quiz, QuizAttempt

SCHEMA_VERSION = "1"

#: The columns the template ships with, in order. The importer accepts any
#: subset that still contains every required column; a column outside this list
#: is rejected so a typo cannot silently drop data.
COLUMNS: tuple[tuple[str, bool, str], ...] = (
    ("section", False, "Exam section the question belongs to, e.g. Physics. Blank = General."),
    ("question_type", False, "single_choice (default), multiple_choice or true_false."),
    ("question_text", True, "The question itself. Required."),
    ("option_a", True, "First option."),
    ("option_b", True, "Second option."),
    ("option_c", False, "Third option, if the question has one."),
    ("option_d", False, "Fourth option, if the question has one."),
    ("option_e", False, "Fifth option, if the question has one."),
    ("correct_option", True, "One key (A) or several separated by a pipe (A|C)."),
    ("explanation", False, "Shown after submission."),
    ("marks", False, "Marks for a correct answer. Blank = the test default."),
    ("negative_marks", False, "Penalty for a wrong answer. Blank = the test default."),
    ("difficulty", False, "easy, medium or hard."),
)

COLUMN_NAMES = tuple(name for name, _, _ in COLUMNS)
REQUIRED_COLUMNS = tuple(name for name, required, _ in COLUMNS if required)
OPTION_COLUMNS = tuple(name for name in COLUMN_NAMES if name.startswith("option_"))
OPTION_LETTERS = tuple(column.removeprefix("option_").upper() for column in OPTION_COLUMNS)

QUESTION_TYPES = ("single_choice", "multiple_choice", "true_false")
DIFFICULTIES = ("easy", "medium", "hard")

MAX_CSV_BYTES = 2 * 1024 * 1024  # 2 MiB — ~2,000 five-option questions
MAX_ROWS = 2000
MAX_ERRORS = 200
MAX_PROMPT_CHARS = 5000
MAX_OPTION_CHARS = 400  # matches Choice.text
MAX_SECTION_CHARS = 120  # matches Question.topic
FETCH_TIMEOUT_SECONDS = 10

DEFAULT_SECTION = "General"


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class CsvImportError(Exception):
    """A problem with the file as a whole: encoding, header, size, fetch."""


@dataclass(frozen=True)
class RowProblem:
    row: int
    message: str
    column: str | None = None
    code: str = "invalid_row"

    def as_dict(self) -> dict:
        return {"row": self.row, "column": self.column, "code": self.code, "message": self.message}


@dataclass
class ParsedQuestion:
    row: int
    section: str
    question_type: str
    prompt: str
    options: list[str]
    correct_indexes: list[int]
    explanation: str = ""
    marks: Decimal | None = None
    negative_marks: Decimal | None = None
    difficulty: str = ""


@dataclass
class ImportReport:
    total_rows: int = 0
    questions: list[ParsedQuestion] = field(default_factory=list)
    errors: list[RowProblem] = field(default_factory=list)
    warnings: list[RowProblem] = field(default_factory=list)
    digest: str = ""
    truncated: bool = False

    @property
    def valid_rows(self) -> int:
        return len(self.questions)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def preview(self, limit: int = 50) -> list[dict]:
        return [
            {
                "row": q.row,
                "section": q.section,
                "question_type": q.question_type,
                "prompt": q.prompt,
                "options": q.options,
                "correct_option": "|".join(OPTION_LETTERS[i] for i in q.correct_indexes),
                "marks": str(q.marks) if q.marks is not None else None,
            }
            for q in self.questions[:limit]
        ]

    def as_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "error_count": self.error_count,
            "warning_count": len(self.warnings),
            "digest": self.digest,
            "errors": [problem.as_dict() for problem in self.errors],
            "warnings": [problem.as_dict() for problem in self.warnings],
            "preview": self.preview(),
            "truncated": self.truncated,
        }

    def summary(self, limit: int = 20) -> str:
        """A short, safe text summary for ``CsvImportJob.error_summary``."""
        if not self.errors:
            return ""
        lines = [
            f"{problem.row}: {problem.message}"
            for problem in self.errors[:limit]
        ]
        if self.error_count > limit:
            lines.append(f"… and {self.error_count - limit} more errors")
        return "\n".join(lines)[:4000]


# --------------------------------------------------------------------------- #
# Template and export
# --------------------------------------------------------------------------- #


def _safe_cell(value: object) -> str:
    """Neutralise spreadsheet formula injection on export.

    A cell beginning with ``=``, ``+``, ``-`` or ``@`` is executed by Excel and
    Sheets. Negative numbers are left alone because they are numbers.
    """
    text = "" if value is None else str(value)
    if not text:
        return ""
    if text[0] in "=+@":
        return "'" + text
    if text[0] == "-" and not re.fullmatch(r"-\d+(\.\d+)?", text):
        return "'" + text
    return text


def template_csv() -> str:
    """The documented template: the exact header plus two illustrative rows."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMN_NAMES)
    writer.writerow(
        [
            "Reasoning",
            "single_choice",
            "Which number completes the series 3, 6, 12, 24, …?",
            "36",
            "48",
            "30",
            "42",
            "",
            "B",
            "Each term doubles, so 24 x 2 = 48.",
            "2",
            "0.5",
            "easy",
        ]
    )
    writer.writerow(
        [
            "Reasoning",
            "multiple_choice",
            "Which of these are prime numbers?",
            "2",
            "3",
            "4",
            "6",
            "",
            "A|B",
            "2 and 3 have no divisors other than 1 and themselves.",
            "2",
            "0.5",
            "medium",
        ]
    )
    return buffer.getvalue()


def export_quiz_csv(quiz: Quiz) -> str:
    """Round-trippable export of one test in schema v1."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMN_NAMES)

    questions = quiz.questions.prefetch_related("choices").order_by("position", "id")
    for question in questions:
        choices = list(question.choices.all())
        letters = OPTION_LETTERS
        row = [
            question.topic or DEFAULT_SECTION,
            question.question_type,
            question.prompt,
        ]
        for index in range(len(OPTION_COLUMNS)):
            row.append(choices[index].text if index < len(choices) else "")
        row.append(
            "|".join(
                letters[index]
                for index, choice in enumerate(choices)
                if choice.is_correct and index < len(letters)
            )
        )
        row.extend(
            [
                question.explanation,
                "" if question.marks is None else str(question.marks),
                "" if question.negative_marks is None else str(question.negative_marks),
                question.difficulty,
            ]
        )
        writer.writerow([_safe_cell(value) for value in row])
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Fetching (SSRF-guarded)
# --------------------------------------------------------------------------- #


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise urllib.error.HTTPError(
            req.full_url, code, "redirects are not followed for CSV imports", headers, fp
        )


def _assert_public_host(host: str) -> None:
    """Reject a host that resolves to anything but a public address."""
    if not host:
        raise CsvImportError("CSV URL has no host.")
    if "." not in host:
        raise CsvImportError("CSV URL must point at a public host name.")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as error:
        raise CsvImportError(f"CSV host could not be resolved: {host}") from error

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_multicast:
            raise CsvImportError(
                "CSV URL must point at a public address; private, loopback and "
                "link-local hosts are refused."
            )


def fetch_csv(url: str) -> str:
    """Download a CSV over HTTPS from a public host.

    Redirects are refused rather than followed, because a redirect is the usual
    way an SSRF guard is bypassed.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise CsvImportError("CSV URL must use https://.")
    _assert_public_host(parsed.hostname or "")

    request = urllib.request.Request(
        url, headers={"User-Agent": f"studyspace-csv-import/{SCHEMA_VERSION}"}
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            payload = response.read(MAX_CSV_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise CsvImportError(f"CSV download failed with HTTP {error.code}.") from error
    except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
        raise CsvImportError("CSV download failed: the host did not answer.") from error

    if len(payload) > MAX_CSV_BYTES:
        raise CsvImportError(f"CSV is larger than the {MAX_CSV_BYTES // (1024 * 1024)} MiB limit.")

    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvImportError("CSV must be UTF-8 encoded.") from error


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _parse_decimal(
    raw: str,
    *,
    row: int,
    column: str,
    errors: list[RowProblem],
) -> Decimal | None:
    text = _clean(raw)
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        errors.append(RowProblem(row, f"{column} must be a number, got {text[:20]!r}.", column, "bad_number"))
        return None
    if value < 0:
        errors.append(RowProblem(row, f"{column} cannot be negative.", column, "negative_number"))
        return None
    return value


def _normalise_header(row: list[str]) -> list[str]:
    header = [cell.strip().lower() for cell in row]
    if header and header[0].startswith("\ufeff"):
        header[0] = header[0].lstrip("\ufeff")

    unknown = [name for name in header if name and name not in COLUMN_NAMES]
    if unknown:
        raise CsvImportError(
            "Unknown column(s): "
            + ", ".join(sorted(unknown))
            + ". Supported columns are: "
            + ", ".join(COLUMN_NAMES)
            + "."
        )

    missing = [name for name in REQUIRED_COLUMNS if name not in header]
    if missing:
        raise CsvImportError(
            "Missing required column(s): " + ", ".join(missing) + "."
        )

    duplicates = {name for name in header if header.count(name) > 1}
    if duplicates:
        raise CsvImportError("Duplicate column(s): " + ", ".join(sorted(duplicates)) + ".")

    if "" in header:
        blank_at = header.index("") + 1
        raise CsvImportError(f"Column {blank_at} has no header name.")

    return header


def parse_questions_csv(text: str) -> ImportReport:
    """Parse and validate a whole CSV. Never touches the database."""
    report = ImportReport(digest=hashlib.sha256(text.encode("utf-8")).hexdigest())

    reader = csv.reader(io.StringIO(text))
    try:
        header_row = next(reader)
    except StopIteration as error:
        raise CsvImportError("CSV is empty.") from error

    header = _normalise_header(header_row)
    index = {name: position for position, name in enumerate(header)}
    data_rows = list(reader)
    report.total_rows = len(data_rows)

    if not data_rows:
        raise CsvImportError("CSV has a header but no question rows.")
    if len(data_rows) > MAX_ROWS:
        raise CsvImportError(f"CSV has {len(data_rows)} rows; the limit is {MAX_ROWS}.")

    seen_prompts: dict[str, int] = {}

    for offset, raw in enumerate(data_rows, start=2):  # row 1 is the header
        if not any(cell.strip() for cell in raw):
            continue  # a blank line is skipped, not an error

        def cell(name: str) -> str:
            position = index.get(name)
            if position is None or position >= len(raw):
                return ""
            return _clean(raw[position])

        row_errors: list[RowProblem] = []

        prompt = cell("question_text")
        if not prompt:
            row_errors.append(RowProblem(offset, "question_text is required.", "question_text", "missing_prompt"))
        elif len(prompt) > MAX_PROMPT_CHARS:
            row_errors.append(
                RowProblem(offset, f"question_text exceeds {MAX_PROMPT_CHARS} characters.", "question_text", "prompt_too_long")
            )

        section = cell("section") or DEFAULT_SECTION
        if len(section) > MAX_SECTION_CHARS:
            row_errors.append(
                RowProblem(offset, f"section exceeds {MAX_SECTION_CHARS} characters.", "section", "section_too_long")
            )

        question_type = cell("question_type").lower() or "single_choice"
        if question_type not in QUESTION_TYPES:
            row_errors.append(
                RowProblem(
                    offset,
                    f"question_type {question_type[:20]!r} is not supported; use {', '.join(QUESTION_TYPES)}.",
                    "question_type",
                    "bad_question_type",
                )
            )

        difficulty = cell("difficulty").lower()
        if difficulty and difficulty not in DIFFICULTIES:
            row_errors.append(
                RowProblem(offset, f"difficulty {difficulty[:20]!r} is not one of easy, medium, hard.", "difficulty", "bad_difficulty")
            )

        options: list[str] = []
        for column in OPTION_COLUMNS:
            value = cell(column)
            if not value:
                continue
            if len(value) > MAX_OPTION_CHARS:
                row_errors.append(
                    RowProblem(offset, f"{column} exceeds {MAX_OPTION_CHARS} characters.", column, "option_too_long")
                )
            options.append(value)

        # Options must be contiguous: a gap means the letters no longer line up
        # with the correct_option keys, which would mis-score the question.
        used = [cell(column) for column in OPTION_COLUMNS]
        first_gap = next((i for i, value in enumerate(used) if not value), None)
        if first_gap is not None and any(used[first_gap:]):
            row_errors.append(
                RowProblem(
                    offset,
                    f"option_{OPTION_LETTERS[first_gap].lower()} is empty but a later option is set; options must be contiguous.",
                    f"option_{OPTION_LETTERS[first_gap].lower()}",
                    "option_gap",
                )
            )

        if len(options) < 2:
            row_errors.append(RowProblem(offset, "A question needs at least two options.", "option_b", "too_few_options"))
        if question_type == "true_false" and len(options) != 2:
            row_errors.append(
                RowProblem(offset, "true_false questions must have exactly two options.", "option_c", "true_false_options")
            )

        # correct_option
        raw_correct = cell("correct_option").upper().replace(",", "|").replace(" ", "")
        keys = [part for part in raw_correct.split("|") if part]
        correct_indexes: list[int] = []
        if not keys:
            row_errors.append(RowProblem(offset, "correct_option is required.", "correct_option", "missing_correct"))
        else:
            for key in keys:
                if key not in OPTION_LETTERS:
                    row_errors.append(
                        RowProblem(offset, f"correct_option key {key[:5]!r} is not a valid option letter.", "correct_option", "bad_correct_key")
                    )
                    continue
                position = OPTION_LETTERS.index(key)
                if position >= len(used) or not used[position]:
                    row_errors.append(
                        RowProblem(
                            offset,
                            f"correct_option names {key} but option_{key.lower()} is empty.",
                            "correct_option",
                            "correct_without_option",
                        )
                    )
                    continue
                if position not in correct_indexes:
                    correct_indexes.append(position)
            if len(set(keys)) != len(keys):
                row_errors.append(RowProblem(offset, "correct_option repeats a key.", "correct_option", "duplicate_key"))
            if correct_indexes and question_type == "single_choice" and len(correct_indexes) != 1:
                row_errors.append(
                    RowProblem(
                        offset,
                        "single_choice needs exactly one correct option; use multiple_choice for several.",
                        "correct_option",
                        "too_many_correct",
                    )
                )
            elif correct_indexes and question_type == "true_false" and len(correct_indexes) != 1:
                row_errors.append(
                    RowProblem(offset, "true_false needs exactly one correct option.", "correct_option", "true_false_correct")
                )

        marks = _parse_decimal(cell("marks"), row=offset, column="marks", errors=row_errors)
        negative_marks = _parse_decimal(
            cell("negative_marks"), row=offset, column="negative_marks", errors=row_errors
        )

        if prompt:
            fingerprint = re.sub(r"\s+", " ", prompt).strip().lower()
            if fingerprint in seen_prompts:
                row_errors.append(
                    RowProblem(
                        offset,
                        f"identical question_text already appears on row {seen_prompts[fingerprint]}.",
                        "question_text",
                        "duplicate_prompt",
                    )
                )
            else:
                seen_prompts[fingerprint] = offset

        if row_errors:
            report.errors.extend(row_errors)
            if len(report.errors) >= MAX_ERRORS and offset < len(data_rows):
                report.truncated = True
                report.warnings.append(
                    RowProblem(offset, f"Stopped collecting after {MAX_ERRORS} errors.", None, "errors_truncated")
                )
                break
            continue

        report.questions.append(
            ParsedQuestion(
                row=offset,
                section=section,
                question_type=question_type,
                prompt=prompt,
                options=options,
                correct_indexes=sorted(correct_indexes),
                explanation=cell("explanation"),
                marks=marks,
                negative_marks=negative_marks,
                difficulty=difficulty,
            )
        )

    return report


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


class ImportBlocked(Exception):
    """Confirmation is not allowed in the current state."""


def import_questions(
    quiz: Quiz,
    report: ImportReport,
    *,
    mode: str = "append",
    allow_replace_with_attempts: bool = False,
) -> int:
    """Write a validated report into ``quiz`` atomically.

    ``append`` keeps existing questions and appends after the highest position.
    ``replace`` deletes them first, and is refused when the test already has
    attempts because answer rows reference questions with ``ON DELETE CASCADE``.
    """
    if mode not in ("append", "replace"):
        raise ValueError("mode must be 'append' or 'replace'")
    if not report.questions:
        raise ImportBlocked("There is nothing to import: the file has no valid questions.")
    if report.errors:
        raise ImportBlocked("Fix the reported row errors before importing.")

    with transaction.atomic():
        locked = Quiz.objects.select_for_update().get(pk=quiz.pk)

        if mode == "replace":
            if not allow_replace_with_attempts and QuizAttempt.objects.filter(quiz=locked).exists():
                raise ImportBlocked(
                    "This test already has attempts. Replacing its questions would delete "
                    "submitted answer sheets, so the import is refused. Create a new test "
                    "for a new version of the paper."
                )
            locked.questions.all().delete()
            start = 1
        else:
            highest = locked.questions.aggregate(top=Max("position"))["top"] or 0
            start = highest + 1

        objects = [
            Question(
                quiz=locked,
                prompt=parsed.prompt,
                explanation=parsed.explanation,
                question_type=parsed.question_type,
                marks=parsed.marks,
                negative_marks=parsed.negative_marks,
                difficulty=parsed.difficulty,
                topic=parsed.section,
                position=start + offset,
            )
            for offset, parsed in enumerate(report.questions)
        ]
        created = Question.objects.bulk_create(objects, batch_size=200)

        choices = []
        for parsed, question in zip(report.questions, created):
            for index, text in enumerate(parsed.options):
                choices.append(
                    Choice(
                        question=question,
                        text=text,
                        position=index,
                        is_correct=index in parsed.correct_indexes,
                    )
                )
        Choice.objects.bulk_create(choices, batch_size=400)

        return len(created)
