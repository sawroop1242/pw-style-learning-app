# Coding-Agent Prompt — Sub-admin Multi-account Cloudflare R2 Storage

**Read first:** docs/BUILD_MASTER_PROMPT.md, docs/IMPLEMENTATION_PLAN.md, docs/FRONTEND_IMPLEMENTATION_PLAN.md, docs/BACKEND_IMPLEMENTATION_PLAN.md, docs/FEATURE_SPEC_R2_STORAGE.md, docs/FEATURE_SPEC_COMMUNITY_POSTS.md, docs/FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md, and docs/BUILD_STATUS.md if present.

## Objective

Implement the required sub-admin-owned multi-account Cloudflare R2 storage manager. Each sub-admin must be able to connect multiple R2 buckets across different Cloudflare accounts from the sub-admin panel. The feature is mandatory for Community post image uploads and course thumbnail uploads.

## Scope

1. Inspect the existing code and milestone status first. Do not skip foundation, authentication, role, or course-ownership prerequisites.
2. Implement tenant-owned storage-target records and a storage adapter for multiple account IDs, buckets and credential sets.
3. Add protected credential handling: secret manager where available, otherwise encrypted-at-rest credentials with restricted backend decryption and rotation/revocation. Never return secret values or log them.
4. Add sub-admin panel screens and APIs for adding/editing targets, testing connectivity, replacing credentials, enabling/disabling, choosing per-purpose defaults, viewing sanitized health/status, and disconnecting safely.
5. Integrate the shared storage adapter into Community post image upload and course thumbnail create/replace/delete workflows.
6. Validate actual image content, MIME, size and dimensions; use generated object keys; keep buckets private; use authorized short-lived signed URLs or a protected delivery endpoint.
7. Store media metadata and target/object references in the database, never file bytes. Implement safe cleanup/retry and disconnect/migration behavior.
8. Add tenant-isolation, security, integration, UI and end-to-end tests; update API documentation, docs/BUILD_STATUS.md and implementation plans with real evidence.

## Non-negotiable authorization and safety

- Every target belongs to one sub-admin. All CRUD, connection tests, defaults, uploads, reads, replacements, deletions and migration operations enforce owner/course/post authorization on the server.
- No sub-admin may access another sub-admin's credentials, targets or media by changing IDs. Main-admin oversight must be explicitly permissioned and audited, without exposing secrets by default.
- Do not commit credentials, put them in frontend code or browser storage, or emit secrets/signed URLs in logs.
- Use private buckets by default. Do not cache authenticated APIs or private media in shared service-worker caches.
- Never silently delete objects when disconnecting a target. Handle partial failures and prevent deletion of objects still referenced elsewhere.
- Do not promise pooled quotas or automatic failover. Any routing/failover must be explicit, privacy-preserving and safe against duplicate uploads.

## Required tests

- Two or more separate Cloudflare accounts/buckets can be connected for one sub-admin and selected for different uploads.
- Community post images and course thumbnails upload, persist and render after reload.
- Cross-sub-admin target/media access is denied for list/detail/mutation/upload/signed URL/migration endpoints.
- Secrets and provider errors are redacted; credential replacement/revocation works.
- Invalid/oversized images, MIME mismatch, active formats, path traversal and unsafe endpoint settings are rejected.
- Signed URL expiry, quota/outage errors, partial upload/database failure, replacement cleanup, disconnect with referenced objects, audit logs and service-worker cache privacy are tested.
- Run actual migration, backend/frontend checks and end-to-end smoke tests; report exact results without inventing success.

## Execution contract

Follow the shared milestone order and implement only the next eligible milestone. If prerequisite auth/ownership foundations are incomplete, stop at the blocker rather than building an insecure bypass. Documentation-only edits do not satisfy this implementation prompt.
