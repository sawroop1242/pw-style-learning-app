# Production Security, Reliability, and Operations — Technical Specification

## Goal
Define the technical controls required before StudySpace is exposed to public users. This specification complements Milestones 1, 3, 10, and 11; it does not authorize skipping the existing sequence or claim controls are already implemented.

## 1. Role-based access control (RBAC)
- Define explicit roles and permissions for anonymous visitors, students, sub-admins, and main admins.
- Enforce authorization on every API endpoint, object lookup, list query, export, and state-changing operation. Hiding buttons in the UI is not security.
- Main admins may manage platform resources; sub-admins may access only courses/tests they own or are explicitly assigned; students may access their own private data and content they are entitled to view.
- Deny by default and validate allowed state transitions. Never accept a role, owner ID, price, access grant, or privileged flag directly from an untrusted client without server-side authorization.
- Add regression tests for anonymous access, privilege escalation, cross-user access, cross-sub-admin access, object-ID guessing, and nested endpoints.

## 2. Audit logs
- Record security- and business-relevant staff actions such as role changes, course publication, access-code generation/revocation, sensitive exports, and account security events.
- Include event type, actor ID where appropriate, target type/ID, timestamp, outcome, and a minimal safe metadata set.
- Never log passwords, OTP values, bearer tokens, SMTP credentials, full access codes, private note contents, or unnecessary personal data. Sanitize untrusted values to prevent log injection.
- Restrict audit-log access; define retention and deletion policy; make logs append-only at the application permission level where practical.
- Test that sensitive actions create appropriate events and secrets never appear in captured logs.

## 3. API abuse prevention and rate limits
- Apply endpoint-specific throttling to login, registration, OTP send/verify, password reset, code redemption, search, quiz submission, and exports.
- Combine per-account and per-IP controls where appropriate, while avoiding permanent lockout and considering shared networks. Return safe retry guidance without disclosing whether an account exists.
- Limit request body size, pagination size, search length, concurrent active attempts, export rows, and expensive filter ranges.
- Add abuse monitoring and configurable limits; do not treat frontend validation or CORS as security controls.
- Test throttle boundaries, concurrent requests, enumeration resistance, and safe error responses.

## 4. Automated backups and restore drills
- Document the database and media/resource metadata included in backups, schedule, retention, encryption, storage access, and responsible operator.
- Keep backups outside the primary database failure domain; do not commit backups or credentials to Git.
- Define recovery point objective (RPO) and recovery time objective (RTO) appropriate to the project's scale, even if initial targets are modest.
- Provide a repeatable restore procedure and periodically verify restoration into an isolated environment. A backup is not considered valid until restoration is tested.
- Do not promise backup automation until a scheduler/storage provider is actually configured and tested. Record last successful backup and last restore verification operationally without exposing sensitive details.

## 5. CI, regression tests, and release gates
- Run reproducible checks on pull requests: Python dependency/setup checks, Django system checks, migration consistency, backend tests, Python compile checks, JavaScript syntax checks, and any configured frontend/browser tests.
- Pin or constrain dependencies appropriately and review security updates; do not blindly auto-upgrade production dependencies.
- Make required checks visible and block releases on critical failures. Use least-privilege CI tokens, minimal workflow permissions, timeouts, and concurrency controls.
- Keep secrets in repository/environment secret stores; mask sensitive values and never print environment dumps.
- Include tests for authorization, authentication/OTP, course publication/access codes, CSV URL SSRF controls, test scoring/result release, private data ownership, PWA cache privacy, and export injection.
- Document commands and actual outcomes. Never fabricate green checks or suppress failures merely to pass CI.

## 6. Monitoring, structured logs, and error reporting
- Provide health/liveness and, where justified, readiness checks that do not disclose secrets, environment variables, database credentials, or internal stack traces.
- Emit structured application logs with request/correlation IDs, severity, event type, duration, and safe status metadata. Redact credentials and personal data.
- Track availability, error rates, latency, failed jobs/email sends, database connectivity, and resource pressure at a scale appropriate to the deployment.
- Return generic user-facing server errors and keep diagnostic traces server-side with restricted access.
- Define an incident triage process and alert thresholds. External monitoring/error vendors require explicit approval and configuration.
- Verify health endpoints, failure behavior, log redaction, and monitoring alerts in the target environment before claiming operational readiness.

## 7. Secure deployment and configuration
- Use HTTPS in deployed environments; configure trusted hosts, CORS/CSRF settings, secure cookies where applicable, HSTS only when HTTPS deployment is verified, and appropriate content/security headers.
- Use environment-managed Django secret key, database credentials, email credentials, allowed hosts, trusted frontend origins, and debug setting. Production must fail safely when required configuration is absent.
- Use least-privilege database and hosting credentials; separate development/staging/production secrets; rotate exposed credentials.
- Apply migrations as a controlled release step, collect static assets reproducibly, expose only intended ports, and document rollback.
- Keep dependency and runtime versions supported; do not assume a deployment is secure because it builds successfully.

## 8. Private data and service-worker cache privacy
- Classify resources as public static assets, public published catalogue metadata, authenticated API responses, private notes/progress/planner data, test payloads/results, and protected paid media.
- Cache only approved versioned static assets and carefully selected public metadata. Never put tokens, OTPs, private APIs, private notes/progress/planner data, active tests, answer keys, or protected media into shared Cache Storage.
- Define logout/account-switch cleanup, cache versioning/eviction, service-worker updates, offline behavior, and stale-access handling.
- Use server authorization as the authority; a stale cached UI or lock flag must never grant access.
- Inspect actual Cache Storage in browser tests and verify private responses are not cached. Test logout and account switching on a shared device.

## 9. Secure paid media and resource delivery
- Public external PDF/video URLs cannot be made private by hiding them in the UI. Explain this limitation to content owners.
- Where access control is required, deliver files through an authenticated, authorization-checked path or a provider-supported private/signed URL mechanism with short expiry and appropriate cache headers.
- Do not proxy arbitrary user-supplied URLs. Validate allowed media hosts and mitigate SSRF, redirect abuse, DNS/IP changes, and oversized responses.
- Do not bypass DRM, paywalls, provider authentication, or hosting terms. External video embeds may remain independently accessible according to provider behavior.
- Test revoked course grants, expired signed URLs, direct URL access, and cache behavior.

## 10. Privacy-safe exports and data lifecycle
- Restrict CSV/report exports by role and ownership; bound row count and date range; audit sensitive exports.
- Escape spreadsheet-formula prefixes in user-controlled CSV fields. Do not expose tokens, answer keys, private notes, or unnecessary direct identifiers.
- Document account deletion/deactivation, data retention, orphaned resources, backups, and audit-log retention.
- Keep personal information minimal and explain what the platform stores. Avoid adding third-party tracking by default.

## 11. Accessibility, performance, and quality
- Test narrow mobile viewport layouts, touch target usability, keyboard navigation, visible focus, labels, semantic structure, and contrast.
- Monitor API query count and response size; paginate lists, avoid N+1 queries, add indexes based on observed query patterns, and bound expensive filters.
- Compress/resize thumbnails, lazy-load nonessential imagery, respect reduced motion, and offer low-data behavior.
- Ensure loading, empty, offline, validation, permission-denied, and server-error states are understandable and do not falsely report success.
- Run representative performance tests on critical API flows and document limits and measured results.

## Required acceptance evidence
For every control, report the exact implementation files, tests/commands, environment, and observed outcomes. Use a checklist:
- [ ] RBAC and ownership tests pass for each role and resource class.
- [ ] Audit logs redact secrets and enforce access/retention rules.
- [ ] Rate limits and request bounds are tested.
- [ ] A backup has been restored successfully in an isolated environment.
- [ ] CI required checks run and release gates are documented.
- [ ] Monitoring and safe health/error behavior are verified in the target environment.
- [ ] Production configuration fails safely and HTTPS/security headers are verified.
- [ ] Browser tests prove private data is absent from shared caches.
- [ ] Paid-media access controls and public-URL limitations are documented and tested.
- [ ] Exports are permission-scoped, bounded, and formula-safe.
- [ ] Accessibility, mobile layout, and representative performance checks are recorded.

## Definition of done
This document is a specification, not proof of implementation. Mark each control complete only after code review and repeatable test/deployment evidence. Integrate work with the existing milestone sequence, especially Milestone 1 foundation verification, Milestone 3 authorization, Milestone 10 quality/security, and Milestone 11 deployment.
