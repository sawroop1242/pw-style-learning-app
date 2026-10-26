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


def _report(stage, detail):
    """Temporary diagnostics: record a failure where it can actually be read.

    A crashed serverless function only returns an opaque 500 page, so the
    traceback is written straight to the database over psycopg (which does not
    need Django, or the app it failed to build).
    """
    try:
        import psycopg

        url = os.environ.get("DATABASE_URL")
        if not url:
            return
        with psycopg.connect(url, connect_timeout=10) as conn:
            conn.execute(
                "create table if not exists deploy_diagnostics ("
                "id bigserial primary key,"
                "created_at timestamptz not null default now(),"
                "stage text not null,"
                "detail text not null)"
            )
            conn.execute(
                "insert into deploy_diagnostics (stage, detail) values (%s, %s)",
                (stage, detail[-6000:]),
            )
            conn.commit()
    except Exception:
        traceback.print_exc()


class _DiagnosingApp:
    """Pass requests through, recording any unhandled exception first."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except Exception:
            _report("request %s" % environ.get("PATH_INFO"), traceback.format_exc())
            start_response(
                "500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")]
            )
            return [b"Server error\n"]


try:
    from django.core.wsgi import get_wsgi_application

    application = _DiagnosingApp(get_wsgi_application())
except Exception:
    _report("startup", traceback.format_exc())
    raise

app = application
