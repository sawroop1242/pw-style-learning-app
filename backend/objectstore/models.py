"""Storage targets: a Cloudflare account, and the buckets inside it.

One sub-admin may hold several Cloudflare accounts (a personal one, a client's,
a second one made for a fresh free tier), and each account may hold several
buckets (course images in one, PDFs in another). The model treats a bucket as
the unit a person actually picks: it is the thing that carries a name, a public
domain and the purposes it may serve.

Credentials live on the account, encrypted (see ``crypto``), and are never part
of a form's rendered value or of ``__str__``.
"""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from . import crypto
from .r2 import Credentials, endpoint_host

ACCOUNT_ID_RE = re.compile(r"^[a-f0-9]{32}$")
BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
ACCESS_KEY_RE = re.compile(r"^[A-Za-z0-9]{16,64}$")


class Purpose(models.TextChoices):
    """What a bucket may be used for. Mirrored by one flag per value."""

    COMMUNITY_IMAGES = "community_images", "Community post images"
    COURSE_IMAGES = "course_images", "Batch cover images"
    PDFS = "pdfs", "Notes and PDFs"


PURPOSE_FIELDS = {
    Purpose.COMMUNITY_IMAGES: "allow_community_images",
    Purpose.COURSE_IMAGES: "allow_course_images",
    Purpose.PDFS: "allow_pdfs",
}
PURPOSE_DEFAULT_FIELDS = {
    Purpose.COMMUNITY_IMAGES: "is_default_community",
    Purpose.COURSE_IMAGES: "is_default_course_images",
    Purpose.PDFS: "is_default_pdfs",
}


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class R2Account(TimeStampedModel):
    """One Cloudflare account, with the API token that can reach its buckets."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="r2_accounts",
        help_text="The sub-admin this account belongs to.",
    )
    name = models.CharField(
        max_length=80,
        help_text="A name you will recognise: \"My Cloudflare\", a client, a project.",
    )
    account_id = models.CharField(
        max_length=32,
        help_text=(
            "Cloudflare dashboard → R2 → Account details. 32 hexadecimal "
            "characters; it is also the first part of every bucket's endpoint."
        ),
    )

    # Both values are ciphertext. The admin form never renders them; see
    # objectstore/forms.py for the write-only fields that set them.
    access_key_id_enc = models.TextField(blank=True, editable=False)
    secret_access_key_enc = models.TextField(blank=True, editable=False)
    access_key_hint = models.CharField(max_length=16, blank=True, editable=False)

    is_active = models.BooleanField(
        default=True,
        help_text="Switch off to stop using this account and its buckets without deleting them.",
    )

    last_checked_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_check_ok = models.BooleanField(null=True, blank=True, editable=False)
    last_check_detail = models.CharField(max_length=200, blank=True, editable=False)

    class Meta:
        verbose_name = "Cloudflare account"
        verbose_name_plural = "Cloudflare accounts (R2)"
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="unique_r2_account_name_per_owner"
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        account_id = (self.account_id or "").strip().lower()
        if not ACCOUNT_ID_RE.match(account_id):
            raise ValidationError(
                {"account_id": "A Cloudflare account id is 32 hexadecimal characters."}
            )

    def save(self, *args, **kwargs):
        self.account_id = (self.account_id or "").strip().lower()
        self.name = (self.name or "").strip()
        super().save(*args, **kwargs)

    # -- credentials -------------------------------------------------------

    def set_credentials(self, access_key_id: str, secret_access_key: str) -> None:
        """Encrypt and stage new credentials (call ``save`` to persist)."""
        if not access_key_id or not secret_access_key:
            raise ValidationError("Both the access key id and the secret are required.")
        self.access_key_id_enc = crypto.encrypt(access_key_id)
        self.secret_access_key_enc = crypto.encrypt(secret_access_key)
        self.access_key_hint = crypto.fingerprint(access_key_id)

    def has_credentials(self) -> bool:
        return bool(self.access_key_id_enc and self.secret_access_key_enc)

    def get_credentials(self) -> Credentials | None:
        """Decrypt for a request. ``None`` when nothing is stored.

        A key that no longer matches raises :class:`crypto.CredentialError`;
        callers turn that into "re-enter the token" rather than a 500.
        """
        if not self.has_credentials():
            return None
        return Credentials(
            account_id=self.account_id,
            access_key_id=crypto.decrypt(self.access_key_id_enc),
            secret_access_key=crypto.decrypt(self.secret_access_key_enc),
        )

    # -- display -----------------------------------------------------------

    @property
    def endpoint(self) -> str:
        return f"https://{endpoint_host(self.account_id)}"

    def masked_account_id(self) -> str:
        value = self.account_id or ""
        return f"{value[:4]}…{value[-4:]}" if len(value) > 8 else value

    @property
    def bucket_count(self) -> int:
        return self.buckets.count()

    @property
    def connected_bucket_count(self) -> int:
        return self.buckets.filter(last_check_ok=True).count()

    def status_label(self) -> str:
        if not self.is_active:
            return "Switched off"
        if not self.has_credentials():
            return "No API token"
        if self.last_check_ok is None:
            return "Not tested yet"
        return "Connected" if self.last_check_ok else "Connection failed"


class R2Bucket(TimeStampedModel):
    """A bucket an upload may be sent to, and what it is allowed to hold."""

    account = models.ForeignKey(
        R2Account, on_delete=models.CASCADE, related_name="buckets"
    )
    name = models.CharField(
        max_length=63,
        help_text="The bucket name exactly as it appears in Cloudflare (it is case-sensitive).",
    )
    public_base_url = models.URLField(
        blank=True,
        help_text=(
            "Optional. A custom domain or the r2.dev address Cloudflare gives the "
            "bucket, e.g. https://files.example.com. With it, public files get "
            "permanent URLs; without it, links are signed and expire."
        ),
    )
    enabled = models.BooleanField(
        default=True, help_text="Switched-off buckets keep their files but accept no new uploads."
    )

    allow_community_images = models.BooleanField(
        "Community post images", default=False
    )
    allow_course_images = models.BooleanField("Batch cover images", default=False)
    allow_pdfs = models.BooleanField("Notes and PDFs", default=False)

    is_default_community = models.BooleanField("Default for community images", default=False)
    is_default_course_images = models.BooleanField("Default for batch covers", default=False)
    is_default_pdfs = models.BooleanField("Default for notes and PDFs", default=False)

    last_checked_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_check_ok = models.BooleanField(null=True, blank=True, editable=False)
    last_check_detail = models.CharField(max_length=200, blank=True, editable=False)

    class Meta:
        verbose_name = "R2 bucket"
        verbose_name_plural = "R2 buckets"
        ordering = ["account__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "name"], name="unique_r2_bucket_per_account"
            )
        ]
        indexes = [models.Index(fields=["account", "enabled"])]

    def __str__(self):
        return f"{self.name} ({self.account.name})"

    def clean(self):
        name = (self.name or "").strip()
        if not BUCKET_NAME_RE.match(name):
            raise ValidationError(
                {
                    "name": (
                        "A bucket name is 3–63 characters: lowercase letters, digits, "
                        "dots and hyphens, starting and ending with a letter or digit."
                    )
                }
            )
        if ".." in name:
            raise ValidationError({"name": "A bucket name cannot contain two dots in a row."})
        base = (self.public_base_url or "").strip()
        if base and not base.startswith("https://"):
            raise ValidationError(
                {"public_base_url": "Use an https:// address; a bucket's public domain is HTTPS."}
            )
        # A bucket cannot be the default for a purpose it is not allowed to serve.
        for purpose, default_field in PURPOSE_DEFAULT_FIELDS.items():
            if getattr(self, default_field):
                setattr(self, PURPOSE_FIELDS[purpose], True)

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.public_base_url = (self.public_base_url or "").strip().rstrip("/")
        for purpose, default_field in PURPOSE_DEFAULT_FIELDS.items():
            if getattr(self, default_field):
                setattr(self, PURPOSE_FIELDS[purpose], True)

        super().save(*args, **kwargs)

        # One default per purpose per owner. Ticking a new default moves it
        # rather than failing: that is what "make this the default" means, and
        # an admin should not have to untick the old one first.
        for purpose, default_field in PURPOSE_DEFAULT_FIELDS.items():
            if getattr(self, default_field):
                R2Bucket.objects.filter(
                    account__owner_id=self.account.owner_id, **{default_field: True}
                ).exclude(pk=self.pk).update(**{default_field: False})

    # -- capabilities ------------------------------------------------------

    def allows(self, purpose: str) -> bool:
        field = PURPOSE_FIELDS.get(purpose)
        return bool(field and getattr(self, field))

    def is_default_for(self, purpose: str) -> bool:
        field = PURPOSE_DEFAULT_FIELDS.get(purpose)
        return bool(field and getattr(self, field))

    @property
    def purposes(self) -> list[str]:
        return [label for purpose, label in Purpose.choices if self.allows(purpose)]

    @property
    def is_usable(self) -> bool:
        return bool(self.enabled and self.account.is_active and self.account.has_credentials())

    def mark_checked(self, *, ok: bool, detail: str) -> None:
        """Record the verdict of a connection test on the bucket and its account."""
        now = timezone.now()
        self.last_checked_at = now
        self.last_check_ok = ok
        self.last_check_detail = (detail or "")[:200]
        self.save(update_fields=["last_checked_at", "last_check_ok", "last_check_detail", "updated_at"])

        account = self.account
        account.last_checked_at = now
        account.last_check_ok = ok
        account.last_check_detail = (detail or "")[:200]
        account.save(update_fields=["last_checked_at", "last_check_ok", "last_check_detail", "updated_at"])

    def public_url(self, key: str) -> str:
        """The permanent URL, when the bucket has a public domain."""
        if not self.public_base_url:
            return ""
        return f"{self.public_base_url}/{str(key).lstrip('/')}"
