#!/usr/bin/env python
"""Manage the Django project that lives in ``backend/``.

The project predates hosted deployments: settings and ``manage.py`` live under
``backend/`` so the repository root can hold the static front end, docs and
tooling. Vercel's zero-configuration Django support looks for ``manage.py`` at
the *project root* to find the WSGI entrypoint and the static-file
configuration, so this file is that marker. It adds ``backend/`` to ``sys.path``
and forwards every command to Django, which means

    python manage.py check
    python manage.py migrate
    python manage.py collectstatic --noinput

behave exactly as they do inside ``backend/``. Nothing is duplicated here.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.management import execute_from_command_line  # noqa: E402

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
