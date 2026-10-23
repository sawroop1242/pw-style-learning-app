import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .catalog import Course
from .common import TimeStampedModel

# Domain separation string, so the same SECRET_KEY used for other purposes
# cannot produce a colliding code hash.
_CODE_HASH_CONTEXT = b"studyspace:access-code:v2:"


def generate_access_code():
    """High-entropy code in a compact alphabet; hashed before storage."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _normalise(code):
    return (code or "").strip().upper()


def hash_access_code(code):
    """Keyed (HMAC-SHA256) hash of an access code.

    A plain ``sha256(secret + code)`` construction is vulnerable to length
    extension and leaks the secret's prefix relationship, so the keyed MAC is
    used instead. The ``v2$`` prefix lets legacy ``sha256$`` rows keep
    verifying while new codes use the stronger construction.
    """
    digest = hmac.new(
        settings.SECRET_KEY.encode(), _CODE_HASH_CONTEXT + _normalise(code).encode(), hashlib.sha256
    ).hexdigest()
    return f"v2${digest}"


def legacy_hash_access_code(code):
    """The pre-hardening construction. Verification only; never issued."""
    digest = hashlib.sha256(
        (settings.SECRET_KEY + ":access-code:" + _normalise(code)).encode()
    ).hexdigest()
    return f"sha256${digest}"


def verify_access_code(code, stored_hash):
    """Constant-time check that ``code`` matches ``stored_hash``.

    Supports both the current ``v2$`` MAC and the legacy ``sha256$`` value so
    codes already issued before the upgrade keep working. Returns a tuple of
    ``(matches, needs_upgrade)``.
    """
    if not stored_hash:
        return False, False
    if stored_hash.startswith("v2$"):
        return hmac.compare_digest(stored_hash, hash_access_code(code)), False
    if stored_hash.startswith("sha256$"):
        candidate = legacy_hash_access_code(code)
        if hmac.compare_digest(stored_hash, candidate):
            return True, True
    return False, False


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
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_uses__gte=1),
                name="access_code_max_uses_at_least_one",
            )
        ]

    @classmethod
    def hash_code(cls, raw_code):
        return hash_access_code(raw_code)

    def clean(self):
        errors = {}
        if not self.max_uses or self.max_uses < 1:
            errors["max_uses"] = "A code must be usable at least once."
        if self.uses_count is not None and self.max_uses and self.uses_count > self.max_uses:
            errors["uses_count"] = "Uses cannot exceed the maximum number of uses."
        if errors:
            raise ValidationError(errors)

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
