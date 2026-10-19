# Study Planner and Reminders — Product and Engineering Specification

## Goal
Help students set realistic learning goals and schedule lessons, tests, and revision. The planner is personal account data and must integrate with the existing course, progress, and test systems.

## Student features
- Create, edit, complete, postpone, and delete study tasks.
- Link a task to an accessible course, lesson, test, or revision item; allow a personal task without a linked resource.
- Set local date/time, optional duration, priority, and recurrence only when recurrence rules are clearly supported.
- Daily and weekly views, today's tasks, overdue tasks, upcoming tasks, and a progress summary.
- Optional daily/weekly goals and a streak based only on clearly defined completed activity. Do not punish users for missed days or misrepresent activity.
- Optional browser/PWA notifications only after explicit permission; provide in-app reminders when notifications are unavailable or denied.
- Allow users to disable reminders, change quiet hours/time zone, and remove notification permission through browser settings.

## Time and notification rules
- Store timezone-aware timestamps and preserve the user's intended local time across daylight-saving/time-zone changes where applicable.
- Reminder delivery must be best-effort and clearly documented; a PWA cannot guarantee background delivery on every mobile browser.
- Do not promise server push notifications unless a real push infrastructure has been separately implemented and tested.
- Avoid duplicate reminders and cap frequency. Never send marketing notifications by default.
- No email/SMS/WhatsApp reminder provider is required for the initial version.

## Privacy and permissions
- All tasks/goals/preferences are private to the authenticated user.
- Enforce ownership in backend querysets and object permissions; never accept arbitrary owner IDs.
- Validate task dates, duration, recurrence, and linked-resource access.
- On resource deletion/unpublishing, show a safe unavailable reference without exposing protected content.
- Do not collect location or contacts for reminders.

## UX and accessibility
- Mobile-first daily/weekly planner, fast task creation, clear completion status and timezone display.
- Keyboard/screen-reader support, touch-friendly controls, loading/empty/error states, and confirmation for destructive actions.
- Gracefully degrade when offline or notifications are unsupported. Do not falsely claim a reminder was delivered.

## Required tests
Task CRUD and ownership, invalid dates/durations, time-zone handling, recurrence edge cases if supported, notification permission denied, duplicate reminder prevention, linked-resource access, and mobile layout/accessibility.

## Definition of done
Integrate with existing user/account and progress systems; add models/migrations only as needed, real APIs, UI and tests in milestone order. Document notification limitations and verify behavior in target browsers.
