# Frontend Implementation Plan — StudySpace PWA

**Repository:** `sawroop1242/pw-style-learning-app`  
**Application:** Mobile-first, installable learning PWA  
**Frontend location:** `frontend/`  
**Status:** Planning only. This document does not claim that the listed screens or behaviors are implemented.

## 1. Purpose and implementation contract

Build the complete student and staff-facing web experience on top of the existing frontend. Inspect the current HTML, CSS, JavaScript, manifest, and service worker before changing them. Preserve the existing vanilla JavaScript approach unless a documented audit demonstrates that it cannot meet a requirement; do not rewrite the framework simply for preference.

This is the frontend companion to [BACKEND_IMPLEMENTATION_PLAN.md](BACKEND_IMPLEMENTATION_PLAN.md). The backend owns identity, permissions, course publication, access-code decisions, scores, attempt history, analytics, and private learner data. The frontend must never be treated as a security boundary or as the source of truth for scores or permissions.

Follow [BUILD_MASTER_PROMPT.md](BUILD_MASTER_PROMPT.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), the feature specifications, and the ordered milestone prompts. Implement one milestone at a time, starting with Milestone 1 foundation verification. These plans do not authorize skipping the milestone sequence.

## 2. Product and UX principles

- Mobile-first layout, usable on narrow Android screens from 320 CSS pixels and on desktop.
- PW-inspired purple-and-white visual direction without copying proprietary branding or assets.
- Fast initial shell, restrained data usage, readable typography, clear hierarchy, and touch-friendly controls.
- Accessible semantic HTML, labels, keyboard operation, visible focus, contrast, and announced status/error messages.
- One consistent navigation system and shared components; no duplicate independent implementations of the same feature.
- Every visible control must work, be disabled with an explanation, or be removed. Never show fake success or demo data as live server data.
- All course materials and media links must be authorized. Do not bypass provider restrictions or access controls.

## 3. Roles and navigation

### Student experience
- Sign up, sign in, sign out, forgot password with email OTP, and change password.
- Home/dashboard: continue learning, recent courses, progress summary, upcoming planner tasks, and available released test insights.
- Course catalogue with search, filters, sort, course cards, and clear locked/unlocked states.
- Course detail: description, course status, folders/sections, lesson/resource list, access requirements, and safe resource opening.
- Lesson view: title, authorized video/embed/external link, related notes, completion state, next/previous navigation, and loading/error states.
- Tests: test-series list, instructions, section overview, timer state, question navigation, answer selection, marked-for-review state, submission confirmation, result and explanation screens according to release policy.
- Notes, bookmarks, revision list, and resource-linked navigation.
- Study planner: task list, daily/weekly view, create/edit/complete/delete tasks, goals if supported by the agreed API, and opt-in best-effort browser reminders.
- Profile/security: account details, password change, sign-out, and relevant privacy controls.
- PWA install guidance and safe offline/error states.

### Main-admin and sub-admin experience
- Staff navigation must be rendered only after server-confirmed role data; route guards are UX only and never replace backend authorization.
- Main admin: platform-wide course/user/test overview, course and access-code administration where authorized, admin analytics, audit-relevant actions, and operational status views only if the backend exposes them.
- Sub-admin: only owned/assigned courses, their learners where authorized, course resources, test management and scoped analytics.
- Do not expose staff pages, learner lists, or admin metrics to students by merely hiding menu items. Backend permissions remain mandatory.
- Keep role-specific screens and actions explicit; do not assume a sub-admin can access global platform data.

## 4. Screen and feature inventory

| Area | Required behavior |
|---|---|
| Authentication | Registration validation; login/logout; OTP request and verification/reset; current-password change; loading, expired OTP, throttling, and delivery-failure states |
| Dashboard | Fetch real current-user data; continue-learning links; progress and tasks; handle empty/new account state |
| Course discovery | Bounded search, filters and sorting supported by API; pagination; no unpublished-course leakage; clear no-results/retry states |
| Course detail | Published metadata, folder/lesson ordering, free/locked/access-granted states, and access-code redemption when supported |
| Lessons/resources | Safe URL handling, authorized playback/opening, completion sync, next/previous navigation, and unavailable-resource messaging |
| Test series | Instructions, attempt eligibility, timers, section navigation, save/resume if supported, submit, server-scored result, explanation/result-release states |
| Notes | Create/edit/delete, validation, resource association, persistence, and sync failures |
| Bookmarks/revision | Add/remove bookmarks; revision states/list; duplicates and deleted/unavailable resources handled safely |
| Student analytics | Only persisted server-derived attempts and metrics; respect result-release and visibility rules |
| Admin analytics | Aggregates from backend; display scope and date range; empty/error states; never calculate privileged global totals from partial client data |
| Study planner | Private tasks, daily/weekly display, due dates/timezones, completion, and optional permission-based reminders |
| Account/profile | Account details, password change, logout and safe auth-expiry behavior |
| PWA/offline | Installable shell, offline banner/states, low-data preference, retry/reconnect handling, update notice |
| Exports | Only authorized backend-generated/exportable data; warn appropriately; do not expose other users' data |
| Accessibility | Keyboard focus, labels, semantic structure, status announcements, reduced-motion consideration, and zoom/reflow |

## 5. Frontend architecture

### 5.1 Shared application structure
Keep code organized around the existing project conventions. At minimum, define clear modules/responsibilities for:
- application bootstrap and route/view selection;
- API client and endpoint wrappers;
- authentication/session state;
- shared layout, navigation, buttons, forms, dialogs, alerts, loading and empty states;
- course catalogue/detail and lesson/resource views;
- quiz/test-taking state and result views;
- notes/bookmarks/revision;
- dashboard, analytics and planner;
- PWA/offline status and install/update handling;
- safe formatting and validation utilities.

These are logical boundaries, not a mandate to create a specific framework or file tree without first inspecting the repository.

### 5.2 API client
- Read API base URL from a documented runtime/build configuration suitable for the actual hosting model. Do not hard-code production secrets or assume frontend and API share an origin.
- Centralize request construction, JSON parsing, pagination, timeout/abort handling where practical, and consistent errors.
- Handle authentication expiry/401 centrally, prevent duplicate submissions, and avoid logging access tokens or sensitive payloads.
- Do not silently fall back to demo data when API calls fail. A demo mode, if retained, must be explicitly enabled and clearly labelled.
- Match the backend's actual response envelope and pagination contract; document any API mismatch instead of guessing.
- Do not place tokens or sensitive records in URLs, analytics events, console logs, or service-worker caches.

### 5.3 State and persistence
- Server state is authoritative for accounts, courses, access grants, notes, progress, bookmarks, planner tasks, attempts, scores and analytics.
- Local storage may hold non-sensitive preferences (for example theme or low-data choice) and carefully designed UI drafts only where justified.
- Do not trust client-side role flags, course unlock flags, timers, scores, correct answers, or local progress as authorization or scoring evidence.
- Offline writes must be limited to specifically approved operations with documented idempotency, conflict resolution, retry behavior, and clear pending/synced/failed states. Do not promise sync until confirmed by the server.

## 6. Security and privacy requirements

- Render all user/course text as text by default; never inject untrusted HTML.
- Validate URL protocols and destinations before opening/embedding media; use restrictive iframe permissions and provider-appropriate embedding rules.
- Never include correct answers in pre-submission payloads or reveal hidden answers in DOM attributes, source, local storage, or cached responses.
- Avoid sensitive content in client logs and error reports. Redact email/OTP/token/password and private notes.
- Handle logout and account switching by clearing in-memory private state and any user-specific client cache; the service worker must not cache private API data.
- Treat a locked state as display information only; every access attempt must be checked by the API.
- Do not claim a public external PDF/video URL is private. Protected/paid media needs backend-authorized delivery or a clearly documented public-link policy.
- Avoid spreadsheet formula injection in any frontend-created export; prefer a validated server export contract.
- Respect user privacy and collect no unnecessary telemetry.

## 7. PWA and offline policy

- Validate `manifest.webmanifest`, icons, display mode, theme colors, start URL, scope, and installation behavior.
- Service worker may cache versioned, safe static app-shell assets only according to the approved cache policy.
- Never cache authenticated API responses, tokens, private notes/progress/bookmarks/planner records, active tests, answer keys, or protected media in shared Cache Storage.
- Do not return the app shell for arbitrary failed API GETs. Distinguish navigation fallback from API/resource failures.
- Add clear offline and reconnect states; never show an offline mutation as server-saved.
- On service-worker upgrades, delete only this application's obsolete caches and preserve unrelated caches.
- Low-data mode must reduce optional loads without breaking core access or hiding important error messages.
- Browser notifications are optional and best-effort; request permission only after a clear user action and do not imply guaranteed delivery.

## 8. Performance and accessibility acceptance

- Avoid horizontal overflow at 320 px; test common narrow Android viewports and desktop.
- Use pagination and bounded rendering for large course/question lists.
- Avoid unnecessary network requests, oversized assets, and blocking scripts.
- Provide loading, empty, error, retry, locked, offline, and success states for every data-driven view.
- Forms have labels, field-level validation, and accessible error announcements.
- Interactive controls have keyboard support and visible focus; dialogs manage focus and Escape behavior appropriately.
- Test zoom/reflow, color contrast, touch target sizing, and reduced-motion preferences where applicable.
- No primary learner or admin action is inert or represented by a placeholder.

## 9. Frontend test strategy

Add tests in the style supported by the existing repository; choose tooling after inspecting the current setup rather than adding a heavy stack without reason.

- Unit tests: API error parsing, auth state transitions, URL validation, display formatting, and local state helpers.
- Component/view tests where practical: form validation, loading/error/empty states, navigation, and role-dependent presentation.
- Integration tests: authentication requests, pagination, course discovery, notes/progress sync, quiz submit/result rendering, and offline errors.
- Browser/manual end-to-end checks: register/login, discover/open a course, open a lesson, update progress, take a test, view permitted results, create a note/bookmark, use planner, logout, and repeat with a staff role.
- Security regression checks: hidden menu is not treated as authorization; no answer keys before submission; private API payloads absent from Cache Storage; account switching clears private UI state.
- Record exact commands, browser/device, viewport, environment and outcomes. Do not report unrun tests as passed.

## 10. Ordered frontend delivery

Frontend work depends on verified backend contracts and follows the shared milestones:

1. **Milestone 1 — Foundation verification:** inspect and verify current repo/runtime/CI; do not start a UI rewrite.
2. **Milestone 7 — Frontend API foundation:** API configuration/client, auth UX integration, errors, loading states and responsive shell after prior backend milestones are ready.
3. **Milestone 8 — Complete learning experience:** course discovery, lessons, tests/results, notes/bookmarks/revision, dashboard, profile, planner and authorized analytics.
4. **Milestone 9 — PWA/offline:** installability, safe cache strategy, low-data and offline behavior.
5. **Milestone 10 — Quality/security:** automated checks, accessibility, performance, security and full journey regression.
6. **Milestone 11 — Deployment:** configure static frontend hosting separately from Django API hosting; verify HTTPS, API origin/CORS, caching and smoke tests.
7. **Milestone 12 — Final acceptance:** execute end-to-end checklist and document evidence and limitations.

Do not jump to a later frontend milestone while prerequisite backend contracts or earlier milestone exit criteria are incomplete.

## 11. Frontend definition of done

A frontend feature is done only when:
- the screen is connected to the documented API and real persisted data;
- success, loading, empty, invalid, permission-denied, expired-session, network-failure and offline behavior are handled as applicable;
- responsive and accessibility checks are recorded;
- security/privacy behavior is covered by tests or explicit verification;
- no misleading placeholder or fake success remains;
- relevant docs and `docs/BUILD_STATUS.md` record actual results.

**Current status:** Plan authored; no frontend source code, tests, or deployment are changed or verified by this document.
