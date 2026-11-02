"""Settings for looking at the console in a phone-sized preview frame.

Only ever used by ``manage.py runserver --settings=config.settings_preview``
from this repository: the running app sets nothing here. A preview is served
inside an iframe on another origin, which is exactly the situation Django's
cookie policy is designed to make awkward — a session cookie that is not
``SameSite=None`` is simply not sent, so signing in would loop back to the login
form. That is the only reason the cookie rules change.

Never point a deployment at this module: it allows every host and sets DEBUG.
"""

from .settings import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = [
    "https://*.e2b.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
SESSION_COOKIE_SAMESITE = "None"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SECURE = True
