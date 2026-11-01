"""What the admin and the rest of the app ask the storage targets to do.

Three jobs live here, and nothing else should reach past them into ``r2``:

* ``test_bucket`` — run a bounded, read-only connection test and record what
  happened on the bucket, on the account and in the audit log;
* ``resolve_bucket`` — pick the bucket an upload should go to (the owner's
  default for that purpose, else their oldest enabled one);
* ``signed_url`` / ``object_url`` — the URL a learner or the admin UI may use.

Every failure path returns a sentence an administrator can act on. None of them
includes an access key, a secret, a signature or a provider stack trace.
"""

from __future__ import annotations

from accounts.models import AuditEvent

from . import crypto, r2
from .models import PURPOSE_DEFAULT_FIELDS, PURPOSE_FIELDS, Purpose, R2Account, R2Bucket

__all__ = [
    "NoStorageTarget",
    "test_bucket",
    "test_account",
    "resolve_bucket",
    "object_url",
]


class NoStorageTarget(Exception):
    """No bucket is configured for the requested purpose."""


def _audit(actor, action: str, target, outcome: str, **metadata) -> None:
    """Record the event, with ids and numbers only.

    ``metadata`` is filtered to scalars so a caller cannot accidentally put a
    token or an object body into the audit trail.
    """
    safe = {
        key: value
        for key, value in metadata.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }
    AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target_type=type(target).__name__ if target is not None else "",
        target_id=str(getattr(target, "pk", "")) if target is not None else "",
        outcome=outcome,
        metadata=safe,
    )


def test_bucket(bucket: R2Bucket, *, actor=None, write: bool = False) -> r2.BucketCheck:
    """Prove the account id, token and bucket name belong together.

    Read-only by default. ``write=True`` additionally uploads a 12-byte probe
    object and deletes it again, which is how ``manage.py r2_check --write``
    tells "can list" apart from "can upload".
    """
    account = bucket.account
    if not account.is_active:
        verdict = r2.BucketCheck(False, None, "This Cloudflare account is switched off.")
        bucket.mark_checked(ok=False, detail=verdict.message)
        _audit(actor, "r2.bucket.test", bucket, "failure", reason="account_disabled")
        return verdict

    try:
        credentials = account.get_credentials()
    except crypto.CredentialError as exc:
        verdict = r2.BucketCheck(False, None, str(exc))
        bucket.mark_checked(ok=False, detail=verdict.message)
        _audit(actor, "r2.bucket.test", bucket, "failure", reason="credential_unreadable")
        return verdict

    if credentials is None:
        verdict = r2.BucketCheck(False, None, "No API token is stored for this account.")
        bucket.mark_checked(ok=False, detail=verdict.message)
        _audit(actor, "r2.bucket.test", bucket, "failure", reason="no_credentials")
        return verdict

    verdict = r2.check_bucket(credentials, bucket.name)

    if verdict.ok and write:
        key = "studyspace-probes/connection-check.txt"
        try:
            r2.put_object(credentials, bucket.name, key, b"StudySpace probe", "text/plain")
            r2.delete_object(credentials, bucket.name, key)
            verdict = r2.BucketCheck(True, verdict.status, verdict.message + " Upload and delete worked.")
        except r2.R2Error as exc:
            verdict = r2.BucketCheck(
                False,
                exc.status,
                f"Reading works, but writing failed: {exc}",
            )

    bucket.mark_checked(ok=verdict.ok, detail=verdict.message)
    _audit(
        actor,
        "r2.bucket.test",
        bucket,
        "success" if verdict.ok else "failure",
        status=verdict.status,
        write=write,
    )
    return verdict


def test_account(account: R2Account, *, actor=None) -> list[tuple[R2Bucket, r2.BucketCheck]]:
    """Test every bucket under an account, newest result per bucket."""
    return [(bucket, test_bucket(bucket, actor=actor)) for bucket in account.buckets.all()]


def resolve_bucket(owner, purpose: str) -> R2Bucket:
    """The bucket an upload for ``purpose`` should go to.

    Order: the owner's default for that purpose, then any enabled bucket that
    allows it (oldest first). Raises :class:`NoStorageTarget` with a sentence
    that names the missing setting.
    """
    if purpose not in PURPOSE_FIELDS:
        raise ValueError(f"Unknown storage purpose: {purpose!r}")

    queryset = R2Bucket.objects.filter(
        account__owner=owner,
        account__is_active=True,
        enabled=True,
        **{PURPOSE_FIELDS[purpose]: True},
    ).select_related("account")

    default_field = PURPOSE_DEFAULT_FIELDS[purpose]
    bucket = queryset.filter(**{default_field: True}).first() or queryset.order_by("created_at", "id").first()
    if bucket is None:
        label = dict(Purpose.choices).get(purpose, purpose)
        raise NoStorageTarget(
            f"No R2 bucket is set up for {label.lower()}. Add one under "
            "Storage → Cloudflare accounts, tick the purpose and enable it."
        )
    return bucket


def object_url(bucket: R2Bucket, key: str, *, expires: int | None = None) -> str:
    """A URL for one object: permanent when the bucket is public, else signed."""
    permanent = bucket.public_url(key)
    if permanent:
        return permanent
    try:
        credentials = bucket.account.get_credentials()
    except crypto.CredentialError as exc:
        raise r2.R2Error(str(exc)) from exc
    if credentials is None:
        raise r2.R2Error("No API token is stored for this bucket's account.")
    return r2.presign_get(credentials, bucket.name, key, expires=expires)
