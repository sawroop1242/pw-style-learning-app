"""ASGI entry point at the repository root.

Present for completeness: the host keeps serving the WSGI application, which is
what ``WSGI_APPLICATION`` names. Keeping the file means the same layout works
for any ASGI server (``uvicorn config.asgi:application``).
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
app = application
