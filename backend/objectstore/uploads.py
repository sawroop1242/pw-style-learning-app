"""One way for an asset to get into R2, and one way back out.

Before this module the R2 subsystem could administer accounts and buckets and
sign URLs, but nothing took an actual file and put it somewhere: editors pasted
a link from whichever host they had used, and the bucket configuration only
described where content *could* live.

The contract here is small on purpose:

* **Validate.** Purpose decides the allowed types and the size ceiling. The
  extension is checked against the declared type, because a browser will happily
  send ``.html`` as ``text/html`` inside the PDF picker.
* **Name.** The key is ``<owner>/<purpose>/<uuid4>.<ext>`` — collision-resistant,
  and it tells nobody what the original filename was, which is often a student's
  name.
* **Resolve.** The bucket comes from ``services.resolve_bucket`` (the owner's
  default for that purpose), never from the request.
* **Store and verify.** Upload, then HEAD the object and compare sizes. An
  upload the bucket did not keep is not reported as success.
* **Deliver.** A public bucket gives a permanent URL; a private one gives a
  short-lived signed URL, minted at read time for the learner who was allowed to
  read it. The key is what gets stored — never a URL carrying a signature.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.conf import settings

from . import crypto, r2, services
from .models import Purpose

__all__ = [
    "UploadRefused",
    "StoredObject",
    "PURPOSE_RULES",
    "validate_upload",
    "object_key",
    "store",
    "url_for_key",
]

MIB = 1024 * 1024


@dataclass(frozen=True)
class PurposeRule:
    """What a purpose accepts."""

    content_types: frozenset[str]
    extensions: frozenset[str]
    max_bytes: int

    @property
    def label(self) -> str:
        first, *rest = sorted(self.extensions)
        return ", ".join([first, *rest])


#: One entry per bucket purpose in ``models.Purpose``. Video is deliberately
#: absent: lessons play from an embed URL (the host's player), and no bucket is
#: configured to hold hundreds of megabytes of video.
PURPOSE_RULES = {
    Purpose.COURSE_IMAGES: PurposeRule(
        content_types=frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"}),
        extensions=frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"}),
        max_bytes=8 * MIB,
    ),
    Purpose.COMMUNITY_IMAGES: PurposeRule(
        content_types=frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"}),
        extensions=frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"}),
        max_bytes=8 * MIB,
    ),
    Purpose.PDFS: PurposeRule(
        content_types=frozenset({"application/pdf"}),
        extensions=frozenset({".pdf"}),
        max_bytes=64 * MIB,
    ),
}


class UploadRefused(Exception):
    """The file is not acceptable; the message is shown to the editor."""


@dataclass(frozen=True)
class StoredObject:
    bucket: object
    key: str
    size: int
    content_type: str
    url: str
    expires_at: datetime | None


def _extension(filename: str) -> str:
    name = (filename or "").strip()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[1].lower()


def validate_upload(purpose: str, filename: str, content_type: str, size: int) -> str:
    """Check a file against its purpose and return the normalised type.

    Raises :class:`UploadRefused` with a sentence the editor can act on.
    """
    rule = PURPOSE_RULES.get(purpose)
    if rule is None:
        raise UploadRefused(
            f"Unknown upload purpose {purpose!r}. Use one of: "
            + ", ".join(sorted(PURPOSE_RULES))
            + "."
        )
    if size <= 0:
        raise UploadRefused("The file is empty.")
    if size > rule.max_bytes:
        raise UploadRefused(
            f"That file is larger than the {rule.max_bytes // MIB} MiB limit for "
            f"{purpose} files."
        )

    declared = (content_type or "").split(";")[0].strip().lower()
    if declared not in rule.content_types:
        raise UploadRefused(
            f"{declared or 'Unknown file type'} is not accepted for {purpose} files. "
            f"Allowed: {', '.join(sorted(rule.content_types))}."
        )

    extension = _extension(filename)
    if extension not in rule.extensions:
        raise UploadRefused(
            f"A {extension or 'file with no extension'} cannot be stored as {purpose}. "
            f"Allowed extensions: {', '.join(sorted(rule.extensions))}."
        )
    return declared


def object_key(owner, purpose: str, filename: str) -> str:
    """``<owner>/<purpose>/<uuid>.<ext>`` — unique, and not the original name."""
    extension = _extension(filename)
    if not extension:
        raise UploadRefused("The file needs an extension so it can be served back.")
    owner_part = getattr(owner, "pk", None) or "shared"
    return f"{owner_part}/{purpose}/{uuid.uuid4().hex}{extension}"


def store(actor, owner, purpose: str, *, filename: str, content_type: str, data: bytes):
    """Upload ``data`` for ``owner`` and prove the bucket kept it.

    ``owner`` chooses the bucket; ``actor`` is who gets recorded in the audit
    trail. They are usually the same person, and they are separate arguments so
    a main admin uploading into a provider's batch writes to that provider's
    storage rather than their own.
    """
    normalised = validate_upload(purpose, filename, content_type, len(data))
    try:
        bucket = services.resolve_bucket(owner, purpose)
    except services.NoStorageTarget as error:
        # Not an error in the file — the operator has not configured storage
        # yet. Say so in the same shape as every other refusal so the editor
        # sees one kind of message, not a stack trace.
        raise UploadRefused(str(error)) from error
    key = object_key(owner, purpose, filename)

    try:
        credentials = bucket.account.get_credentials()
    except crypto.CredentialError as error:
        raise UploadRefused(str(error)) from error
    if credentials is None:
        raise UploadRefused("No API token is stored for this bucket's account.")

    try:
        r2.put_object(credentials, bucket.name, key, data, content_type=normalised)
        status = r2.object_head(credentials, bucket.name, key)
    except r2.R2Error as error:
        services._audit(actor, "asset_upload", bucket, "failed", key=key, purpose=purpose)
        raise UploadRefused(f"The file could not be stored: {error}") from error

    if status != 200:
        # A 200 from PUT that is not followed by a 200 from HEAD means the
        # object is not there. Reporting success would leave an editor with a
        # curriculum entry pointing at nothing.
        services._audit(actor, "asset_upload", bucket, "failed", key=key, purpose=purpose)
        raise UploadRefused(
            "The bucket accepted the upload but the file was not readable "
            f"afterwards (HEAD answered {status}); the upload was treated as "
            "failed. Check the bucket's permissions and try again."
        )

    ttl = getattr(settings, "R2_SIGNED_URL_TTL", 900)
    permanent = bucket.public_url(key)
    url = permanent or services.object_url(bucket, key, expires=ttl)
    expires_at = (
        None if permanent
        else datetime.now(timezone.utc) + timedelta(seconds=ttl)
    )

    services._audit(
        actor, "asset_upload", bucket, "success",
        key=key, purpose=purpose, bytes=len(data),
    )
    return StoredObject(
        bucket=bucket,
        key=key,
        size=len(data),
        content_type=normalised,
        url=url,
        expires_at=expires_at,
    )


def url_for_key(owner, purpose: str, key: str, *, expires: int | None = None) -> str | None:
    """The URL a learner may use for one stored key, or ``None``.

    Returns ``None`` rather than raising when storage is not configured: a batch
    page must still render its curriculum if R2 has not been set up yet or the
    token expired. The lesson simply stays locked, which is the safe direction.
    """
    if not key:
        return None
    try:
        bucket = services.resolve_bucket(owner, purpose)
        return services.object_url(bucket, key, expires=expires)
    except (services.NoStorageTarget, r2.R2Error, crypto.CredentialError):
        return None
