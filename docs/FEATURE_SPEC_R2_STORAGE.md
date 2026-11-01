# Feature Specification — Sub-admin Multi-account Cloudflare R2 Storage

**Status:** Step 1 shipped (2026-11-02): the account/bucket model, encrypted
credentials, the admin panel and the connection test. Upload plumbing (sections
3–5) is **not** built yet — the panel configures storage, it does not yet move
a file into it.  
**Priority:** Mandatory prerequisite for Community post images and course thumbnails.  
**Applies to:** Django backend, sub-admin panel, object-storage adapter, Community posts, course administration, media delivery, audit/security controls.

## 1. Goal

Allow every sub-admin to connect and manage multiple Cloudflare R2 buckets across different Cloudflare accounts entirely from their own sub-admin panel. The same storage manager must support Community post image uploads and course thumbnail uploads. Storage targets are tenant-owned; one sub-admin must never gain access to another sub-admin's credentials, target configuration, or media.

### 1a. What exists today (verified)

| Piece | Where | Evidence |
|---|---|---|
| `R2Account` — one Cloudflare login: name, 32-hex account id, owner, on/off | `objectstore/models.py` | `objectstore/tests/test_storage.py::AccountModelTests` |
| `R2Bucket` — name, public base URL, enabled, per-purpose allow flags, one default per purpose per owner | `objectstore/models.py` | `BucketRulesTests` |
| Credentials encrypted at rest (Fernet; keys from `R2_CREDENTIAL_KEYS`, or HKDF-SHA256 over `SECRET_KEY` when unset) | `objectstore/crypto.py` | `CryptoLockTests` |
| SigV4 signing, presigned URLs, read/write calls — stdlib only, no SDK | `objectstore/r2.py` | `SigningTests` (fixed clock) |
| "Test connection": read-only ListObjectsV2, bounded at 8 s, result stored on the bucket *and* the account, audited | `objectstore/services.py` | `ConnectionTestTests` against a local HTTP server |
| Admin panel with buckets inline on the account page; sub-admins see only their own; secrets never rendered | `objectstore/admin.py` | `AdminPanelTests` |
| `manage.py r2_check [--bucket X] [--write]`, `manage.py r2_rotate_key [--new-key|--apply]` | `objectstore/management/commands/` | `CommandTests` |
| `objectstore.W001` warns a production deploy whose tokens rely on `SECRET_KEY` | `objectstore/checks.py` | `StartupCheckTests` |

Not built yet, and therefore not claimed: upload endpoints and validation
(section 4), routing/defaults beyond `resolve_bucket()`, Community and course
thumbnail integration, cleanup/retry, migration between targets, and the
end-to-end tests that go with them.

Credentials live in the database, not a secret manager, because a sub-admin has
to be able to paste their own token without a deploy. That is only acceptable
because they are encrypted with application key material and never returned by
any UI.

## 2. Target and ownership model

- Each storage target belongs to exactly one sub-admin/tenant and has a stable internal ID, display name, Cloudflare account ID, bucket name, S3-compatible endpoint/region configuration, enabled state, connection/health status, allowed purposes, optional per-purpose default, and timestamps.
- One sub-admin can configure multiple targets in one or more Cloudflare accounts. Do not assume all targets share an account ID, endpoint, credential, quota or billing account.
- Credential material must be handled separately from normal target metadata. Prefer a deployment secret manager; otherwise encrypt credentials at rest using managed key material, restrict decryption to the backend, and document key rotation/revocation. APIs return only whether a credential is configured and safe metadata, never the secret.
- The sub-admin panel can add, test, rename/update, replace/rotate credentials, enable/disable, choose defaults, inspect status and disconnect their own targets. The connection test must be bounded and non-destructive.
- Main-admin oversight is limited to an explicit permission and audit trail. It must not make stored secrets readable to the main-admin UI by default.

## 3. Media workflows

### Community post images
- Authorized sub-admins can upload images during post create/edit, select one of their enabled targets allowed for Community media, and see persisted previews after reload.
- Verify post ownership/course assignment and target ownership on the server for every upload, attach, replace, read and delete action.
- Students receive access only to images on posts visible to them. Private buckets and short-lived signed URLs or an approved protected delivery endpoint are the default.

### Course thumbnails
- Authorized sub-admins can upload or replace a thumbnail for a course they own/are assigned to and select a permitted target or configured default.
- Verify course ownership and target ownership server-side. Thumbnail metadata must be returned only with authorized course responses.
- Reuse the same storage adapter, credential system, validation, audit and cleanup behavior as Community media.

## 4. Upload and database rules

- Store media metadata only in the database: target ID, object key, safe display filename, detected MIME type, byte size, optional dimensions, owner, related course/post, upload state and timestamps. Never store the file bytes in a database field.
- Use random/collision-resistant object keys generated by the server. Never use user filenames as paths; reject traversal, control characters and malformed object keys.
- Validate actual content type and image decoding, not only the filename or browser-supplied MIME. Set configurable byte and pixel limits; reject SVG and active formats by default unless a reviewed sanitizer is explicitly adopted.
- Use bounded streaming uploads and request limits. Do not load unbounded files into memory.
- Keep buckets private by default. Signed URLs must be short-lived, scoped to the exact object and issued only after authorization. Never expose R2 credentials to the browser or embed them in public URLs.
- Use durable ordering or an outbox/retry process so failed uploads, database writes, replacements and object deletion do not create silent data loss. Do not report success until both object storage and database metadata reach the documented successful state.
- If one object is referenced by multiple records, do not delete it until all references are safely removed.

## 5. Routing, defaults, quotas and disconnect

- Allow a default target by purpose (Community images, course thumbnails) and explicit target selection per upload. Automatic routing by quota/health is optional and must be configured deliberately.
- Do not promise that quotas are pooled across accounts. Track known provider quota/rate-limit errors without claiming exact free capacity unless the provider API supplies a reliable value.
- Cross-target failover is opt-in. Retry only when safe, avoid duplicate objects, record the final target, and preserve the requested privacy/access policy.
- Disabling or disconnecting a target blocks new uploads but must not silently delete existing media. Show remaining object references and require a documented keep, migrate, or explicitly confirm-break decision before removing access credentials.
- Provide a migration/repoint workflow if media must move between targets; verify object existence and metadata before switching database references.

## 6. Security and operations

- Enforce tenant ownership at query and object-permission levels for target CRUD, connection tests, defaults, upload, replace, read, delete and migration endpoints.
- Never log access keys, secret keys, signed URLs, authorization headers, request signatures or raw provider exceptions. Redact audit metadata.
- Validate endpoint configuration and use the supported R2 endpoint form; prevent arbitrary endpoint configuration from becoming an SSRF path. Restrict connection tests to supported Cloudflare R2 endpoints and expected operations.
- Apply throttling to connection tests and uploads. Audit target creation/change/test result, credential rotation, enable/disable/disconnect, default changes, uploads, replacements, deletions and privileged cross-tenant actions.
- Private media and authenticated management APIs must not enter shared service-worker Cache Storage. Review CDN/cache headers and signed URL expiry behavior.
- Document backup/restore and credential-rotation implications. Database backup alone does not back up R2 objects.

## 7. Required acceptance tests

- A sub-admin can connect two or more buckets across different Cloudflare accounts and select them separately.
- A sub-admin can upload a Community post image and course thumbnail to selected targets; metadata and previews persist after reload.
- Another sub-admin cannot list, test, alter, select, migrate or delete those targets/media, including by tampering with IDs.
- Main-admin capabilities match explicit permissions and do not reveal secret values.
- Invalid credentials, inaccessible buckets, expired credentials, rate limits, quota errors and provider outages yield sanitized recoverable errors.
- Reject oversized, malformed, mismatched MIME, invalid image, active-content and path-traversal uploads.
- Verify signed URLs expire and unauthorized users cannot obtain protected images.
- Verify replacement and deletion cleanup, retry after partial failure, no deletion of still-referenced objects, and safe disconnect with existing references.
- Verify audit redaction and that private API/media are not cached in shared service-worker storage.
- Run migration, backend permission/integration, frontend interaction and end-to-end mobile tests. Record exact commands and outcomes.

## 8. Definition of done

This feature is complete only when the credential protection, tenant-owned target model, APIs, storage adapter, sub-admin UI, Community/course integrations, cleanup/retry workflow, and required tests are implemented and verified. Markdown alone is not implementation evidence.
