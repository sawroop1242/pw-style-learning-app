from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Role(models.TextChoices):
    STUDENT = "student"
    SUB_ADMIN = "sub_admin"
    MAIN_ADMIN = "main_admin"


class Profile(models.Model):
    """Extends the Django user with an explicit application role. The role is
    the single source of truth for API scoping; `is_staff` only controls
    Django-admin access."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.STUDENT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.role}"

    @property
    def is_main_admin(self):
        return self.role == Role.MAIN_ADMIN

    @property
    def is_sub_admin(self):
        return self.role == Role.SUB_ADMIN

    @property
    def is_staff_role(self):
        return self.role in {Role.MAIN_ADMIN, Role.SUB_ADMIN}


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    """Every user gets a profile with the student role by default."""
    if created:
        Profile.objects.create(user=instance)


class PasswordResetOTP(models.Model):
    """Single-use, short-lived, purpose-bound OTP. Only a keyed hash of the
    code is stored; the plaintext exists solely in the delivery email."""

    class Purpose(models.TextChoices):
        PASSWORD_RESET = "password_reset"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reset_otps"
    )
    purpose = models.CharField(
        max_length=40, choices=Purpose.choices, default=Purpose.PASSWORD_RESET
    )
    otp_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts_used = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "purpose"],
                condition=models.Q(consumed_at__isnull=True),
                name="unique_active_otp_per_user_purpose",
            )
        ]

    @property
    def is_consumed(self):
        return self.consumed_at is not None

    @property
    def is_expired(self):
        from django.utils import timezone

        return self.expires_at <= timezone.now()

    def __str__(self):
        return f"OTP(user={self.user_id}, {self.purpose})"


class AuditEvent(models.Model):
    """Append-only security/business event record. Metadata must be redacted
    at write time: never store secrets, raw codes, tokens or private note
    bodies here."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=80, blank=True)
    outcome = models.CharField(max_length=20, default="success")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"AuditEvent({self.action}, actor={self.actor_id})"
