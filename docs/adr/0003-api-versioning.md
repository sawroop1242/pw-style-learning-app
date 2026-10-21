# ADR 0003: API Versioning

**Date:** 2026-10-20  
**Status:** Accepted

## Context

The API needs versioning to support future breaking changes without breaking existing clients.

## Decision

Use URL prefix versioning: `/api/v1/` for all API endpoints starting Milestone 4. Router namespace: `v1`.

## Rationale

1. **Explicit and visible** - Version in URL makes it obvious which version clients are using
2. **Easy routing** - Simple to route to different viewsets per version
3. **CDN/cache friendly** - Different versions can be cached separately
4. **Industry standard** - Used by GitHub, Stripe, AWS, etc.
5. **No header parsing** - Simpler client implementation

## Implementation

```python
# config/urls.py
urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("courses.urls", namespace="v1")),
    path("api/v1/", include("accounts.urls", namespace="v1")),
]
```

## Consequences

- All new endpoints in M4+ will be under `/api/v1/`
- Existing `/api/` endpoints will be deprecated (redirect or 410)
- Client must specify version in requests
- Easy to add `/api/v2/` later without breaking v1 clients