# Coding-Agent Prompt — Milestone 6: Notes and Progress Synchronization

## Objective
Make notes and learning progress durable, authenticated, user-specific, and resilient to network failures.

## Notes requirements
- List, create, read, update, and delete notes for the authenticated user.
- Support optional course/lesson association only when valid and visible to that user.
- Validate lengths, required fields, IDs, and content types; paginate large lists.
- Set ownership from the request user on the server. Never accept a submitted owner as authoritative.
- Define stable update semantics and conflict behavior; use timestamps or version fields only if the implementation needs conflict detection.
- Return clear validation and authorization errors.

## Progress requirements
- Persist per-user lesson progress with a clear uniqueness rule, e.g. one progress row per user/lesson.
- Define completion and incomplete/reopen behavior, timestamps, and idempotent updates.
- Compute dashboard totals from authorized server data; avoid trusting browser counters.
- Ensure progress is associated with an existing lesson and current user.
- Prevent duplicate rows and race-related inconsistent state where practical.

## Frontend contract
Document expected success/error response shapes for the frontend API client. Failed network writes must not display a false “saved/synced” state. If an offline queue is not yet implemented, show pending/error state rather than pretending sync succeeded.

## Tests
Cover CRUD, invalid payloads, pagination, ownership, cross-user access, duplicate progress updates, repeat completion, reopening if supported, invalid lesson association, and database persistence across client sessions.

## Acceptance
Backend suite and migration checks pass; all ownership tests pass. Update status and stop before Milestone 7.
