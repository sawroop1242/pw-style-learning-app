from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .catalog import Lesson
from .common import TimeStampedModel
from .test_engine import Question


class Note(TimeStampedModel):
    """Private note, optionally linked to a course lesson or question."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_notes"
    )
    lesson = models.ForeignKey(
        Lesson, null=True, blank=True, on_delete=models.CASCADE, related_name="notes"
    )
    question = models.ForeignKey(
        Question,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    title = models.CharField(max_length=180, default="My note")
    body = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["user", "updated_at"])]

    def __str__(self):
        return f"{self.user}: {self.title}"


class Progress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="progress_records"
    )
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["lesson__position", "lesson_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson"], name="unique_user_lesson_progress"
            )
        ]

    def __str__(self):
        return f"{self.user} — {self.lesson}"


class Bookmark(TimeStampedModel):
    """Private saved reference to a course, lesson, PDF resource or question.
    Stores a stable resource pointer, never a copy of protected content."""

    BOOKMARKABLE_MODELS = ("course", "lesson", "pdfresource", "question")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    resource = GenericForeignKey("content_type", "object_id")
    note = models.CharField(max_length=500, blank=True)
    tag = models.CharField(max_length=80, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="unique_user_bookmark_resource",
            )
        ]

    def clean(self):
        if self.content_type and self.content_type.model not in self.BOOKMARKABLE_MODELS:
            raise ValidationError({"content_type": "Resource type cannot be bookmarked."})

    def __str__(self):
        return f"Bookmark(user={self.user_id}, {self.content_type}, {self.object_id})"


class RevisionItem(TimeStampedModel):
    """Private revision state for a lesson or question. Never touches formal
    attempt records."""

    class Status(models.TextChoices):
        NEEDS_REVISION = "needs_revision"
        REVIEWED = "reviewed"

    REVISABLE_MODELS = ("lesson", "question")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="revision_items"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    resource = GenericForeignKey("content_type", "object_id")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEEDS_REVISION
    )
    note = models.CharField(max_length=500, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="unique_user_revision_resource",
            )
        ]

    def clean(self):
        if self.content_type and self.content_type.model not in self.REVISABLE_MODELS:
            raise ValidationError({"content_type": "Resource type cannot be revised."})

    def __str__(self):
        return f"RevisionItem(user={self.user_id}, {self.content_type}, {self.object_id})"


class StudyTask(TimeStampedModel):
    """Private planner task; may link to an accessible course, lesson, quiz
    or revision item, or stand alone."""

    class Priority(models.TextChoices):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_tasks"
    )
    title = models.CharField(max_length=180)
    notes = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    linked_content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL
    )
    linked_object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_resource = GenericForeignKey("linked_content_type", "linked_object_id")

    class Meta:
        ordering = ["is_completed", "due_at", "-created_at"]
        indexes = [models.Index(fields=["user", "is_completed", "due_at"])]

    def clean(self):
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            raise ValidationError({"duration_minutes": "Duration must be positive."})
        if (
            self.linked_content_type is not None
            and self.linked_content_type.model not in ("course", "lesson", "quiz", "revisionitem")
        ):
            raise ValidationError({"linked_content_type": "Unsupported linked resource."})

    def __str__(self):
        return f"{self.user}: {self.title}"


class NotificationRead(TimeStampedModel):
    """Which derived notifications this account has already seen.

    Notifications are computed on read (an announcement, a task falling due, a
    result being released) rather than stored as rows, because each of those
    already has a table and a copy would drift. What cannot be derived is
    "I have read this", so only that is stored: one small row per item the
    learner has opened.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_reads"
    )
    key = models.CharField(max_length=80)
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-read_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key"], name="unique_notification_read_per_user"
            )
        ]

    def __str__(self):
        return f"NotificationRead({self.user_id}, {self.key})"
