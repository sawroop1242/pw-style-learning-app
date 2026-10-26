"""Serverless entry point for the Django application.

Why this file exists: the host's Django auto-detection has to import
``WSGI_APPLICATION`` from the repository root, but this project's Django package
lives in ``backend/config``. Every request therefore died with an opaque
``FUNCTION_INVOCATION_FAILED`` before a single view ran -- including the
database-free ``/healthz/``, while pre-built static files kept answering 200.

Declaring the handler explicitly removes the guesswork: ``api/index.py`` is a
plain Python function whose WSGI callable is ``app``, and every path is
rewritten to it. ``backend/`` goes on ``sys.path`` first so ``config.settings``,
``config.urls`` and the ``courses``/``accounts`` apps resolve exactly as they do
under ``manage.py``.
"""

import os
import sys
import traceback

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
for _path in (ROOT_DIR, BACKEND_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _failure(exc: BaseException):
    """Temporary diagnostic: report a start-up crash instead of a blank 500."""

    detail = "".join(traceback.format_exception(exc))[-6000:]

    def app(environ, start_response):
        body = detail.encode("utf-8", "replace")
        start_response(
            "500 Internal Server Error",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("X-Studyspace-Startup", "failed"),
            ],
        )
        return [body]

    return app


try:
    from django.core.wsgi import get_wsgi_application

    app = get_wsgi_application()
    application = app
except BaseException as exc:  # pragma: no cover - start-up guard only
    app = application = _failure(exc)
