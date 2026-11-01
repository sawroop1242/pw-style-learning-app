from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .catalog import Course
from .common import TimeStampedModel


class TestSeries(TimeStampedModel):
    """Owner-scoped container for tests/mock exams."""

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    subject = models.CharField(max_length=80, default="General", db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="owned_test_series",
    )
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "test series"

    def __str__(self):
        return self.title


class Quiz(TimeStampedModel):
    """A test inside a series, or a standalone course quiz. Extended in
    Milestone 5 into a full timed test engine; answers are always scored
    server-side."""

    class TimingMode(models.TextChoices):
        UNTIMED = "untimed"
        TIMED = "timed"
        SECTION_TIMED = "section_timed"
        TOTAL_AND_SECTION = "total_and_section"

    class ResultReleasePolicy(models.TextChoices):
        IMMEDIATE = "immediate"
        AFTER_CLOSE = "after_close"
        MANUAL = "manual"

    series = models.ForeignKey(
        TestSeries,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="tests",
    )
    course = models.ForeignKey(
        Course,
        related_name="quizzes",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    timing_mode = models.CharField(
        max_length=20, choices=TimingMode.choices, default=TimingMode.UNTIMED
    )
    duration_minutes = models.PositiveIntegerField(
        null=True, blank=True, help_text="Total duration for timed modes."
    )
    attempt_limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="Null means unlimited attempts."
    )
    shuffle_questions = models.BooleanField(default=False)
    shuffle_options = models.BooleanField(default=False)
    result_release_policy = models.CharField(
        max_length=20,
        choices=ResultReleasePolicy.choices,
        default=ResultReleasePolicy.IMMEDIATE,
    )
    marks_per_question = models.DecimalField(
        max_digits=6, decimal_places=2, default="1.00"
    )
    negative_marks_per_wrong = models.DecimalField(
        max_digits=6, decimal_places=2, default="0.00"
    )
    pass_threshold_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage needed to pass, when configured.",
    )
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "quizzes"

    def clean(self):
        if (
            self.timing_mode in {self.TimingMode.TIMED, self.TimingMode.TOTAL_AND_SECTION}
            and not self.duration_minutes
        ):
            raise ValidationError(
                {"duration_minutes": "Timed quizzes require a total duration."}
            )

    @property
    def owner(self):
        return self.series.owner if self.series else self.course.owner if self.course else None

    def __str__(self):
        return self.title


class Question(TimeStampedModel):
    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "single_choice"
        MULTIPLE_CHOICE = "multiple_choice"
        TRUE_FALSE = "true_false"

    class Difficulty(models.TextChoices):
        EASY = "easy"
        MEDIUM = "medium"
        HARD = "hard"

    quiz = models.ForeignKey(Quiz, related_name="questions", on_delete=models.CASCADE)
    prompt = models.TextField()
    explanation = models.TextField(blank=True)
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.SINGLE_CHOICE
    )
    marks = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Per-question override; falls back to quiz default.",
    )
    negative_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, blank=True
    )
    topic = models.CharField(max_length=120, blank=True, db_index=True)
    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.prompt[:80]


class Choice(TimeStampedModel):
    question = models.ForeignKey(Question, related_name="choices", on_delete=models.CASCADE)
    text = models.CharField(max_length=400)
    is_correct = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.text[:80]


class QuizAttempt(TimeStampedModel):
    """Immutable-snapshot attempt: question order, option order and scoring
    rules are frozen at start so later edits cannot rewrite history."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress"
        SUBMITTED = "submitted"
        EXPIRED = "expired"

    #`` None`` means the paper was sat without an account. Those attempts carry
    # an opaque token instead (only its SHA-256 is stored), so a guest can
    # autosave, submit and read the result of their own attempt and nothing
    # else. Signing in is never required to sit a test.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )
    guest_token_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS
    )
    score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    question_order = models.JSONField(default=list)
    rules_snapshot = models.JSONField(default=dict)
    result_released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["user", "quiz", "status"])]

    @property
    def is_released(self):
        return self.result_released_at is not None

    @property
    def is_guest(self):
        return self.user_id is None

    def __str__(self):
        who = f"user={self.user_id}" if self.user_id else "guest"
        return f"Attempt({who}, quiz={self.quiz_id}, {self.status})"


class AttemptAnswer(TimeStampedModel):
    attempt = models.ForeignKey(
        QuizAttempt, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(
        Choice, related_name="+", blank=True
    )
    answered = models.BooleanField(default=False)
    marked_for_review = models.BooleanField(default=False)

    class Meta:
        ordering = ["question__position", "question_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"], name="unique_attempt_question_answer"
            )
        ]

    def __str__(self):
        return f"Answer(attempt={self.attempt_id}, question={self.question_id})"


class CsvImportJob(TimeStampedModel):
    """Metadata for an external-CSV-URL question import. The CSV blob or raw
    body is never persisted — only the source URL and safe counts."""

    class Status(models.TextChoices):
        PENDING = "pending"
        VALIDATED = "validated"
        IMPORTED = "imported"
        FAILED = "failed"

    quiz = models.ForeignKey(
        Quiz, on_delete=models.CASCADE, related_name="import_jobs"
    )
    source_url = models.URLField()
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="csv_import_jobs",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    total_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    source_sha256 = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 of the exact bytes that were validated. Confirmation refuses a different file.",
    )
    error_summary = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "CSV import job"
        verbose_name_plural = "CSV import jobs"
        ordering = ["-created_at"]

    @property
    def owner(self):
        """The provider who owns the target test.

        Object-level permissions resolve ownership through ``owner``; without
        this every staff action on a job answers 403 to its own creator.
        """
        return self.quiz.owner

    def __str__(self):
        return f"CsvImportJob(quiz={self.quiz_id}, {self.status})"


class QuestionReport(TimeStampedModel):
    """A learner saying "this question looks wrong", attached to the attempt.

    The reason used to live only in the browser: the exam window collected it,
    put it in the autosave payload and the server dropped it. A report is worth
    keeping because it is the only signal a provider gets about a bad question.

    One row per (attempt, question): reporting the same question twice updates
    the reason instead of piling up duplicates. A guest may report a question on
    their own attempt; ``user`` stays null for them and the attempt token is the
    only credential, exactly like autosave and submit.
    """

    class Reason(models.TextChoices):
        WRONG_ANSWER = "wrong_answer", "The marked answer looks wrong"
        TYPO = "typo", "Spelling or formatting problem"
        AMBIGUOUS = "ambiguous", "Question is ambiguous"
        MISSING_INFO = "missing_info", "Not enough information to answer"
        OTHER = "other", "Something else"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWING = "reviewing", "Being reviewed"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    attempt = models.ForeignKey(
        QuizAttempt, on_delete=models.CASCADE, related_name="reports"
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="reports"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="question_reports",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    detail = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"], name="unique_report_per_question"
            )
        ]
        indexes = [models.Index(fields=["status", "-created_at"])]

    @property
    def owner(self):
        """Whoever owns the paper: object permissions resolve through this."""
        return self.attempt.quiz.owner

    def __str__(self):
        return f"Report(attempt={self.attempt_id}, question={self.question_id}, {self.reason})"
