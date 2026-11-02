import os
from datetime import timedelta
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
    # Cloudflare R2 storage targets: per-sub-admin accounts and buckets.
    "objectstore",
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
    # Last in, first out: the policy is attached to whatever the view returns,
    # including the static shell served by config.views.
    "config.middleware.ContentSecurityPolicyMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-level overrides (the admin's branding and index) live here.
        # They must come before APP_DIRS: django.contrib.admin ships its own
        # admin/index.html, and an app directory would lose to it.
        "DIRS": [BASE_DIR / "templates"],
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

# --- Cloudflare R2 storage -------------------------------------------------
# Credentials for storage targets are encrypted before they touch the database.
# `R2_CREDENTIAL_KEYS` is a comma-separated list of urlsafe-base64 32-byte keys
# (generate one with `python manage.py r2_rotate_key --new-key`). The first key
# encrypts; every key is tried when decrypting, so a key can be rotated without
# a downtime window. With no keys configured, a key is derived from SECRET_KEY —
# fine for development, and changing SECRET_KEY then makes stored tokens
# unreadable, which is why production should set the variable explicitly.
R2_CREDENTIAL_KEYS = [
    key.strip() for key in os.getenv("R2_CREDENTIAL_KEYS", "").split(",") if key.strip()
]
# A connection test must never hold a request open. Eight seconds is longer
# than a healthy R2 round-trip and shorter than a user's patience.
R2_REQUEST_TIMEOUT = float(os.getenv("R2_REQUEST_TIMEOUT", "8"))
# Signed URLs are a fallback for private buckets; a public custom domain or the
# r2.dev subdomain (set per bucket) is preferred.
R2_SIGNED_URL_TTL = int(os.getenv("R2_SIGNED_URL_TTL", "900"))

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

# DRF's throttles count through the cache. Django's default is per-process
# local memory, so with more than one worker — or on a serverless platform,
# where every instance is its own process — a client gets the full allowance
# from each of them. A shared cache is what makes the limit actually a limit.
CACHE_URL = (
    os.getenv("CACHE_URL", "").strip() or os.getenv("REDIS_URL", "").strip()
)
if CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": CACHE_URL,
            # A throttle window is a minute; a day-long key would only keep
            # counters alive after the incident that filled them.
            "TIMEOUT": 300,
        }
    }
else:
    # Development and single-process use. `manage.py check` warns when this is
    # reached in staging or production — see accounts/checks.py.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "studyspace-local",
        }
    }

# ADR 0004. These were never in the settings file, so SimpleJWT's defaults
# applied: a 5-minute access token (fine) but a 1-day refresh token with no
# rotation and no blacklisting, so a stolen refresh token stayed valid for a
# day and could not be revoked. The values below are the ones the ADR records.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

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
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "PAGE_SIZE": 20,
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

# --------------------------------------------------------------------------- #
# Content Security Policy
# --------------------------------------------------------------------------- #

# No third-party scripts, fonts or styles: everything the pages load is served
# from this origin, so `'self'` is the whole story for scripts. Styles keep
# `'unsafe-inline'` for the inline `style="…"` attributes used by the shell and
# the generated markup — CSS cannot execute, and every dynamic value that goes
# into those strings is escaped by the same helper as the text.
#
# Frames are allowed from any https origin because a provider configures its own
# video and PDF host; scripts inside those frames are not ours to police, and
# `frame-ancestors 'none'` stops anyone framing *this* site.
CONTENT_SECURITY_POLICY = os.getenv(
    "CONTENT_SECURITY_POLICY",
    " ".join(
        [
            "default-src 'self';",
            "base-uri 'self';",
            "object-src 'none';",
            "frame-ancestors 'none';",
            "form-action 'self';",
            "script-src 'self';",
            "style-src 'self' 'unsafe-inline';",
            "img-src 'self' data: blob: https:;",
            "media-src 'self' https:;",
            "font-src 'self' data:;",
            "frame-src 'self' https:;",
            "connect-src 'self' https:;",
            "worker-src 'self';",
            "manifest-src 'self';",
        ]
    ),
)

# Roll a change out in this mode first: the browser reports violations instead
# of blocking them. `manage.py check` does not care either way.
CSP_REPORT_ONLY = env_bool("CSP_REPORT_ONLY", False)

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
# Password-reset mail has three possible transports, picked in this order:
#
#   1. an explicit EMAIL_BACKEND, so an operator can always override;
#   2. an HTTP provider key — Brevo or Resend — which needs one secret instead
#      of a host/port/username/password set and works where SMTP is blocked;
#   3. console while DEBUG (prints the letter in the terminal), SMTP otherwise.
#
# The API keys are read here, before EMAIL_BACKEND is resolved, because the
# presence of a key is what selects the transport.
BREVO_API_KEY = (os.getenv("BREVO_API_KEY") or "").strip()
RESEND_API_KEY = (os.getenv("RESEND_API_KEY") or "").strip()
MAIL_API_BACKEND = (
    "accounts.mail_backends.BrevoEmailBackend"
    if BREVO_API_KEY
    else "accounts.mail_backends.ResendEmailBackend"
    if RESEND_API_KEY
    else ""
)

EMAIL_BACKEND = (
    os.getenv("EMAIL_BACKEND", "").strip()
    or MAIL_API_BACKEND
    or (
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    )
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "StudySpace <noreply@studyspace.local>")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
# A provider that stops answering must not hold a password-reset request open
# until the platform kills the function: the code is generated inside that
# request, so a 30s hang is 30s of a locked worker doing nothing.
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))

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
