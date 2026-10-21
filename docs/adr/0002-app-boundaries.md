# ADR 0002: App Boundaries

**Date:** 2026-10-20  
**Status:** Accepted

## Context

The project has three main Django apps currently:
- `accounts` - User management, authentication, profiles, OTP, audit events
- `courses` - Course catalog, lessons, quizzes, access codes, personal data (notes, progress, bookmarks, revision, study tasks), community posts
- `config` - Project settings, URLs, health check

## Decision

Maintain current app boundaries with one addition:
- Keep `accounts` and `courses` as separate apps
- Add `analytics` app in Milestone 5 for student and staff analytics
- Do NOT split `courses` into smaller apps (catalog, access, test_engine, personal, community)

## Rationale

1. **Cohesive domain** - All `courses` models are tightly related (courses → folders → lessons/quizzes → questions/choices → attempts/answers)
2. **Shared ownership logic** - Sub-admin ownership scoping applies across all course-related models
3. **Avoid premature modularization** - Splitting would create circular imports and shared base classes
4. **Analytics separation** - Analytics is a distinct cross-cutting concern with different access patterns (aggregations, time-series)

## Consequences

- `courses` app will continue to grow; monitor for when split becomes necessary
- `analytics` app will import from `courses` but not vice versa
- All admin ownership logic stays in `courses/admin.py`