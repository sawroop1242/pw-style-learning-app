"""WSGI entry point at the repository root, for hosts that expect one there.

The Django project lives in ``backend/`` (``config``/``courses``/``accounts``),
so this module puts ``backend/`` on ``sys.path`` before importing anything from
Django, exactly as ``manage.py`` does.

The host loads this module when starting a function; gunicorn and the Procfile
keep using ``config.wsgi`` directly.
"""

import os
import sys
import traceback

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _fallback(detail):
    """TEMPORARY: answer with the startup traceback instead of an opaque 500.

    A crashed serverless function only shows "FUNCTION_INVOCATION_FAILED", so
    until the deployment is understood the failure has to come back through the
    only channel that exists: the response. Remove this once it is fixed.
    """

    def application(environ, start_response):
        body = detail.encode("utf-8", "replace")
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    return application


try:
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()
except Exception:
    application = _fallback(traceback.format_exc())

app = application
