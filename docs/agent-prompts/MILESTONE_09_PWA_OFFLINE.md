# Coding-Agent Prompt — Milestone 9: PWA Installation and Safe Offline Behavior

## Objective
Make StudySpace installable and useful under intermittent connectivity without leaking private learner data into shared caches.

## Inspect first
Review manifest, icons, service worker registration, precache/runtime cache rules, app shell routes, API client, and browser support. Identify existing caches and upgrade behavior.

## Requirements
- Valid web app manifest with correct name/short name, start URL, scope, display mode, theme/background colors, and available icons of required sizes.
- Service worker cache versioning and predictable installation, activation, update, and obsolete-cache cleanup.
- Precache only safe static app-shell resources needed offline. Use an explicit allowlist; do not cache arbitrary GET responses.
- Never place authenticated API responses, notes, progress, quiz attempts, access/refresh tokens, or other private data in Cache Storage.
- Do not return the app shell for every failed network request, especially API calls or unknown resource paths.
- Offline mode must clearly distinguish cached public content from unavailable account-backed data.
- Pending writes must not be represented as synced. If an offline write queue is implemented, define idempotency, ownership, retry/backoff, logout/user-switch cleanup, and conflict behavior before enabling it.
- Make cache cleanup scoped to this application's named caches only.
- Ensure app works when service workers are unsupported and explains when installation is unavailable.

## Tests and manual validation
Add tests or scripted checks for manifest correctness, cache allowlists, API exclusion, activation cleanup, failed API request behavior, and registration errors. Perform browser-based online/offline and update tests if tooling exists; record browser/version and observed results.

## Acceptance
Installability and offline shell behavior are verified on supported browsers; private data is not cached; API errors remain API errors rather than app-shell HTML. Update status and stop before Milestone 10.
