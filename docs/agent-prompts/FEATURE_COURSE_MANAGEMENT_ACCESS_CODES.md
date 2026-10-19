# Coding-Agent Prompt — Course Management, Telegram Contact, and Access Codes

## Before implementation
Read `docs/FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md` completely, then inspect the actual models, migrations, admin, serializers, views, permissions, routes, frontend, tests, and build status. This prompt supplements the milestone sequence; it does not authorize skipping a milestone or implementing the whole system in one run.

## Execution rule
- Run exactly the currently authorized milestone from `docs/agent-prompts/README.md`.
- If working on Milestone 1, verify the foundation only and do not implement product features.
- In Milestone 2, implement the data-model/admin subset.
- In Milestone 3, implement role and permission enforcement.
- In Milestone 4, implement course/content/access APIs and their validation.
- In Milestone 8, implement the learner-facing screens and end-to-end code redemption journey.
- If the user explicitly asks to run this standalone prompt after prerequisite milestones, first verify those prerequisites are complete and then implement only the next uncompleted slice, recording it in the plan.
- Do not satisfy implementation work by writing more documentation alone.

## Non-negotiable product decisions
1. Main admin creates and deactivates sub-admin accounts. Sub-admins can manage only their own courses and related content/codes; they cannot create admins or manage other providers' data.
2. Courses have cover image URL, description, subject/category, published/draft state, price mode (free/paid), and provider Telegram contact.
3. A course contains subject folders. Folders contain titled video lessons with validated embed URLs and titled chapter PDFs with download resources.
4. Free courses need no code. Paid courses are unlocked only by a valid code redeemed server-side.
5. Only main admins and authorized course-owning sub-admins can generate/revoke course-bound codes. There is no payment gateway, online checkout, UPI payment, or alternate in-app payment path.
6. The course detail page shows the provider's Telegram contact and tells learners to contact that provider to obtain a code. The app must not claim to verify payments or Telegram messages.
7. Paid PDFs/resources must not be exposed through permanent public links if the app claims to enforce access. Use private storage, an authenticated download endpoint, or short-lived signed URLs after authorization.
8. Access checks happen server-side on every protected API/media-download request. Frontend state is never authoritative.

## Implementation quality
Follow `docs/FEATURE_SPEC_COURSES_AND_ACCESS_CODES.md` for code entropy and hashing, one-use-by-default redemption, expiry/revocation, rate limiting, atomic redemption, audit events, safe URL validation, pricing invariants, migrations, UX states, and the full test matrix. Reuse sound existing models and avoid duplicate abstractions.

## Stop condition and report
At the end of the authorized milestone, run its actual checks and report changed source files, migrations, exact test commands/results, remaining risks, and status/plan updates. Stop. Never fabricate successful tests or production readiness.
