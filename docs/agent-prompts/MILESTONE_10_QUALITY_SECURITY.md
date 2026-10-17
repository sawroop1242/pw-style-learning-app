# Coding-Agent Prompt — Milestone 10: Quality, Security, Accessibility, and Performance

## Objective
Establish repeatable release-quality checks and close critical security, accessibility, reliability, and performance gaps across the full application.

## Required review areas
- Backend: permissions/ownership, input validation, authentication throttling, secret configuration, CORS/CSRF/hosts/HTTPS, secure cookies, security headers, quiz answer secrecy, error handling, database constraints, query efficiency, and dependency hygiene.
- Frontend: safe DOM rendering, token/session handling, API error behavior, no false success states, keyboard navigation, labels, focus, contrast, reduced-motion behavior where applicable, and 320 px layout.
- PWA: cache privacy, cache versioning, offline behavior, logout/user-switch handling.
- Operations: health checks, logs without secrets/PII, database migrations, configuration validation, backup assumptions, and recovery documentation.

## Automated checks
- Backend tests, migration consistency, Django system checks, Python compilation/lint/type checks where configured.
- Frontend syntax, lint, unit/integration tests, and build checks appropriate to the existing stack.
- CI workflow with pinned or intentionally bounded actions/tool versions, least-privilege permissions, concurrency behavior, dependency caching, and actionable logs.
- Dependency vulnerability checks that do not leak secrets and whose findings are reviewed rather than blindly auto-fixed.
- Accessibility audit and performance checks using available tooling; distinguish automated scores from manual verification.

## Engineering rules
- Fix root causes, not just suppress warnings.
- Do not add broad permissions, wildcard CORS, disabled TLS checks, hardcoded production secrets, or blanket cache rules to make checks green.
- Do not mark a check passed if the tool was unavailable. Record exact evidence and limitations.
- Avoid excessive CI complexity and unnecessary paid services.

## Acceptance
All required CI checks pass, or every remaining failure is reproducible, scoped, and explicitly documented with a mitigation plan. No unresolved critical/high security defect remains without owner-approved mitigation. Update status and stop before Milestone 11.
