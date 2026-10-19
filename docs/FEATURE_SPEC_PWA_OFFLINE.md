# PWA Offline Learning and Low-Data Mode — Product and Engineering Specification

## Goal
Make the existing installable PWA resilient on unreliable mobile connections while keeping account data private and respecting media licensing/access controls. This supplements Milestone 9; it does not authorize unsafe caching of private content.

## Offline behavior
- App shell, versioned CSS/JS, icons and other safe public static assets may be cached for installability and offline navigation.
- Show a clear offline indicator and distinguish cached content from live server data.
- Public catalogue metadata may be cached only under a documented freshness/expiry strategy and only if it contains no private fields.
- Notes/progress updates may be queued only if the feature is implemented with an explicit conflict and retry policy. Show pending/synced/failed states and avoid duplicate submissions.
- Optional offline notes/PDF access must be restricted to content that is legally and technically permitted for offline storage, with an explicit user action and a removal mechanism. Never assume an external video embed is downloadable or available offline.
- Never cache authentication tokens, OTPs, authenticated API responses, private notes, personal dashboards, test answer keys, active test payloads or paid protected media in a shared service-worker cache.
- Do not allow offline test submission to bypass server deadlines, attempt limits, access grants or result-release rules.

## Low-data mode
- Offer a user-controlled preference to reduce nonessential images/animations and defer thumbnails until needed.
- Respect reduced-motion settings and provide text alternatives.
- Do not lower question readability or hide essential status/error information.
- Keep cache size bounded; version caches, delete obsolete entries and handle quota errors.

## Reliability and security
- Use a documented service-worker strategy by resource class (app shell, public static assets, public catalogue, authenticated APIs).
- Avoid cache-first for sensitive or frequently changing resources.
- Use HTTPS in deployed environments and handle service-worker update prompts safely.
- Prevent stale cached access-control decisions from unlocking protected resources.
- Define behavior for logout/account switching, cache cleanup and shared-device privacy.
- Provide safe retry with idempotency where needed; never silently report unsynced changes as saved.

## Required tests
Offline first launch after prior install, offline navigation, cache update/eviction, logout/account switch, API failure, queued update retry/duplicate protection, cache privacy inspection, low-data preference, and protected-content access after access changes.

## Definition of done
Pass real browser/PWA checks on supported mobile browsers, document supported offline cases and limitations, and verify no sensitive data is stored in shared caches. Do not claim offline media playback unless tested and explicitly authorized by the media provider.
