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

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts"
    )
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

    def __str__(self):
        return f"Attempt(user={self.user_id}, quiz={self.quiz_id}, {self.status})"


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
    error_summary = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"CsvImportJob(quiz={self.quiz_id}, {self.status})"
