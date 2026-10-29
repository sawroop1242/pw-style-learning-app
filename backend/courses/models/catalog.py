from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .common import TimeStampedModel


class Course(TimeStampedModel):
    """Published catalogue entry owned by a sub-admin (provider) or main admin."""

    class PricingMode(models.TextChoices):
        FREE = "free"
        PAID = "paid"

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=80, default="General", db_index=True)
    image_url = models.URLField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_courses",
    )
    pricing_mode = models.CharField(
        max_length=10, choices=PricingMode.choices, default=PricingMode.FREE
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    currency = models.CharField(max_length=3, default="INR")
    telegram_handle = models.CharField(max_length=80, blank=True)
    telegram_url = models.URLField(blank=True)
    is_published = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "-created_at"]
        indexes = [
            models.Index(fields=["is_published", "subject"]),
            models.Index(fields=["is_published", "pricing_mode"]),
        ]

    def clean(self):
        errors = {}
        if self.pricing_mode == self.PricingMode.FREE and (self.price or 0) != 0:
            errors["price"] = "Free courses must have a zero price."
        if self.pricing_mode == self.PricingMode.PAID and (self.price or 0) <= 0:
            errors["price"] = "Paid courses must have a positive price."
        if self.telegram_handle and self.telegram_handle.startswith("@") is False:
            errors["telegram_handle"] = "Telegram handle must start with '@'."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class CourseFolder(TimeStampedModel):
    """Ordered subject folder within a course; parent of lessons and PDFs."""

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="folders"
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "title"], name="unique_folder_title_per_course"
            )
        ]

    def __str__(self):
        return f"{self.course}: {self.title}"


class CourseFaculty(TimeStampedModel):
    """A teacher listed on a batch page.

    Deliberately small and owned by whoever owns the course: a name, the
    subject they teach, a short bio and an optional portrait URL. Nothing here
    is scraped or borrowed from another platform — a row exists because a
    provider typed it in.
    """

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="faculty"
    )
    name = models.CharField(max_length=120)
    subject = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name_plural = "course faculty"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "name"], name="unique_faculty_name_per_course"
            )
        ]
        indexes = [models.Index(fields=["course", "position"])]

    def __str__(self):
        return f"{self.course}: {self.name}"


class Lesson(TimeStampedModel):
    course = models.ForeignKey(
        Course, related_name="lessons", on_delete=models.CASCADE
    )
    folder = models.ForeignKey(
        CourseFolder,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    position = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "id"]
        indexes = [models.Index(fields=["course", "is_published"])]

    def clean(self):
        if self.folder and self.folder.course_id != self.course_id:
            raise ValidationError(
                {"folder": "Folder must belong to the same course as the lesson."}
            )

    def __str__(self):
        return f"{self.course}: {self.title}"


class PdfResource(TimeStampedModel):
    """Chapter PDF attached to a folder. Protected resources are only served
    through grant-checked API paths in later milestones."""

    folder = models.ForeignKey(
        CourseFolder, on_delete=models.CASCADE, related_name="pdf_resources"
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    file_url = models.URLField()
    position = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    is_protected = models.BooleanField(
        default=True,
        help_text="When true, the URL is only returned after a course-grant check.",
    )

    class Meta:
        verbose_name = "PDF resource"
        verbose_name_plural = "PDF resources"
        ordering = ["position", "id"]

    @property
    def course(self):
        return self.folder.course

    def __str__(self):
        return f"{self.course}: {self.title}"
