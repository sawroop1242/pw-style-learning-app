"""Import shim for the Django project package, which lives in ``backend/config``.

``manage.py`` (and gunicorn) run from ``backend/``, so ``config`` is simply the
package next to them. A serverless host instead resolves ``DJANGO_SETTINGS_MODULE``
and ``WSGI_APPLICATION`` from the repository root, where no ``config`` package
exists -- and importing the entrypoint is the first thing a request does, so
every request failed before any view ran.

This module makes the name importable from the root as well: it puts ``backend/``
on ``sys.path`` (so ``courses``, ``accounts`` and friends resolve) and points the
package path at the real ``backend/config`` directory, so ``config.settings``,
``config.urls``, ``config.wsgi`` and ``config.asgi`` are the same modules they
always were. When the interpreter already runs from ``backend/`` this file is not
on ``sys.path`` and nothing here is used.
"""

import os
import sys

BACKEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"
)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

__path__ = [os.path.join(BACKEND_DIR, "config")]
