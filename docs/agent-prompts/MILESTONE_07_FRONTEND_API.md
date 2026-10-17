# Coding-Agent Prompt — Milestone 7: Frontend API Client and Application Foundation

## Objective
Connect the existing mobile-first frontend to the Django API through a reliable, testable API layer and build the shared application shell. Do not rebuild the entire learning experience in this milestone.

## Inspect first
Read all frontend HTML, CSS, JavaScript, manifest, and service-worker code. Identify how views/navigation are currently rendered, current localStorage/demo behavior, browser support, and available test tooling. Preserve vanilla JS unless a concrete blocker justifies a separate, documented framework migration.

## API client
- Configure API base URL from a documented environment/build-time setting compatible with the chosen static hosting. Do not assume browser JavaScript can read server environment variables at runtime.
- Centralize fetch requests, JSON parsing, timeout/abort handling where supported, error normalization, pagination, and authentication behavior.
- Handle 401/403, expired access tokens, refresh failure, offline/network failure, and server validation errors explicitly.
- Avoid storing long-lived sensitive credentials in insecure persistent browser storage. Document the JWT storage trade-off and choose the least-risk practical approach for this architecture.
- Do not retry unsafe write operations blindly. Retry only when the request semantics support it.
- Remove silent fake-success behavior. Clearly label any optional demo mode and never confuse it with server-persisted user data.

## Application shell and UX
- Create consistent navigation and reusable helpers for loading, empty, error, retry, signed-out, and offline states.
- Ensure every form has labels, validation feedback, and keyboard support.
- Add accessible focus management and semantic landmarks.
- Avoid unsafe HTML injection; render untrusted text using safe DOM APIs.
- Use responsive CSS and check 320 px width without horizontal overflow.
- Preserve the existing purple/white design direction without copying proprietary branding.

## Tests
Add practical unit/browser tests for API success/error parsing, pagination, auth expiration behavior, offline/network errors, safe rendering, navigation, and responsive smoke checks where available. Run syntax checks and existing tests.

## Acceptance
Frontend can sign up/sign in against a running Django API and display actual server responses. Setup instructions explain frontend/API URLs and CORS. Update status and stop before Milestone 8.
