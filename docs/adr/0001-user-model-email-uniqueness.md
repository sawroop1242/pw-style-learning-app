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

Keep Django's default `User` model (`django.contrib.auth.models.User`) rather than implementing a custom user model.

Case-insensitive uniqueness for username and email is enforced by the
**database**, through functional unique indexes added in
`accounts/migrations/0002_case_insensitive_unique_identity.py`:

```
CREATE UNIQUE INDEX accounts_user_username_lower_uniq ON auth_user (LOWER(username));
CREATE UNIQUE INDEX accounts_user_email_lower_uniq    ON auth_user (LOWER(email))
    WHERE email <> '';
```

The serializer keeps its friendly field-level checks, and now also catches
`IntegrityError` so the request that *loses* a registration race receives the
same `400 {"username": …}` the first one did, instead of a 500.

## Rationale

1. **No migration complexity** - Custom user model must be set before first migration; we're past that point
2. **Django ecosystem compatibility** - Default User works with all built-in auth views, admin, and third-party packages
3. **SimpleJWT integration** - Works out of the box with default User
4. **No custom model needed for the constraint** - a raw functional index on `auth_user` gives database enforcement without owning the model, and is valid on both SQLite (development) and PostgreSQL (production)

## Consequences

- Username and email are unique case-insensitively at the database level; Django's own exact-case `username` unique constraint remains as well
- Blank emails are exempt, because superusers created from the command line have none
- A pre-2026-11 database is deduplicated by the migration before the index is created: the oldest account keeps its name, later collisions get `-<id>` / `+dup<id>` suffixes
- Application must always normalize before queries (using `iexact` or lowercase)
- Cannot add extra fields to User model; use `Profile` one-to-one for extensions (already implemented)