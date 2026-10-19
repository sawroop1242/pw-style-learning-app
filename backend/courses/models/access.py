import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from .catalog import Course
from .common import TimeStampedModel


def generate_access_code():
    """High-entropy code in a compact alphabet; hashed before storage."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def hash_access_code(code):
    """Keyed hash so database contents alone cannot be used to redeem codes
    or mount offline comparisons across deployments."""
    digest = hashlib.sha256(
        (settings.SECRET_KEY + ":access-code:" + code.strip().upper()).encode()
    ).hexdigest()
    return f"sha256${digest}"


class AccessCode(TimeStampedModel):
    """Course-bound code. Only the hash is persisted; the raw value is shown
    to staff exactly once at creation time."""

    class Status(models.TextChoices):
        UNUSED = "unused"
        REDEEMED = "redeemed"
        REVOKED = "revoked"

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="access_codes"
    )
    code_hash = models.CharField(max_length=128, unique=True)
    max_uses = models.PositiveIntegerField(default=1)
    uses_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_access_codes",
    )
    last_redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="redeemed_access_codes",
    )
    last_redeemed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_access_codes",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["course", "code_hash"])]

    @classmethod
    def hash_code(cls, raw_code):
        return hash_access_code(raw_code)

    @property
    def status(self):
        if self.revoked_at is not None:
            return self.Status.REVOKED
        if self.uses_count >= self.max_uses:
            return self.Status.REDEEMED
        return self.Status.UNUSED

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    def __str__(self):
        return f"AccessCode(course={self.course_id}, {self.status})"


class CourseAccessGrant(TimeStampedModel):
    """Durable paid-course access for a student. Created only by server-side
    redemption; revoking a code never silently revokes an existing grant."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_grants"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="grants")
    access_code = models.ForeignKey(
        AccessCode,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="grants",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="grants_given",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "course"], name="unique_user_course_grant"
            )
        ]

    @property
    def is_active(self):
        return self.revoked_at is None

    def __str__(self):
        return f"Grant(user={self.user_id}, course={self.course_id})"
