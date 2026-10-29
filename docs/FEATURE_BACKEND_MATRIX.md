# Feature ↔ backend matrix

Every control the learner can see, and what it talks to. Produced by walking
each page's HTML and its module, then resolving every path against Django's URL
configuration and calling it with real data.

## Media

| # | Feature | Screen | Endpoint | Verdict |
|---|---|---|---|---|
| 0.1 | Recorded class, direct file | `player.html` | `Lesson.video_url` → `<video>` | connected |
| 0.2 | Recorded class, embed page | `player.html` | `Lesson.video_url` → `<iframe>` | connected — `https://embed.vcdn.me/embed/…` is an HTML player, not a media file, so it is framed instead of handed to `<video src>` |
| 0.3 | Locked recording on a paid batch | `player.html` | `video_url` withheld without a grant | connected |

**Verdicts**

| | Meaning |
|---|---|
| **connected** | The screen calls an endpoint that exists and returns the data it renders. |
| **backend-orphan** | The endpoint is implemented and tested; no screen calls it. The feature exists on the server and is invisible in the app. |
| **ui-orphan** | The screen offers the feature; there is no endpoint. The control is decoration, or it writes somewhere that is thrown away. |

Re-check the connected column with `node tools/checks/live.js`. Its **contract**
section boots every page module against the real API with a recording fetcher,
so the endpoint list is whatever the modules actually request rather than a
hand-written table, then replays each recorded path: a `404` is the one answer
that means a screen is calling something the backend does not publish (`401`,
`403` and `405` all prove the route exists). It currently replays 27 distinct
paths. Findings below are as of commit `ab0493c` + this change.

---

## 1. Catalogue and discovery

| # | Feature | Screen | Endpoint | Verdict |
|---|---|---|---|---|
| 1.1 | Batch grid | `courses.html` | `GET /api/courses/` | connected |
| 1.2 | Free / paid filter | `courses.html` | `?pricing_mode=` | connected |
| 1.3 | Subject facet (from returned rows) | `courses.html` | `?subject=` | connected |
| 1.4 | Text search (top bar + in-page) | shell, `courses.html` | `?search=` | connected |
| 1.5 | Sort (newest, price, title) | `courses.html` | `?ordering=` | connected |
| 1.6 | "My batches" tab | `courses.html?mine=1` | `?mine=1` | connected |
| 1.7 | Paging | `courses.html` | `?page=`, `?page_size=` | connected |
| 1.8 | Batch detail, description, curriculum | `course.html` | `GET /api/courses/?slug=` | connected |
| 1.9 | Paper list for a batch | `course.html` | `GET /api/quizzes/?course=` | connected |
| 1.10 | Enrol with an access code | `course.html` | `POST /api/access-codes/redeem/` | connected |
| 1.11 | Similar batches | `course.html` | `GET /api/courses/?page_size=6` | connected |
| 1.12 | FAQ accordion | `course.html` | — (authored copy) | n/a |
| 1.13 | Faculty panel | `course.html` | `GET /api/courses/<id>/` → `faculty` | connected (`CourseFaculty`, staff CRUD at `/api/staff/faculty/`) |

## 2. Test series and the exam window

| # | Feature | Screen | Endpoint | Verdict |
|---|---|---|---|---|
| 2.1 | Paper list, open / attempted tabs | `tests.html` | `GET /api/quizzes/`, `GET /api/quiz-attempts/` | connected |
| 2.2 | Attempt history | `tests.html` | `GET /api/quiz-attempts/` (now with `quiz_title`) | connected |
| 2.3 | Start a paper (guest or signed in) | `test-player.html` | `POST /api/quizzes/start/` | connected |
| 2.4 | Question paper + choices | `test-player.html` | `GET /api/quizzes/<id>/` | connected |
| 2.5 | Autosave, resume, timer from server deadline | `test-player.html` | `POST …/autosave/` | connected |
| 2.6 | Submit and score | `test-player.html` | `POST …/submit/` | connected |
| 2.7 | Result, section breakdown, solutions | `test-player.html` | `GET …/result/` | connected |
| 2.8 | Report a question | `test-player.html` | `POST /api/question-reports/` (guest token or JWT) | connected |
| 2.9 | Topic-wise strengths | `test-player.html` result | `section_breakdown` is keyed on `Question.topic` | connected |

## 3. Learning loop

| # | Feature | Screen | Endpoint | Verdict |
|---|---|---|---|---|
| 3.1 | Lesson player, chapters, PDFs, notices | `player.html` | `GET /api/lessons/`, `/pdfs/`, `/community/` | connected |
| 3.2 | Record that a lesson was opened / finished | `player.html` | `POST /api/progress/` | connected |
| 3.3 | "Continue learning" and "Lessons done" | `dashboard.html` | read `/api/progress/` | connected once 3.2 writes |
| 3.4 | Note on a lesson | `player.html` "Notes" tab | `GET`/`POST /api/notes/?lesson=` | connected (the tab writes notes and lists the section PDFs below) |
| 3.5 | Notes: list, create | `dashboard.html` | `GET`/`POST /api/notes/` | connected |
| 3.6 | Study plan: create, complete, reopen | `dashboard.html` | `POST /api/study-tasks/`, `…/complete/`, `…/reopen/` | connected |
| 3.7 | Attempt score trend | `dashboard.html` | `GET /api/quiz-attempts/` | connected |
| 3.8 | Upcoming papers | `dashboard.html` | `GET /api/quizzes/?page_size=60` | connected |

## 4. Notifications

| # | Feature | Screen | Endpoint | Verdict |
|---|---|---|---|---|
| 4.1 | Bell in the top bar | every page | `GET /api/notifications/`, `POST /api/notifications/read/` | connected |

The study-planner spec calls for in-app reminders ("provide in-app reminders
when notifications are unavailable or denied"). A bell that never opens is
worse than no bell.

## 5. Downloads and community

| # | Feature | Screen | Endpoint | Verdict |
|---|---|---|---|---|
| 5.1 | Lecture list (only lessons with a recording) | `downloads.html` | `GET /api/lessons/` | connected |
| 5.2 | Chapter PDFs | `downloads.html` | `GET /api/pdfs/` | connected |
| 5.3 | Papers | `downloads.html` | `GET /api/quizzes/` | connected |
| 5.4 | Offline "saved" list | — | none by design (the PWA caches the shell, never student data) | documented |
| 5.5 | Announcement feed | `community.html` | `GET /api/community/` | connected |
| 5.6 | Batch-only feed | `community.html` | `?course=` | connected |

## 6. Account

| # | Feature | Screen | Endpoint | Verdict |
|---|---|---|---|---|
| 6.1 | Register | `login.html` | `POST /api/auth/register/` | connected |
| 6.2 | Sign in / refresh / sign out | all | `/api/token/`, `/api/auth/logout/` | connected |
| 6.3 | Forgot password (OTP) | `login.html` | `/auth/forgot-password/`, `/verify-otp/`, `/resend-otp/` | connected |
| 6.4 | Change password | `login.html` | `POST /api/auth/change-password/` | connected |
| 6.5 | Profile + counts | `profile.html` | `GET /api/auth/me/` | connected |
| 6.6 | Guests attempt tests without signing in | `test-player.html` | `POST /api/quizzes/start/` | connected |

## 7. Staff

| # | Feature | Screen | Endpoint | Verdict |
|---|---|---|---|---|
| 7.1 | Course, folder, lesson, PDF, quiz, question authoring | Django admin + `/api/staff/*` | full CRUD, publish/unpublish | connected |
| 7.2 | Access-code issuing | `/api/staff/access-codes/` | create, revoke | connected |
| 7.3 | CSV question import | `/api/staff/import-jobs/` | schema, template, validate, confirm, export | connected |

---

## What this change closes

| Gap | Fix |
|---|---|
| 1.13 Faculty | `CourseFaculty` model, nested in the course payload, staff CRUD, seeded rows |
| 2.2 `Test #5` | `quiz_title` on the attempt serializer |
| 2.8 Question report | `QuestionReport` model + `POST /api/question-reports/`, works for guest attempts via `X-Attempt-Token` |
| 2.9 Topics | `topic_breakdown` in the result payload; review screen renders it |
| 3.2 Progress | player posts `progress` on open and on "Mark complete" |
| 3.4 Lesson notes | player "Notes" tab lists and writes learner notes for the lesson |
| 3.6 Planner | dashboard creates, completes and reopens tasks |
| 4.1 Bell | `GET /api/notifications/` derives an inbox from published announcements, due tasks and released results; the dot reflects the count |

Each gap is covered by a backend test that asserts the response **and** a DOM
test that asserts the screen uses it.
