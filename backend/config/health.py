from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """Liveness: the process is up. Deliberately does not touch the database,
    so a slow or missing database cannot make the platform restart a healthy
    container."""
    return JsonResponse({"status": "ok"})


@require_GET
def readiness(request):
    """Readiness: this instance can actually serve requests.

    Checks that the database answers, because a Django deployment with an
    unreachable database looks "up" and then fails on every page. Returns 503
    with a short reason and never echoes a connection string or a password.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as error:  # noqa: BLE001 - any failure means "not ready"
        return JsonResponse(
            {
                "status": "unavailable",
                "database": "unreachable",
                "reason": type(error).__name__,
                "checked_at": timezone.now().isoformat(),
            },
            status=503,
        )

    return JsonResponse(
        {
            "status": "ok",
            "database": "ok",
            "vendor": connection.vendor,
            "checked_at": timezone.now().isoformat(),
        }
    )
