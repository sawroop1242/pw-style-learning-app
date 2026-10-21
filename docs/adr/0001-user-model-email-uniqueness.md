# ADR 0001: User Model and Email Uniqueness

**Date:** 2026-10-20  
**Status:** Accepted

## Context

The application needs a user model that supports:
- Authentication via username or email
- Case-insensitive email uniqueness
- Role-based access (student, sub_admin, main_admin)
- Profile extension with audit trail

## Decision

Keep Django's default `User` model (`django.contrib.auth.models.User`) rather than implementing a custom user model. Enforce case-insensitive uniqueness for both username and email at the application level (serializer validation).

## Rationale

1. **No migration complexity** - Custom user model must be set before first migration; we're past that point
2. **Django ecosystem compatibility** - Default User works with all built-in auth views, admin, and third-party packages
3. **SimpleJWT integration** - Works out of the box with default User
4. **Application-level enforcement** - We already normalize and validate case-insensitively in serializers (verified in tests)

## Consequences

- Username and email uniqueness enforced in `UserRegistrationSerializer` and `CustomTokenObtainPairSerializer`
- Database-level unique constraints on `User.username` and `User.email` remain case-sensitive (PostgreSQL default)
- Application must always normalize before queries (using `iexact` or lowercase)
- Cannot add extra fields to User model; use `Profile` one-to-one for extensions (already implemented)