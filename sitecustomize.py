"""Make ``backend/`` importable when Python starts from the repository root.

Kept for the deployment host, which resolves a Django project relative to the
repository root while this project keeps its Django package in ``backend/``.
Python imports this module automatically at start-up when the repository root is
on ``sys.path``; when it is not (``manage.py`` run from ``backend/``, the test
runner, gunicorn with an explicit ``config.wsgi``), nothing here runs and
nothing changes.
"""

import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if os.path.isdir(BACKEND_DIR) and BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
