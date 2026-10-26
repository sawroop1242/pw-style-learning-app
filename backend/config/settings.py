import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
if ENVIRONMENT not in {"development", "test", "staging", "production"}:
    raise ImproperlyConfigured(
        "ENVIRONMENT must be one of: development, test, staging, production."
    )


def env_bool(name, default):
    """Parse a boolean environment variable without silently accepting typos."""
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(
        f"{name} must be a boolean value (true/false, 1/0, yes/no, on/off)."
    )


DEBUG = env_bool("DEBUG", ENVIRONMENT in {"development", "test"})
if ENVIRONMENT in {"staging", "production"} and DEBUG:
    raise ImproperlyConfigured(
        f"DEBUG must be false when ENVIRONMENT={ENVIRONMENT}."
    )

_secret_key = os.getenv("SECRET_KEY", "").strip()
if not _secret_key:
    if ENVIRONMENT in {"staging", "production"}:
        raise ImproperlyConfigured(
            f"SECRET_KEY must be set when ENVIRONMENT={ENVIRONMENT}."
        )
    _secret_key = "django-insecure-local-development-key-do-not-use-in-production"
elif ENVIRONMENT in {"staging", "production"} and (
    len(_secret_key) < 50 or "change-me" in _secret_key.lower()
):
    raise ImproperlyConfigured(
        "Staging/production SECRET_KEY must be a long, randomly generated secret (at least 50 characters)."
    )
SECRET_KEY = _secret_key

_default_hosts = "localhost,127.0.0.1" if ENVIRONMENT in {"development", "test"} else ""
# Add testserver for Django test client
if ENVIRONMENT == "test":
    _default_hosts += ",testserver"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", _default_hosts).split(",")
    if host.strip()
]
if ENVIRONMENT in {"staging", "production"} and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        f"ALLOWED_HOSTS must list the deployed hostnames when ENVIRONMENT={ENVIRONMENT}."
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "accounts",
    "courses",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
# The deployment host reads this setting, turns "config.wsgi.application" into
# the file path config/wsgi.py and loads that file directly, so the entry point
# lives at the repository root and points back at this project. Only one of
# WSGI_APPLICATION / ASGI_APPLICATION may be set: when both are present the
# ASGI one wins, and the WSGI server then refuses to start.
WSGI_APPLICATION = "config.wsgi.application"

# Serverless platforms bill per instance and freeze it between requests, so a
# long-lived connection is a leak rather than a saving: set DB_CONN_MAX_AGE=0
# there. A long-running host keeps 600 seconds, which is what it is for.
DB_CONN_MAX_AGE = int(os.getenv("DB_CONN_MAX_AGE", "0" if ENVIRONMENT in {"development", "test"} else "600"))

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=DB_CONN_MAX_AGE,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Manifest hashing (for far-future cache headers) is only needed in
# production; without a collectstatic manifest, admin pages raise
# "Missing staticfiles manifest entry" in development and tests.
if ENVIRONMENT == "production":
    STATICFILES_STORAGE_BACKEND = "whitenoise.storage.CompressedManifestStaticFilesStorage"
else:
    STATICFILES_STORAGE_BACKEND = "whitenoise.storage.CompressedStaticFilesStorage"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": STATICFILES_STORAGE_BACKEND},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080"
        if ENVIRONMENT in {"development", "test"}
        else "",
    ).split(",")
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication"
    ],
    # Deny by default: every public endpoint must opt in to AllowAny
    # explicitly, so a new view cannot leak data by omission.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated"
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle"
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Per-IP ceiling for anonymous reads. Raise it if a whole campus shares
        # one address; auth endpoints add their own tighter, scoped limits.
        "anon": os.getenv("THROTTLE_ANON", "100/minute"),
        "user": os.getenv("THROTTLE_USER", "1000/minute"),
    },
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Behind a TLS-terminating proxy the request arrives over HTTP; without this
# header SECURE_SSL_REDIRECT would loop forever.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_HTTPONLY = True
# SameSite is env-driven because the same code runs first-party in production
# and inside a preview iframe on a different top-level site. There, "Lax" is not
# sent on a form POST, so Django reports "CSRF cookie not set" and the admin
# cannot log in. "None" (which browsers only honour together with "Secure") is
# the preview's setting; production keeps the default.
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)

if not DEBUG:
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", ENVIRONMENT == "production"
    )
    # `preload` only adds the directive to the header; submitting the domain to
    # the browser preload list stays a manual, deliberate step.
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", ENVIRONMENT == "production")

# Email configuration
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "StudySpace <noreply@studyspace.local>")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Validate mutually incompatible TLS/SSL settings
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be true.")

# OTP configuration
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))

# Logging: JSON-ish single-line records that stay readable in a log drain and
# never include secrets or request bodies.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
