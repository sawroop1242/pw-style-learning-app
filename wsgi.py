"""WSGI entry point at the repository root, for hosts that expect one there.

Vercel's Django integration builds a single WSGI function from the project and
looks for ``wsgi.py`` beside ``manage.py``. The app itself lives in ``backend/``
(``config``/``courses``/``accounts``), so ``manage.py`` and this module put
``backend/`` on ``sys.path`` before importing anything from Django.

Nothing here is Vercel-specific beyond the entry point: gunicorn and the Procfile
keep using ``config.wsgi`` directly, and the path setup below is a no-op when the
process was already started from ``backend/``.
"""

import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
app = application  # some hosts look for `app` instead of `application`
