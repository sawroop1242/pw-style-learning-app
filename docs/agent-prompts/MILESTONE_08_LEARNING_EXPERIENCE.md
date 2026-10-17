# Coding-Agent Prompt — Milestone 8: Complete Learner Experience

## Objective
Connect all core learning journeys to real backend behavior. A visually polished screen with nonfunctional buttons or demo-only state does not satisfy this milestone.

## Required student journeys
1. Registration, login, logout behavior, and profile view/edit.
2. Dashboard populated from the authenticated user's actual courses/lesson progress and quiz attempts; handle a new account with no activity.
3. Browse published courses; search/filter/paginate; open course details.
4. Open a lesson, show authorized video/link handling and useful fallback when embed playback is unsupported, and mark lesson complete/incomplete according to the API.
5. Take a quiz, submit answers, view server-calculated score and post-submission explanations, then inspect attempt history.
6. Create, edit, list, and delete notes; show whether changes are saved, pending, or failed.
7. Navigate across views, refresh the page, and recover the appropriate signed-in/out state without leaking another user's data.

## UX requirements
- Mobile-first layout, touch-friendly controls, clear progress, empty/loading/error/retry states.
- No dead primary actions, placeholder buttons that look functional, or hidden failures.
- No client-side answer scoring as source of truth.
- Do not display fabricated metrics or demo courses as real backend data.
- Safe text rendering and accessible forms, labels, status announcements, focus behavior, and contrast.
- Graceful media fallback, including opening an authorized external video URL where embed is not supported.
- Confirm destructive note actions and avoid losing unsaved content unexpectedly.

## Integration and testing
Use a real local backend and test account. Add frontend integration/end-to-end coverage to the extent supported by the repository. Test successful, empty, invalid-input, unauthorized, expired-session, and offline scenarios. Test narrow mobile and desktop viewports; record the actual browser/tool used.

## Acceptance
All seven journeys work against the API, primary controls are functional, and known limitations are explicit. Update status and stop before Milestone 9.
