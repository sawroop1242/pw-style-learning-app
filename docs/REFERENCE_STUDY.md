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
   `AttemptAnswer` rows already existed; nothing aggregated them. This is the
   single most-praised PW feature and the cheapest differentiator we own. It is
   now shipped as P3 (see §5) — the gap was also a data gap: the one label a
   question carried was doing two jobs (section *and* chapter), so nothing could
   rank a chapter without also breaking the exam window's tabs.
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
| P3 | Weak-topic analysis from marked answers | PW (G2 reviews), edX analytics | `/api/insights/topics/` + `dashboard.html` (shipped) | M |
| P4 | Batch page as tabs: overview / classes / papers / teachers | PW batch-overview URL | `course.html` (shipped) | M |
| P5 | Schedule ("today's classes"), with no live claim | PW, Frappe `lms_batch_timetable` | `GET /api/schedule/` + `#schedule-list` / `#class-timetable` (shipped) | L |
| P6 | Drag-and-drop outline in the console | Frappe `CourseOutline.vue` | `/admin/courses/course/<id>/outline/` (shipped) | M |
| P7 | Faceted catalogue filters | Unacademy, richie | `courses.html` + `/api/courses/facets/` (shipped) | M |
| P8 | Goal-first entry ("what are you preparing for?") | Unacademy landing | home hero | S |
| P9 | Command palette in the console | Frappe `CommandPalette.vue`, unfold | we have the jump box; extend to actions | S |
| P10 | Certificates on completion | Frappe `lms_certificate` | out of scope until batches have rules | – |

## 4. What we are not doing

- **No downloads, no "download video".** The user removed it; PW's offline mode
  is not a licence to bring it back.
- **No live-class infrastructure, and no live claims either.** PW's live
  classes need a conferencing provider, a teacher presence and a studio. We
  embed video. So there is no "join the stream" button, no Live badge and no
  `live` state in the API: a class is a recording, the timetable says the hour
  it airs, and whether that hour has passed. A badge that cannot be earned is
  a lie with a nice colour.
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

**P3 shipped** — weak-topic analysis, the pattern the study found in PW's
"AI-based test analysis … weak chapters" reviews and in edX's per-topic
analytics.

- **The data had to be split first.** A question carried one label, `topic`,
  used both as the exam window's section ("Physics") and as the thing a result
  should rank ("Kinematics"). Those are different questions — *which part of the
  paper* and *which idea does this test* — so `Question.section` now holds the
  first and `Question.topic` the second. Migration `0011` keeps every existing
  label as its section and leaves topics empty: nobody recorded the chapter, and
  inventing one would put a number on a screen that was never measured.
- **`GET /api/insights/topics/`** aggregates the signed-in learner's *released*
  attempts into `{topic, questions, correct, incorrect, unanswered, answered,
  accuracy, score, max_score, attempts}`, plus a `focus` list of the weakest
  chapters. The thresholds travel in the payload (`rules.min_answered = 3`,
  `rules.weak_below = 60`) so the screen prints the rule it used instead of
  asserting a verdict.
- **What it refuses to say.** Accuracy is `correct / (correct + incorrect)`: a
  chapter that was skipped has `accuracy: null`, not 0%. A chapter with fewer
  than three marked answers is never called weak. Unreleased results are not
  read at all, guest attempts are never pooled into a profile, and the numbers
  come from the frozen paper — renaming or deleting a question afterwards cannot
  rewrite what was measured (`test_the_numbers_follow_the_frozen_paper…`).
- **Where it lands.** The result screen's "Where the marks went" panel becomes
  per-chapter, and `dashboard.html` gains "Where to focus": the weakest chapters
  with the rule printed underneath, an honest empty state when nothing has been
  released, and a "no chapter below the threshold" state that does not invent a
  problem to fill the card.
- **The import follows.** CSV schema v2 adds a `topic` column next to `section`
  (`docs/CSV_QUESTION_IMPORT.md`); v1 files still import, untagged.

**P7 shipped** — the faceted catalogue, the pattern Unacademy opens with and the
one PW's own reviewers call the platform's weak spot ("finding the right batch").

- **The facets are counted on the server.** `GET /api/courses/facets/` returns a
  count for every value, and each group is counted with the *other* groups
  applied and **its own left out**. That is the whole rule: ticking Physics must
  not erase Biology from the panel, and "Physics (3)" must mean "three batches
  if this is the only subject ticked", not "three of the six cards currently on
  screen". The old panel counted the current page, so on page 2 of 3 it offered
  a different set of subjects than page 1.
- **Two fields earned their place.** `Course.exam` and `Course.level` (`0012`):
  PW's batch finder is exam-first, and a subject list cannot express "JEE vs
  NEET vs SSC". Both are blank-able, and a blank is not a value — the batch
  stays listed, it just never claims an exam nobody chose.
- **Multi-select, honestly.** Repeated query parameters (`?exam=JEE&exam=NEET`)
  mean either; the panel draws checkbox groups, keeps a ticked value visible
  even when another filter has emptied its group (a filter you cannot see is one
  you cannot remove), and never prints an empty heading.
- **The state lives in the URL**, so a filtered catalogue can be reloaded,
  bookmarked or sent to a classmate and come back the same.
- **The panel is reachable at 320px.** It used to be `display: none` below
  900px with no way to open it; now a Filters button opens the sheet, Escape
  closes it, the button reports the number of active filters, and the checkbox
  inputs are visually hidden but still in the tab order (`display: none` had
  made the whole panel keyboard-inaccessible).
- **`mine` keeps its meaning.** The counts follow it, so "My batches" never
  advertises a filter that would empty it.

**P5 shipped** — a real class schedule, the largest remaining item and the one
the batch page had been missing (`lms_batch_timetable` is the Frappe doctype
that makes it look easy; §1, above).

- **A class got one field, not a status.** `Lesson.starts_at` (`0013`) is an
  optional date-time; nothing else was added. `is_live` is deliberately absent,
  and as of the next run so is every other claim of liveness: these classes are
  recordings at an embed URL, and `courses/schedule.py` computes only whether
  the hour has passed. A stored boolean would outlive its class; a computed
  live window would still describe a broadcast that never happened.
- **No air time means on demand, and on demand is not midnight.** A lesson with
  `starts_at IS NULL` is excluded from the timetable rather than parked at
  00:00. Putting an undated recording on a timetable would invent an hour.
  The admin says so in the field's help text and offers a "No air time" filter.
- **`GET /api/schedule/`** returns one week — `?days` clamped 1–30, and a
  nonsensical value falls back to 7 instead of answering `400`, because a bad
  query parameter should not blank a page. The payload is
  `{timezone, now, scope, window_days, counts, groups, next}` plus a `classes`
  list on each day group: `{id, title, section, starts_at, ends_at,
  duration_minutes, status, recording, is_locked, can_open, course}`.
  **`video_url` is never in it** — the timetable says when a class airs, the
  player says what it plays.
- **Two states, and today's group keeps its finished classes.** `upcoming`
  before the hour, `ended` from it. 19:00 Physics that ran until 19:52 stays on
  today's row all evening — a timetable that erases itself at half past is not
  a record of what happened — and a row only offers **Watch** when the payload
  says there is a recording behind it. `next` is the first class that has not
  aired yet.
- **Who sees what.** No `?course=`: the signed-in learner's own week, built from
  the batches they hold a grant for (plus ones they own) — a guest is asked to
  sign in rather than shown a stranger's timetable. `?course=<id|slug>` is the
  batch's timetable and is public metadata, the same as the curriculum list: a
  batch page may say "Physics, 19:00, Thursday" to everyone. **Recordings stay
  gated** — `is_locked` / `can_open` are computed per class for the caller, so a
  paid recording is listed and locked rather than hidden. Unpublished batches
  and unpublished lessons never appear at all.
- **One clock.** The payload declares its zone (`Asia/Kolkata`), and the page
  prints every air time in it — the same calendar the day headings were cut on.
  Printing the device's zone instead was the tempting shortcut and it is wrong:
  a learner three time zones away would read "Friday" over a time that, in
  their Friday, is still Thursday. `GET /api/courses/<id>/` carries the same
  `timezone`, so a lesson row and the strip above it can never disagree.
- **Two empty states, two sentences.** A quiet day inside a scheduled week
  ("Nothing on today") and a week with nothing in it ("Nothing on the
  timetable") are different facts and get different copy. Neither is styled as
  an error.
- **Where it lands.** `index.html` draws `#schedule-list` grouped by day, today
  first and marked, with a summary line ("N classes today · N still to come
  this week"). `course.html` gains a `#class-timetable` card above the content
  tree — the "Schedule" anchor PW puts on every batch page — and each class row
  in the tree shows its air time when it has one.
- **The old "today's classes" is retired.** `GET /api/lessons/?added=today` was
  "what was uploaded today", which is not a timetable. It is gone from the home
  screen; the endpoint still exists for the player.

**The batch tree shipped** — the structure every batch page in the reference
had and ours did not: **subject → section → its classes and its notes**, read
the way a syllabus is read.

- **`CourseFolder.subject`** (`0014`) is the third level. A plain name rather
  than a table: a provider types "Physics" once per section, and there is
  nothing else to store about it, so a foreign key would add a join to every
  batch page to hold one string. Blank means *not filed*, and the page then
  lists the section under the batch's own subject — it never invents a subject
  the faculty did not choose, and the API returns the blank verbatim.
- **Notes stopped being a place and became files.** They were a fifth tab
  listing every PDF; now each one sits in the section it belongs to, next to
  the classes, which is where a learner looks for "the DPP for this chapter".
  The tab is gone rather than duplicated — two answers to one question is how a
  product starts disagreeing with itself.
- **A file manager's habits, without a file manager's weight.** Native
  `<details>`/`<summary>` disclosure (keyboard, find-in-page, works if the
  module never loads), a search box that filters rows while keeping the open
  chapters open, counts on every folder line, and a row that says what it is —
  a class with its length, a note labelled PDF. A locked note is listed and
  badged, never linked.
- **The page costs five queries, not five per chapter.** The detail endpoint's
  counts read the viewset's annotation instead of re-counting, and classes and
  notes are prefetched with the batch they will ask about. Twelve sections cost
  the same as two, pinned by `test_the_page_does_not_cost_a_query_per_chapter`;
  `_published()` exists because `.filter()` on a prefetched relation silently
  throws the prefetch away.

The next milestone is a decision, not a queue: P9 (console command palette) is
the cheapest thing left, P8 (goal-first home) is the most visible, and P10
(certificates) still waits on batches having rules.

Each later item gets the same treatment: a pattern named, its source cited, its
landing place in this codebase agreed before any code is written.
