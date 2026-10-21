# ADR 0004: Token Storage and Management

**Date:** 2026-10-20  
**Status:** Accepted

## Context

The application uses JWT tokens for authentication via `djangorestframework-simplejwt`. Need to decide on token storage, rotation, and invalidation strategy.

## Decision

Continue using SimpleJWT with the following configuration:
- Access token lifetime: 30 minutes
- Refresh token lifetime: 7 days
- Enable `token_blacklist` app for refresh token invalidation
- Rotate refresh tokens on each use (`ROTATE_REFRESH_TOKENS = True`)
- Blacklist old refresh tokens after rotation (`BLACKLIST_AFTER_ROTATION = True`)
- Invalidate all refresh tokens on password change and logout

## Rationale

1. **Stateless access tokens** - Short-lived access tokens (30 min) limit exposure window
2. **Server-side revocation** - Blacklist app provides server-side revocation for refresh tokens
3. **Rotation** - Rotating refresh tokens limits damage from token theft
4. **Security events** - Password change and logout invalidate all tokens (already implemented)
5. **Proven library** - SimpleJWT is widely used and maintained

## Configuration (in settings.py)

```python
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
```

## Consequences

- Refresh tokens stored in database (OutstandingToken, BlacklistedToken tables)
- Requires `rest_framework_simplejwt.token_blacklist` in INSTALLED_APPS
- Logout and password change must explicitly blacklist tokens (already implemented)
- Access tokens cannot be revoked individually (short lifetime mitigates this)