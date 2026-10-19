# Coding-Agent Prompt — Production Security and Reliability

## Read first
Read `docs/FEATURE_SPEC_PRODUCTION_SECURITY_RELIABILITY.md`, `docs/BUILD_MASTER_PROMPT.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/BUILD_STATUS.md`, and the current milestone prompt. Inspect existing code, workflows, deployment config, tests, and repository status before proposing edits.

## Non-negotiable execution rules
- Do not skip milestones. Milestone 1 foundation verification remains a prerequisite; do not describe this feature as complete before relevant later milestones are implemented and verified.
- Work only on the currently authorized milestone. If asked for docs only, change Markdown only and do not modify application source code.
- Preserve useful code and avoid broad rewrites. Use least privilege and secure defaults.
- Never log, commit, echo, or request credentials in chat. Use placeholders in examples and environment/deployment secrets for real values.
- Never mark a control or test as passed without actual evidence from the repository/runtime/target deployment.

## Task checklist when implementation is authorized
1. Map each specification requirement to existing code, tests, workflows, and deployment config. Label it implemented, partial, missing, or unverified with evidence.
2. Apply role-based permissions and ownership checks at every endpoint/query/object/action; deny by default and add cross-user/cross-sub-admin regression tests.
3. Add minimal, redacted audit events for sensitive staff/security actions; explicitly test secret redaction and access restrictions.
4. Configure endpoint-specific throttles and bounded request sizes, pagination, search, attempts and exports. Test boundary and concurrent behavior.
5. Document backup scope/retention/RPO/RTO and a repeatable restore drill. Do not claim automated backups until an actual scheduler and destination are configured and a restore is verified.
6. Configure least-privilege CI permissions, repeatable Django/backend/frontend checks, test gates, workflow timeouts and secret-safe diagnostics.
7. Add safe structured logs, correlation IDs, health/readiness behavior and monitoring hooks. External vendors require approval; test real target-environment behavior before claiming alerts work.
8. Harden production configuration, HTTPS, trusted hosts/origins, cookies/security headers and migrations/deployment/rollback steps without breaking local development.
9. Audit service-worker caching by resource class; ensure private API responses, tokens, notes/progress/planner data, active tests, answer keys and protected media are not stored in shared caches.
10. Review paid-resource delivery honestly: public external URLs are public; implement access control only through a supported authorized delivery path, never DRM/paywall bypass.
11. Bound and authorize exports; protect CSV against spreadsheet formula injection; document data retention/deletion.
12. Add mobile accessibility, performance, and error-state tests for changed paths.

## Testing and evidence
- Run the exact relevant commands and capture exit codes/output without exposing secrets.
- Include regression tests for role/ownership boundaries, rate limiting, log redaction, backup restoration procedure, cache privacy, protected media, export safety, and production settings.
- Distinguish automated test evidence from manual browser/deployment checks.
- If a check cannot run due to missing runtime, credentials, hosting, or device, report the blocker and provide the exact next action instead of guessing.
- Update `docs/BUILD_STATUS.md` and `docs/IMPLEMENTATION_PLAN.md` only with observed evidence.

## Required final report
List changed files, requirements addressed, tests/checks run with exact outcomes, deployment/browser checks still pending, unresolved risks, and the next authorized milestone. Stop after the milestone; do not claim production readiness without target-environment evidence.
