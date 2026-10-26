from django.contrib import admin
from django.urls import include, path, re_path

from . import views as site
from .health import healthz, readiness

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("healthz/ready/", readiness, name="ready"),
    path("admin/", admin.site.urls),
    path("api/", include("courses.urls")),
    path("api/", include("accounts.urls")),
    # The static front end, served from the same origin as the API. Registered
    # last so /admin/, /api/ and /static/ always win; the patterns themselves
    # only match the site's own files.
    path("", site.page, {"name": "index.html"}, name="home"),
    re_path(r"^(?P<name>[a-z0-9][a-z0-9-]*\.html)$", site.page, name="page"),
    re_path(r"^(?P<path>assets/.+|manifest\.webmanifest|sw\.js|offline\.html|splash\.html)$", site.asset),
]
