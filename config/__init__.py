"""The Django project package, importable from the repository root.

The real project lives in ``backend/config`` -- that is where ``manage.py``,
``settings.py``, ``urls.py`` and the apps are, and it is how the app has always
been run. A hosted Django build instead starts from the repository root and
resolves ``WSGI_APPLICATION`` ("config.wsgi.application") to the *path*
``config/wsgi.py`` next to ``manage.py``, so that file has to exist here too.

This package makes both worlds true at once:

* ``config/wsgi.py`` and ``config/asgi.py`` here are the two entry points the
  host looks for -- real files, so its file-path check succeeds;
* ``settings``, ``urls``, ``views`` and the rest still come from
  ``backend/config``, because that directory is appended to this package's
  search path, so there is exactly one settings module and no code is copied;
* ``backend/`` is put on ``sys.path`` so ``courses`` and ``accounts`` import
  the same way they do under ``manage.py``.
"""

import os
import sys

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_ROOT_DIR, "backend")

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

__path__ = [
    os.path.dirname(os.path.abspath(__file__)),
    os.path.join(_BACKEND_DIR, "config"),
]
