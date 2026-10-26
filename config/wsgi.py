"""WSGI entry point at the repository root.

The host derives this path from ``WSGI_APPLICATION`` (``config.wsgi.application``)
and loads the file directly, so it must exist here. Everything else -- settings,
URLs, apps -- is the real project in ``backend/config``, reached through this
package's ``__path__``.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
app = application
