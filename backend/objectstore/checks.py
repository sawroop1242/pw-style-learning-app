"""Startup warnings for the storage app.

The panel stores its credentials encrypted. If no explicit key is configured,
the key is derived from ``SECRET_KEY`` — fine locally, and a trap in production
the day ``SECRET_KEY`` is rotated, because every stored token becomes
unreadable. ``manage.py check`` runs in the deploy script, so the warning lands
in the build log rather than in a support ticket.
"""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def storage_encryption_key_check(app_configs, **kwargs):
    if settings.ENVIRONMENT not in {"staging", "production"}:
        return []
    if getattr(settings, "R2_CREDENTIAL_KEYS", None):
        return []

    from django.db.utils import OperationalError, ProgrammingError

    from .models import R2Account

    try:
        has_tokens = R2Account.objects.exclude(access_key_id_enc="").exists()
    except (OperationalError, ProgrammingError):
        # `manage.py check` runs before `migrate` in the deploy script, so on a
        # fresh database the table does not exist yet. A check must never be
        # the thing that breaks a deploy.
        return []
    if not has_tokens:
        # Nothing stored yet: no need to nag, but say it once for the operator.
        return []
    return [
        Warning(
            "Stored Cloudflare R2 credentials use a key derived from SECRET_KEY.",
            hint=(
                "Set R2_CREDENTIAL_KEYS to a comma-separated list of keys generated "
                "with `python manage.py r2_rotate_key --new-key`, then run "
                "`python manage.py r2_rotate_key --apply`. Rotating SECRET_KEY "
                "without this makes every stored API token unreadable."
            ),
            id="objectstore.W001",
        )
    ]
