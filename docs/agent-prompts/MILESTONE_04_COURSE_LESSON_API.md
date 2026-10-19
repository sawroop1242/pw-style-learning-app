# Coding-Agent Prompt — Milestone 4: Course and Lesson API

## Objective
Build a predictable, documented course catalogue and lesson API for public published content and authenticated learner actions.

## Inspect first
Read models, serializers, viewsets, router registration, current response formats, and frontend expectations. Preserve compatible endpoints where reasonable; document any breaking change and update consumers.

## Required API behavior
- Paginated course listing and course detail.
- Search by supported text fields and filters by subject/category and other fields that actually exist.
- Stable ordering with allowlisted ordering fields and bounded page sizes.
- Published courses and lessons visible to students; drafts hidden from anonymous and ordinary authenticated users. Staff can preview/manage drafts through explicit permission paths.
- Lesson list/detail scoped to the relevant course and publication rules; avoid leaking a draft through nested endpoints.
- Lesson completion endpoint that requires authentication and writes progress for the current user only.
- Validate video URLs using an explicit allowlist of schemes and safe embed/provider rules. Reject javascript/data URLs and arbitrary unsafe iframe HTML. Support ordinary external links when authorized; do not bypass login, paywalls, DRM, or provider restrictions.
- Consistent not-found behavior for hidden/unpublished content where that avoids disclosure.
- Predictable validation errors and API pagination metadata.

## Required course content and code-access API behavior

Follow `docs/FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md` and reuse existing API patterns. Support course cover image URL, free/paid mode and pricing validation, provider Telegram contact, subject folders, ordered titled video lessons with safe embed URLs, and titled chapter PDF download resources. Public catalog endpoints expose published courses only and must not leak drafts or staff-only metadata.

Add authorized staff APIs for course/folder/resource CRUD and course-bound code generation/revocation. Sub-admin actions must be restricted to owned courses. Add student code redemption for a selected paid course; atomically redeem one-use-by-default codes, create a durable grant, rate-limit guessing, and return safe generic failures. Students must not read raw code data, hashes, or audit records. Free courses require no code; no payment endpoint or checkout path should be added. Every paid lesson/PDF delivery request must check the user's grant. Use an authenticated download endpoint or short-lived signed URL for private PDFs; do not claim a permanent public URL is protected.

Validate Telegram usernames/links and media URL schemes/allowed providers. Never accept arbitrary iframe HTML or perform unsafe server-side fetches of supplied URLs.

## Tests
Cover list/detail, anonymous behavior, publication filtering, search/filter/order, pagination, invalid parameters, URL validation, course/lesson relationships, lesson completion ownership, staff access, and draft leakage. Check query counts or use appropriate ORM loading to prevent obvious N+1 patterns.

## Acceptance
API schema or endpoint documentation matches actual responses; tests pass; frontend-relevant response examples are included. Update build status and stop before Milestone 5.
