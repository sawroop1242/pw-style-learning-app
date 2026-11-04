# What the reference products actually do

A study of four open-source codebases and the two products this app is measured
against, written to answer one question: **what should StudySpace copy, and what
should it deliberately not copy?**

Nothing here is a guess about what a competitor "probably" does. Each claim is
tied to a file in a cloned repository or to a page fetched on 2026-11-04, and
each pattern is followed by the exact place it would land in this codebase.

> Copy the *pattern*, never the *brand*. No PW or Unacademy logo, wordmark,
> teacher photograph, course name or sentence of copy goes into this app, and
> nothing here proposes defeating a DRM check. The references are used the way a
> designer uses a museum: to see how a problem was solved, then solve it again.

## Sources

| Source | What it is | Why it is here |
| --- | --- | --- |
| `frappe/lms` (clone, `main`) | A real LMS: batches, live classes, assessments, certificates | Closest open-source match to a coaching-institute product |
| `unfoldadmin/django-unfold` | A maintained Django admin theme | The console's visual reference |
| `openfun/richie` | Django course catalogue for Open edX | Filtering and catalogue patterns |
| `edx/edx-platform` | The largest open-source LMS | How a course outline is modelled at scale |
| `pw.live`, `unacademy.com` | The two products students compare us to | Learner-side structure and vocabulary |

## 1. What the learner side looks like

**Physics Wallah.** The public site is a mega-menu of exam families (JEE, NEET,
UPSC, boards, government exams, upskilling) with a hero and a stat strip; the
signed-in product is a *batches* list, and each batch is a set of tabs — the
live URL pattern is `pw.live/study-v2/batches/<id>/batch-overview#Description_1`,
i.e. overview, schedule, notes, tests, doubts under one batch rather than five
top-level sections. Independent reviews of the app converge on the same three
points: the dashboard returns you to your last lesson quickly, the interface is
*consistent* between a lecture, a note and a test, and the catalogue is now big
enough that **finding the right batch is the weak spot — filters are the
complaint**. The most-praised feature in G2 reviews is not video at all: it is
*analysis* — "AI-based test analysis and recommendations to help me understand my
weak chapters".

**Unacademy.** The landing page asks one question before anything else — "Select
your goal / exam", eight popular goals, then a "see all 200+" escape hatch. Below
it: a four-number stat strip, then three capability blocks ("Daily live classes",
"Practice and revise", "Learn anytime, anywhere"). The signed-out funnel is
goal → course → sign up; nothing is shown before the goal is chosen.

**Where this codebase already matches:** batches, folders, lessons with embedded
video, PDF notes, exam-pattern quizzes with negative marking, attempts and score
trend, personal notes, bookmarks, revision items, study tasks, community feed,
access codes, Telegram hand-off for paid batches. That is a genuinely complete
feature set — bigger than most open-source LMSes in one respect: it has an
access-code path for paid content without a payment gateway.

**What is missing, in the order a student would notice it:**

1. **Per-batch progress is not real.** `frontend/assets/js/dashboard.js` draws the
   continue-card bar as `row.completed ? 100 : 40` — a hard-coded 40% for every
   lesson that has merely been *opened*. The product shows a number it did not
   measure. (Frappe LMS, by contrast, derives progress from
   `lms/lms/doctype/lms_course_progress`.)
2. **No streak and no study time.** PW and Unacademy both make daily return
   visible. We record `Progress.completed_at` and `Lesson.duration_minutes` and
   show neither as a habit signal.
3. **No weak-topic analysis.** `Question.topic` and the per-question
   `AttemptAnswer` rows already exist; nothing aggregates them. This is the
   single most-praised PW feature and the cheapest differentiator we own.
4. **A batch is one long page.** PW puts overview / schedule / notes / tests /
   doubts in tabs. Our `course.html` stacks folders and lessons and leaves the
   tests and notes of the same batch elsewhere.
5. **The catalogue has no filters.** Only search. PW's own reviewers say this is
   where the biggest platform loses people.

## 2. What a staff console looks like when it is good

`django-unfold` is the strongest evidence available because it is a maintained
theme with real screens behind it. Reading its `templates/admin/change_list.html`
and `change_form.html`:

- **The list is a filter rail plus a result card**, with the filters and the
  table in one flex row (`#changelist` with `x-resize`), and search/actions in a
  single bar above the table. Ours does filters-above-table; theirs is the more
  compact arrangement on wide screens.
- **Every action lives in `nav-global-side`**, i.e. one slot at the top right of
  the content column — not split between a page head and Django's
  `object-tools`. We converged on the same rule last run (one History link, one
  Add button); unfold confirms it.
- **`templates/admin/index.html` is a dashboard of app cards**, each card a link
  list with counts — the same shape as our workflow cards, which is reassuring.
- **Charts are first-class** (`static/unfold/js/chart/chart.js`,
  `ChartEmptyState` in Frappe's Vue side): a number without a trend is not shown
  as a dashboard tile.

`frappe/lms` contributes the one console feature we do not have and clearly
should: **a drag-and-drop course outline** (`CourseOutline.vue` +
`ChapterRow.vue`, using `vuedraggable`) where chapters and lessons are reordered
by dragging, renamed inline, and lessons can be moved between chapters. Our
equivalent is a tabular inline of `position` integers on the course form — the
worst possible way to express an order.

## 3. The catalogue of patterns worth taking

| # | Pattern | Where it is proven | Where it lands here | Effort |
| --- | --- | --- | --- | --- |
| P1 | Real progress, never a placeholder | Frappe `lms_course_progress` | `ProgressSerializer` + `dashboard.js` | S |
| P2 | Streak and study time from completed work | PW / Unacademy dashboards | dashboard figures | S |
| P3 | Weak-topic analysis from marked answers | PW (G2 reviews), edX analytics | new `/api/insights/topics/` | M |
| P4 | Batch page as tabs: overview / classes / notes / papers / teachers | PW batch-overview URL | `course.html` (shipped) | M |
| P5 | Schedule ("today's classes") | PW, Frappe `lms_batch_timetable` | needs a schedule field on lessons | L |
| P6 | Drag-and-drop outline in the console | Frappe `CourseOutline.vue` | `/admin/courses/course/<id>/outline/` (shipped) | M |
| P7 | Faceted catalogue filters | Unacademy, richie | `courses.html` + API facet list | M |
| P8 | Goal-first entry ("what are you preparing for?") | Unacademy landing | home hero | S |
| P9 | Command palette in the console | Frappe `CommandPalette.vue`, unfold | we have the jump box; extend to actions | S |
| P10 | Certificates on completion | Frappe `lms_certificate` | out of scope until batches have rules | – |

## 4. What we are not doing

- **No downloads, no "download video".** The user removed it; PW's offline mode
  is not a licence to bring it back.
- **No live-class infrastructure.** PW's live classes need a conferencing
  provider, a timetable and a teacher presence. We embed video and will say so
  plainly rather than fake a "live" badge.
- **No invented numbers anywhere.** If a panel cannot be computed from a row in
  the database, it renders an empty state — the rule that P1 exists to enforce.
- **No brand, no logo, no teacher photo, no copied sentence.** Structure only.

## 5. This run

**P1 + P2 shipped** — the two smallest patterns with the largest honesty gain.

- `ProgressSerializer` now carries `course` and `lesson_duration_minutes`, so a
  dashboard can draw a batch's share without a request per batch; both are
  read-only.
- `GET /api/progress/?completed=1` answers "how many lessons have I finished"
  with an exact count. The row count could not: a row exists from the moment a
  lesson is *opened*.
- The continue-card bar is the batch's real completion (1 of 3 lessons = 33%)
  instead of the fixed 40% it used to draw for anything merely opened.
- The continue list asks for `ordering=-updated_at`: "continue" means the lesson
  you left, not the one that happens to sit first in the syllabus.
- Two figures joined the head: **Day streak** (consecutive days with a finished
  lesson, yesterday accepted so the number does not read zero every morning) and
  **This week** (minutes from finished lessons, summed from their durations).

**P4 shipped** — the batch page is a five-tab page with an address for each tab.

- `course.html` carries `#batch-tabs` with Overview, Classes, Notes, Papers and
  Teachers, following the ARIA tabs pattern: one tab in the tab order, arrow
  keys (plus Home and End) move between them, and each tab points at a panel
  through `aria-controls`.
- The choice is in the URL — `course.html?slug=…&tab=notes` opens Notes, the
  Back button walks the tabs a visitor visited, and an unknown `?tab=` falls
  back to Overview instead of rendering nothing.
- Notes left the lesson list: they are their own tab, grouped by section, and a
  locked PDF is badged instead of offering a reader it has no file for. Classes
  keeps lessons only, so no row appears twice.
- Papers and Teachers are the old Tests and Faculty panels under the names the
  rest of the product uses; the batch FAQ folded into Overview, where the
  access question it answers is already explained.
- Each tab counts what is behind it (`3` classes, `2` notes, …) and hides the
  badge at zero — "Notes 0" is noise, not information.

**P6 shipped** — the console now has a drag-and-drop outline, the pattern this
study found in `lms/public/js/courseOutline/CourseOutline.vue` (§2, above).

- `/admin/courses/course/<id>/outline/` arranges a batch's sections and classes
  as one list: drag a handle, press ↑ / ↓, or pick another section for a class.
  The batch form's "What is in this batch" card links to it.
- The order is saved as a whole, once. `courses/outline.py` validates the
  payload against the batch — every section once, every class once, no foreign
  rows — and applies nothing when the validation fails, so a refused save
  cannot leave two rows claiming the same position.
- A revision travels with the page: a save built on an order somebody else has
  since changed is answered `409` with a reload link rather than overwriting
  their work.
- The arrows and the section menu are the same operation without a dragging
  movement (WCAG 2.2, 2.5.7), and the handle answers ↑ / ↓ for keyboard use.

P3 — weak-topic analysis from `Question.topic` and the marked `AttemptAnswer`
rows — is the next milestone, and the one that makes the product feel *smart*
rather than merely tidy.

Each later item gets the same treatment: a pattern named, its source cited, its
landing place in this codebase agreed before any code is written.
