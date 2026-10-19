# Coding-Agent Prompt — Implement Community Posts

**Read first:** `docs/BUILD_MASTER_PROMPT.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/FRONTEND_IMPLEMENTATION_PLAN.md`, `docs/BACKEND_IMPLEMENTATION_PLAN.md`, `docs/FEATURE_SPEC_COMMUNITY_POSTS.md`, and `docs/BUILD_STATUS.md` if present.

## Objective

Implement the Community posts feature from `docs/FEATURE_SPEC_COMMUNITY_POSTS.md` in the existing StudySpace application. This is an implementation task, not a documentation-only task. Inspect the live code, current git status, models, routes, permissions, frontend navigation, service worker, tests and migrations before editing. Preserve the current stack and existing working features.

## Scope

1. Add a community post model or extend a suitable existing model only if that model is semantically appropriate. Include title, safely stored body, author, timestamps, visibility scope (global or authorized course), draft/published state, and pinning if justified by the existing architecture.
2. Add database migration(s), admin registration, serializers/validation, API routes/views, pagination and server-side permissions.
3. Implement a student-facing Community feed and post detail/read view using the existing frontend architecture and API client.
4. Implement create/edit/draft/publish/pin/delete controls for main admin and authorized sub-admins. Use real API calls and actual response/error states.
5. Integrate audit events, request throttling, safe text/Markdown rendering, and privacy-safe service-worker behavior according to the production security specification.
6. Update OpenAPI/API documentation, tests, `docs/BUILD_STATUS.md`, and relevant plans with evidence from the actual run.

## Authorization policy

- Main admin may create global announcements and manage all community posts.
- Sub-admin may create and manage only posts in courses they own/are assigned to; they may not create global announcements or edit another author's posts unless an existing explicit moderation permission authorizes it.
- Students may read published posts within their visibility scope only.
- Community is authenticated-only by default.
- Never rely on frontend role checks alone. Enforce list/queryset filtering and object-level permissions for every endpoint and mutation. Do not trust client-supplied author, timestamps, role, or scope IDs.
- Hidden posts must not leak through detail endpoints, pagination, error messages, search, or nested course serializers.

## Implementation rules

- Use one milestone per run. First confirm that prerequisite foundation/auth/ownership milestones are complete. If they are not, implement only the current next milestone or report the precise blocker; do not bypass the shared order to build Community prematurely.
- Use existing models and API conventions where appropriate; avoid duplicate role, course, or audit systems.
- Use plain text or strictly sanitized Markdown. Never inject raw post HTML.
- Validate body/title lengths, request sizes and any optional links/attachments. Do not add uploads unless the existing protected-media/storage design supports them safely.
- Add throttling and audit events for create/update/publish/unpublish/pin/delete, without logging full post bodies or secrets.
- Never cache authenticated Community API responses or private staff-management data in shared service-worker Cache Storage.
- Keep comments, likes, reactions, direct messages, and real-time chat out of scope.
- Do not claim tests passed unless they were actually run; do not claim deployment or production readiness without real evidence.

## Required tests

- Main-admin global/course post create/edit/publish/pin/delete.
- Sub-admin authorized course post CRUD and denial for global scope, other owners' posts, unauthorized course IDs and ownership changes.
- Student read-only access; drafts/unpublished/deleted/out-of-scope posts are inaccessible.
- Anonymous access denied; author/timestamp spoofing rejected or ignored safely.
- Pagination, validation, throttling, safe rendering, audit-log redaction, attachment/link validation and API errors.
- Frontend loading/empty/error/offline/populated states and role-appropriate controls.
- Community API payloads are not cached by the service worker.
- Mobile and keyboard/accessibility checks.

## Acceptance and report

Run the relevant backend and frontend tests, migration checks, lint/type checks if configured, and the core end-to-end smoke test. Record exact commands and actual outcomes. Update `docs/BUILD_STATUS.md` with files changed, evidence, failures/blockers and the next milestone. Stop after this scoped run and report what was genuinely completed. If prerequisite milestones are incomplete, stop and explain the dependency rather than falsely marking the feature done.
