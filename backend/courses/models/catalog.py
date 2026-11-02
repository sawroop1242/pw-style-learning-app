import re
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .common import TimeStampedModel

# Telegram usernames are 4–32 characters, start with a letter, and may contain
# letters, digits and underscores. A handle that does not match this cannot
# produce a working `t.me` link, and a dead "Get code" button is worse than
# none, so the admin refuses it instead of storing it.
TELEGRAM_USERNAME = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{3,31})$")


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
    telegram_handle = models.CharField(
        max_length=80,
        blank=True,
        help_text=(
            "Telegram username the learner should message for an access code, "
            "with or without the @ — e.g. @studyspace_access."
        ),
    )
    telegram_url = models.URLField(
        blank=True,
        help_text="Optional public channel or group to link from the batch page.",
    )
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
        handle = (self.telegram_handle or "").strip()
        if handle and not TELEGRAM_USERNAME.match(handle):
            errors["telegram_handle"] = (
                "Use a Telegram username: 4–32 letters, digits or underscores, "
                "starting with a letter — @studyspace_access and studyspace_access "
                "both work."
            )
        if errors:
            raise ValidationError(errors)

    @property
    def telegram_username(self):
        """The bare username, or ``""`` when no usable handle is stored.

        The ``@`` people type in the admin is not part of the ``t.me`` path, so
        it is stripped here once instead of in every caller.
        """
        match = TELEGRAM_USERNAME.match((self.telegram_handle or "").strip())
        return match.group(1) if match else ""

    @property
    def telegram_dm_message(self):
        """What the learner's Telegram draft says before they send it.

        It names the batch and its number, because the teacher may be running
        several batches and "send me the code" alone is not enough to answer.
        """
        if self.pk:
            return (
                f'Hi! I want an access code for the batch "{self.title}" '
                f"(batch #{self.pk} · {self.slug})."
            )
        return f'Hi! I want an access code for the batch "{self.title}" ({self.slug}).'

    @property
    def telegram_dm_url(self):
        """A direct-message link with that text pre-filled, or ``""``."""
        username = self.telegram_username
        if not username:
            return ""
        return f"https://t.me/{username}?{urlencode({'text': self.telegram_dm_message})}"

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


def viewer_url_for(file_url, embed_url=""):
    """The URL to put in the reader's ``<iframe>``.

    Two rules, both learned from real providers:

    * an editor-supplied embed link wins, because only they know which URL a
      host actually serves for embedding;
    * otherwise the link is framed as it is. A PDF URL frames itself, and a
      host's share page (pdfhost's ``/v/<id>`` is one) is already that host's
      reader — wrapping it in Google's viewer only puts one viewer inside
      another, which is what the pdfhost link did.

    The single rewrite is Google Drive, whose ``/view`` page refuses framing
    but whose ``/preview`` does not. The reader always offers "open in a new
    tab" as well, because a host can start sending ``X-Frame-Options: DENY``
    at any time and no amount of URL guessing survives that.
    """
    if (embed_url or "").strip():
        return embed_url.strip()

    url = (file_url or "").strip()
    if not url:
        return ""

    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    path = parsed.path or ""

    if hostname.endswith("drive.google.com") or hostname.endswith("docs.google.com"):
        if "/view" in path:
            return url.replace("/view", "/preview")
    return url


class PdfResource(TimeStampedModel):
    """Chapter PDF attached to a folder. Protected resources are only served
    through grant-checked API paths in later milestones."""

    folder = models.ForeignKey(
        CourseFolder, on_delete=models.CASCADE, related_name="pdf_resources"
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    file_url = models.URLField()
    embed_url = models.URLField(
        blank=True,
        help_text=(
            "Optional. Paste the link the host gives for embedding, if it has "
            "one. Leave it blank and the file link is shown as it is — a PDF "
            "opens in the browser's viewer, and a share page such as pdfhost's "
            "/v/… opens in that site's reader."
        ),
    )
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

    @property
    def viewer_url(self):
        return viewer_url_for(self.file_url, self.embed_url)

    def __str__(self):
        return f"{self.course}: {self.title}"
