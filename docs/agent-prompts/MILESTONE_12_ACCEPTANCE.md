# Coding-Agent Prompt — Milestone 12: Final Product Acceptance

## Objective
Decide whether StudySpace meets the agreed release criteria using evidence from a clean setup and end-to-end learner/staff workflows. This milestone is an audit and remediation pass, not a reason to conceal unfinished features.

## Required procedure
- Read the master prompt, implementation plan, build status, README, known limitations, and deployment instructions.
- Use a clean checkout and documented environment; install dependencies and apply migrations from scratch.
- Run all backend/frontend tests, lint/static checks, migration checks, CI checks, and configured security checks.
- Test as anonymous visitor, ordinary student, a second student, and staff/admin. Never use real private student data in test fixtures.
- Verify registration/login/token lifecycle; published/unpublished content visibility; notes and progress ownership; quiz answer secrecy and server scoring; course/lesson navigation; error/empty/offline states; mobile responsiveness; PWA cache privacy; and admin content workflows.
- Confirm that no major feature relies on hidden local demo data or fake success states.
- Check documentation against the actual shipped behavior. Label features as implemented, partial, planned, or blocked.
- Verify deployment with real health checks and smoke tests if deployed; otherwise say “not deployed” or “deployment unverified.”
- Fix issues that fit this milestone and rerun impacted checks. If a large defect needs a separate milestone, report it rather than silently widening scope.

## Release gate
Do not recommend production release if there is an unresolved critical security issue, cross-user data exposure, quiz answer leakage, failed database migrations, untested core learning journeys, or a deployment with unknown persistence/HTTPS behavior.

## Required final report
Include:
- Commit/ref tested and clean-checkout environment.
- Features accepted and evidence for each.
- Exact test/check commands and pass/fail/blocked outcomes.
- Security and privacy findings and their resolution status.
- Deployment URL and observed smoke-test evidence, or explicitly state no verified deployment.
- Remaining limitations and prioritized follow-up work.
- Accurate updates to README, implementation plan, and build status.

Do not declare “production ready” unless the release gate is met. Stop after the report.
