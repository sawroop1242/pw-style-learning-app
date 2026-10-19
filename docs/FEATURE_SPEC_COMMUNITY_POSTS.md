# Feature Specification — Community Posts

**Status:** Planned; implementation and tests have not been verified.  
**Applies to:** Frontend, Django REST API, role permissions, audit logging, and PWA cache policy.

## 1. Goal

Add a **Community** section to StudySpace where students can read announcements/posts published by administrators. Main admins and authorized sub-admins can create posts. The feature must use the existing account, role, course ownership, API, and UI architecture rather than creating a separate login or permission system.

## 2. Roles and visibility

- **Main admin:** create platform-wide posts; edit, publish/unpublish, pin, and delete any community post; moderate sub-admin posts; view the full post-management list.
- **Sub-admin:** create posts only within the platform-wide or course scope explicitly assigned to them. Default policy: sub-admin posts are scoped to courses they own/are assigned to; they cannot publish a platform-wide announcement or edit/delete another author's post unless explicitly granted a moderation permission.
- **Student:** read published posts that apply to the student's platform/course access. Students cannot create, edit, pin, publish, or delete posts.
- Enforce every rule on the server at list, detail, create, update, publish, pin, and delete endpoints. Hiding a button is not authorization.
- A post linked to a course must not reveal unpublished course details or content to a student who cannot access that course. Global announcements may be visible to all authenticated students; whether to show public posts to logged-out visitors must be an explicit product decision, default **authenticated users only**.

## 3. Post data and lifecycle

Each post should support, as justified by the existing data model:
- title (required, bounded length);
- body/content (required, bounded length; render as plain text or safely sanitized Markdown, never raw untrusted HTML);
- author and created/updated timestamps assigned by the server;
- visibility/scope: platform-wide or one authorized course;
- publication status: draft or published;
- optional pinned flag controlled by authorized staff;
- optional attachment/link only if the existing resource/security policy supports it. Validate protocol, size/type and access policy; do not allow arbitrary unsafe uploads.
- optional scheduled publication is out of scope for v1 unless explicitly approved later.

Use database constraints and indexes where useful. Preserve author attribution. A post's author, timestamps, and scope permissions must not be trusted from client-supplied values.

## 4. Student community feed

- Add a Community entry in the authenticated learner navigation.
- Show published, in-scope posts newest first; pinned posts appear before ordinary posts, with stable ordering.
- Include title, author display name/role as allowed, publication date, body, and linked course context when applicable.
- Provide pagination and a clear empty state, loading state, error/retry state, and offline state.
- A post detail view may be a separate route or expandable detail depending on existing frontend architecture.
- Do not display drafts, deleted posts, scheduled/unpublished posts, or posts outside the current student's visibility scope.
- Do not add comments, likes/reactions, direct messages, or real-time chat in v1. These are separate future features.

## 5. Admin and sub-admin authoring UI

- Add a staff-only post management view with a list, create/edit form, draft/publish action, and permitted delete action.
- Main admin can select platform-wide scope or a course scope; sub-admin can select only a course they own/are assigned to.
- Provide confirmation before destructive deletion and clear validation/save errors.
- Main admin can pin/unpin and moderate posts across scopes. Sub-admin pinning is limited to their authorized course posts unless a narrower policy is selected.
- The backend must re-check role, ownership, publication state and scope on every mutation.
- All visible actions must work against real API endpoints; do not use local-only fake success.

## 6. API contract requirements

Exact paths must be reconciled with the current URL conventions before implementation. Define and document equivalent capabilities for:
- list posts visible to the current user, with pagination and optional course filter;
- retrieve a single visible post;
- create a draft or published post, restricted to staff roles;
- update an authorized post;
- publish/unpublish;
- pin/unpin with role and scope checks;
- delete with role and ownership checks.

Use stable response schemas and validation errors. The server assigns author and timestamps. Use a consistent permission-denied/not-found strategy that does not leak the existence of hidden posts. Querysets must filter by publication and visibility before returning results.

## 7. Security, privacy, and reliability

- Escape plain text or sanitize supported Markdown with a maintained, restrictive allowlist; do not render raw HTML.
- Validate title/body length and request size; throttle create/update/publish endpoints to prevent spam.
- Validate any link/attachment type, URL scheme and allowed access path. Do not expose protected paid course material via a public attachment URL.
- Record security-relevant post creation, publication, scope changes, pinning, moderation and deletion in the existing redacted audit system where available.
- Avoid logging full post bodies or private learner information unnecessarily.
- Do not cache authenticated community API responses or private/staff post-management data in shared service-worker Cache Storage. Offline mode may show a generic unavailable state; it must not imply new posts were saved or synced.
- Ensure pagination and query indexes avoid loading the entire post table for each feed request.
- Keep CSRF/authentication behavior consistent with the chosen API auth model.

## 8. Testing and acceptance criteria

### Backend tests
- Student can list/retrieve only published posts in their visibility scope.
- Anonymous users cannot read community content by default.
- Student cannot create/update/publish/pin/delete posts.
- Sub-admin can create/edit/delete only permitted posts and cannot create a global post or modify another sub-admin's post.
- Main admin can manage all posts and scopes.
- Direct-object-ID attempts, course-scope changes, author spoofing, hidden/unpublished posts and deleted posts are protected.
- Input validation, pagination, throttling, safe rendering metadata, audit redaction and attachment/link validation are covered.
- Queries do not reveal posts for inaccessible/unpublished courses.

### Frontend tests
- Community navigation and feed render loading, empty, error, offline, and populated states.
- Student UI is read-only; staff authoring controls appear only for server-confirmed roles.
- Form validation, draft/publish, edit, pin and delete states match API responses.
- Mobile layout, keyboard navigation, accessible labels and visible focus are verified.

### Definition of done
The Community feature is complete only after database migrations, API, permission tests, frontend integration, security/cache review, and a real end-to-end smoke test pass. A specification or prompt alone does not mean the feature has been implemented.
## 9. Mandatory sub-admin-owned Cloudflare R2 storage and image uploads

This is required scope for the Community feature, not an optional enhancement. Each sub-admin must be able to connect and manage multiple Cloudflare R2 storage targets across separate Cloudflare accounts from the sub-admin panel. This capability is also used for course thumbnails.

### Sub-admin storage panel
- Provide a Storage / R2 Connections screen inside the authenticated sub-admin panel. A sub-admin can add, test, enable/disable, set a default, rename, and remove their own storage target, and see a safe status summary.
- Each target represents one bucket and contains a stable internal target ID, display name, Cloudflare account ID, bucket name, S3-compatible endpoint/region configuration, access key ID, secret access key reference, status, intended media purposes, and timestamps. Support multiple targets across multiple Cloudflare accounts for the same sub-admin.
- Show secret credentials only during initial entry where feasible; never return the stored secret to the browser after save. Use a managed secret store or encrypted server-side secret storage with key management and rotation procedures. Never put credentials in frontend bundles, local storage, URLs, logs, error messages, Git, or ordinary database plaintext.
- Test connectivity with a bounded, non-destructive operation and report sanitized success/failure. Do not expose provider error details that contain credentials or internal configuration.
- The main admin may have platform-level oversight and revoke compromised targets, but must not casually expose a sub-admin's secret credentials. Cross-tenant access requires an explicit audited permission.

### Community post images and course thumbnails
- Staff authoring UI must support uploading one or more permitted images to a Community post and uploading/replacing a course thumbnail. A sub-admin chooses one of their own enabled R2 targets or uses a configured default for the relevant purpose.
- The server verifies that the actor owns/has assignment authority over the post/course and the selected storage target belongs to that same sub-admin. Never trust a target ID merely because the frontend submitted it.
- Store only media metadata in the application database: target ID, object key, original display filename if safe, detected MIME type, byte size, dimensions where needed, owner, related post/course, created timestamp, and upload status. Store no file bytes in the database.
- Validate extension and detected content type, enforce configurable byte/pixel limits, reject SVG and active content by default unless a hardened sanitization policy is explicitly approved, generate collision-resistant object keys, normalize filenames, and prevent path traversal.
- Use private buckets by default. Deliver images through short-lived signed URLs or an approved controlled media endpoint; do not expose access keys or rely on guessed object URLs. Ensure students only see images attached to posts/courses they are allowed to view.
- On replacement or deletion, remove the old object only after the database change succeeds, or use a durable cleanup job/outbox so failures can be retried. Do not leave the database pointing to a missing object or delete an object still referenced elsewhere.
- Disable/remove a target safely: block new uploads, show any remaining references, and require a clear policy for existing media (keep accessible, migrate, or explicitly confirm that content will break). Do not silently delete stored files when disconnecting credentials.
- R2 account quotas and billing remain separate per Cloudflare account. Do not promise automatic capacity pooling or cross-account replication. Cross-target retry/failover must be explicitly configured, avoid duplicate objects, and never silently switch a file to a target with incompatible access policy.

### Security and acceptance tests
- Sub-admin A cannot list, test, edit, disable, select, or remove sub-admin B's targets or media; tampered target IDs are rejected server-side.
- Verify connection tests, secret redaction, key rotation/revocation, permission checks, upload size/type limits, invalid image rejection, object-key safety, signed URL expiry, post/course visibility, replacement/deletion cleanup and failure recovery.
- Verify Community images and course thumbnails upload to the selected account/bucket and survive reloads using persisted metadata.
- Verify private Community APIs/media are not cached in shared service-worker storage.
- Add accessible mobile UI states for empty, configured, testing, connected, invalid credentials, permission denied, quota/limit error, upload progress, retry, and disconnected targets.
- Definition of done includes backend models/migrations, protected credential handling, storage adapter, API, UI, permission/security tests and an end-to-end test. Documentation alone is not implementation evidence.
