"""WSGI entry point at the repository root, for hosts that expect one there.

The Django project lives in ``backend/`` (``config``/``courses``/``accounts``),
so this module puts ``backend/`` on ``sys.path`` before importing anything from
Django, exactly as ``manage.py`` does.

The host loads this module when starting a function; gunicorn and the Procfile
keep using ``config.wsgi`` directly.

TEMPORARY instrumentation: the deployment answers an opaque 500 on every path,
so start-up stages are recorded in the database and an import failure comes back
in the response. Remove both once the deployment is understood.
"""

import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _report(stage, detail=""):
    try:
        import psycopg

        url = os.environ.get("DATABASE_URL")
        if not url:
            return
        with psycopg.connect(url, connect_timeout=8) as conn:
            conn.execute(
                "create table if not exists deploy_diagnostics ("
                "id bigserial primary key,"
                "created_at timestamptz not null default now(),"
                "stage text not null,"
                "detail text not null)"
            )
            conn.execute(
                "insert into deploy_diagnostics (stage, detail) values (%s, %s)",
                (stage, (detail or "")[-6000:]),
            )
            conn.commit()
    except Exception:
        traceback.print_exc()


_report("module-imported", "file=%s cwd=%s" % (__file__, os.getcwd()))

try:
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()
    _report("startup-ok", "sys.path[0:4]=%r" % (sys.path[0:4],))
except Exception:
    _detail = traceback.format_exc()
    _report("startup-failed", _detail)

    def application(environ, start_response):
        body = _detail.encode("utf-8", "replace")
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]


app = application
