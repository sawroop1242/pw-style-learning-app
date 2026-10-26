"""Serve the static front end from Django.

In development the site is served by ``tools/serve.py``, which proxies ``/api``
to Django. On a single-process host there is no second server to do that, so
Django serves the pages and the API together — one origin, one URL, no CORS and
the same relative ``/api`` base the pages already use.

Only these paths are ever served from ``frontend/``:

* ``assets/...`` — CSS, JS, images, icons
* the PWA files: ``manifest.webmanifest``, ``sw.js``, ``offline.html``,
  ``splash.html``
* the pages themselves, as ``<name>.html``

``/admin/``, ``/api/`` and ``/static/`` are matched by their own url patterns
first, so nothing here can shadow them. Requests outside the list 404, so the
directory cannot be browsed and a new file never becomes public by accident.
"""

from __future__ import annotations

import mimetypes
from http import HTTPStatus
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe

#: ``backend/config/views.py`` -> repository root -> ``frontend/``
FRONTEND_ROOT = (Path(settings.BASE_DIR).parent / "frontend").resolve()

#: Files at the site root that are not pages.
ROOT_FILES = ("manifest.webmanifest", "sw.js", "offline.html", "splash.html")

#: Extensions that must not be cached aggressively: a deploy should be visible
#: on the next request, not when a year-old cache entry expires.
NO_STORE = {".html", ".webmanifest", ".js"}

EXTRA_TYPES = {
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
}


def _resolve(relative: str) -> Path:
    """Map a URL path to a file inside ``frontend/``, or 404."""
    candidate = (FRONTEND_ROOT / relative).resolve()
    if candidate != FRONTEND_ROOT and FRONTEND_ROOT not in candidate.parents:
        raise Http404("Not found")
    if not candidate.is_file():
        raise Http404("Not found")
    return candidate


def _content_type(path: Path) -> str:
    """A file's media type, with an explicit charset for anything text.

    ``FileResponse`` does not add ``charset`` by itself, and the pages carry
    non-ASCII copy — without it a browser may fall back to Latin-1.
    """
    media_type = (
        EXTRA_TYPES.get(path.suffix)
        or mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )
    if "charset" in media_type:
        return media_type
    if media_type.startswith("text/") or media_type in {
        "application/json",
        "application/manifest+json",
        "image/svg+xml",
    }:
        return f"{media_type}; charset=utf-8"
    return media_type


@require_safe
def page(request, name: str = "index.html"):
    """One of the site's HTML pages."""
    if not name.endswith(".html"):
        raise Http404("Not found")
    return _serve(_resolve(name), cache=False)


@require_safe
def asset(request, path: str):
    """A file under ``assets/`` or one of the PWA files at the site root."""
    if not path.startswith("assets/") and path not in ROOT_FILES:
        raise Http404("Not found")
    return _serve(_resolve(path), cache=path not in NO_STORE)


def _serve(file_path: Path, *, cache: bool) -> FileResponse:
    response = FileResponse(open(file_path, "rb"), content_type=_content_type(file_path))
    if cache:
        # Media changes only with a deploy, and a stale icon is harmless.
        response["Cache-Control"] = "public, max-age=3600"
    else:
        response["Cache-Control"] = "no-store"
    if file_path.name == "sw.js":
        # A service worker must be re-fetched on every page load, and it is
        # allowed to control the whole origin, not just its own directory.
        response["Cache-Control"] = "no-cache"
        response["Service-Worker-Allowed"] = "/"
    if response.status_code == HTTPStatus.OK:
        response["X-Content-Type-Options"] = "nosniff"
    return response
