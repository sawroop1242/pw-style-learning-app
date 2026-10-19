# Coding-Agent Prompt — Milestone 3: Authentication and Authorization

## Objective
Deliver a secure student account lifecycle and prove that private records cannot cross user boundaries.

## Inspect first
Review current JWT routes, serializers, permissions, throttling, settings, and all viewsets. Identify existing behavior and backward compatibility requirements. Keep Simple JWT unless there is evidence requiring a change.

## Required behavior
- Registration with normalized/validated identity fields and Django password validation.
- Login and access-token refresh with predictable error responses.
- Logout behavior documented honestly: if refresh-token blacklisting is selected, install/configure the required app and migrations; otherwise explicitly document the stateless JWT limitation and provide the chosen revocation strategy.
- Current-user profile read/update endpoints with a strict allowlist of editable fields.
- Appropriate anonymous/public permissions only for explicitly public endpoints.
- Every note, progress record, quiz attempt, and user profile operation must enforce ownership in queryset filtering and object-level authorization.
- Staff-only content management and moderation operations.
- Authentication throttling and sensible request validation. Avoid logging credentials, JWTs, passwords, or private payloads.
- Consistent 401/403 responses; do not rely on CORS to provide authorization.

## Required role hierarchy and object ownership

Implement and test three distinct permission levels: main admin, course-owning sub-admin, and student. Only the main admin can create/deactivate sub-admin accounts. Sub-admins can manage only their own courses, folders, lessons, PDF resources, access codes, and related grants within the explicitly allowed policy; they cannot create/promote staff or access another provider's records. Students cannot call any staff management or code-generation endpoints. Enforce ownership in querysets and object-level permissions on list, detail, create, update, delete, bulk generation, revoke, and publish actions. Do not rely on frontend visibility or a user-submitted owner ID.

Paid course access must be represented by a server-side grant, not a client flag. Include access-code redemption throttling and fail-closed permissions. Follow the complete matrix in `docs/FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md`.

## Security cases to test
- Anonymous user cannot read or mutate private data.
- User A cannot list, read, edit, or delete User B's notes, progress, attempts, or profile.
- Client cannot assign another owner by submitting an owner/user ID.
- Invalid, expired, malformed, or revoked tokens fail closed.
- Staff-only routes reject ordinary students.
- Registration rejects invalid or weak passwords and duplicate identifiers without leaking sensitive details.
- Throttling is tested without making the suite flaky.

## Implementation rules
Use dedicated serializers for public and private fields. Never serialize password hashes, refresh tokens, or internal authorization state. Apply ownership restrictions to list querysets as well as detail actions. Avoid broad exception handlers that turn authorization errors into success.

## Acceptance
All auth and permission tests pass, endpoint documentation is updated, and a concise threat/permission matrix is recorded in project docs. Run the full backend suite and migration checks. Update status with evidence and stop before Milestone 4.
