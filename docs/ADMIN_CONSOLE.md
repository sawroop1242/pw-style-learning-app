# The staff console

Django admin, restyled and rearranged to the thirty-screen design atlas. This
page is the map: what each screen is, where it lives, and what it is allowed to
show.

## Shape

| Part | What it is |
|---|---|
| Rail | Dark navy (`#0e1729`), grouped by job, not by app. The current screen is marked. Below 1024px it is a drawer |
| Top bar | Breadcrumb trail, **Jump to** (a search over the screens this account may open, `/` to focus), account chip with a POST logout |
| Working area | `#f6f7fb`, white cards, 14px radius, one violet (`#6d5dfc`) primary action per screen |
| Status | One chip for everything: green is live, blue is draft, amber is pending, red is failed. `config.admin_ui.pill` |

There is no dark mode. The palette is pinned light in `staff/admin.css`: an OS
set to dark would otherwise get a half-converted console, and long question
forms read better on white.

## The thirty screens

| # | Screen | Where |
|---|---|---|
| 01 | Admin console home | `/admin/` — four stat tiles, then one card per job |
| 02 | Batches list | `/admin/courses/course/` |
| 03 | Batch editor | `/admin/courses/course/<id>/change/` — sections inline |
| 04 | Batch sections | `/admin/courses/coursefolder/` |
| 05 | Lessons list | `/admin/courses/lesson/` |
| 06 | Lesson editor | `/admin/courses/lesson/<id>/change/` |
| 07 | Notes and PDFs | `/admin/courses/pdfresource/` |
| 08 | Faculty | `/admin/courses/coursefaculty/` |
| 09 | Test series | `/admin/courses/testseries/` |
| 10 | Tests list | `/admin/courses/quiz/` |
| 11 | Test editor | `/admin/courses/quiz/<id>/change/` — questions inline |
| 12 | Question bank and editor | `/admin/courses/question/` — choices inline |
| 13 | CSV import jobs | `/admin/courses/csvimportjob/` |
| 14 | Access codes | `/admin/courses/accesscode/` |
| 15 | Access grants | `/admin/courses/courseaccessgrant/` |
| 16 | R2 accounts | `/admin/objectstore/r2account/` |
| 17 | R2 buckets | `/admin/objectstore/r2bucket/` |
| 18 | Announcements | `/admin/courses/communitypost/` |
| 19 | Question reports | `/admin/courses/questionreport/` |
| 20 | Attempts | `/admin/courses/quizattempt/` |
| 21 | Attempt answers | `/admin/courses/attemptanswer/` |
| 22 | Learner notes | `/admin/courses/note/` |
| 23 | Progress | `/admin/courses/progress/` |
| 24 | Bookmarks | `/admin/courses/bookmark/` |
| 25 | Revision items | `/admin/courses/revisionitem/` |
| 26 | Study tasks | `/admin/courses/studytask/` |
| 27 | Users and groups | `/admin/auth/user/`, `/admin/auth/group/` |
| 28 | Profiles and roles | `/admin/accounts/profile/` |
| 29 | Password-reset codes | `/admin/accounts/passwordresetotp/` |
| 30 | Audit and tokens | `/admin/accounts/auditevent/`, `/admin/token_blacklist/` |

Every screen lists only what the signed-in account may open: a sub-admin sees
their own batches, lessons and tests, never someone else's. That scoping lives
in the model admins (`OwnershipScopedAdmin`), not in the theme.

## Reading a list screen

- **Page head** — the model's plural name, how many rows the current filter
  matched, and the one action the screen exists for (`Add …`).
- **Chips** — filters run across the top instead of down the right edge, so two
  filters are one click each. A chip keeps the search term and the other
  filters; page links come from Django's own paginator, so they keep them too.
- **Table** — white card, uppercase column heads, a pill where a state belongs.
- **Footer** — `Showing 1–25 of 431`, with the page links beside it.

## Editing

Fieldsets are cards, the save bar is sticky, and `History` sits in the page head.
Nothing about Django's validation, inlines, autocomplete or permissions changed:
if a field is added to a model and a ModelAdmin lists it, it appears here.

### Secondary screens

History, delete (single and bulk), password change and the signed-out page share
the same head-and-card frame. Each of those templates extends the Django
original and calls `{{ block.super }}` for the body, so the POST form, the CSRF
token and Django's pagination survive an upgrade untouched.

### Signed out

The login screen keeps the brand and gains a heading, but drops everything that
implies a session: no jump box, no account menu, no sign-out. `has_permission`
is `True` for anonymous users on the login page, so those parts are gated on the
screen having `opts` — not on `has_permission` alone.

## Behaviour in the browser

`backend/static/staff/admin.js` is one IIFE, no inline handlers (the CSP blocks
those). It adds:

| Control | Keys | What it does |
| --- | --- | --- |
| Jump box (`/` to focus) | `↑` `↓` `Enter` `Esc` | Starts-with matches first, then contains; the list is `role="listbox"` and the input points at the active option with `aria-activedescendant`. |
| Rail filter | — | Hides non-matching rows, then hides groups with nothing left. |
| Account menu | `Esc` / click outside | `details`-based, so it opens without JavaScript. |
| Rail drawer (≤1024px) | `Esc` | Closes on escape, on a click outside, and after a screen is chosen. |

It also labels the bare widgets inside a tabular inline from their column head
and drops `aria-describedby` references to elements Django did not render.

## Colour

One palette, light only. Django's own variables are pinned in the same block, so
a machine set to a dark OS theme still gets the light console rather than a
half-converted one. Every text pair used in the console was measured against
AA (4.5:1) when this was written; the muted grey, the green and the amber pills
were darkened to get there.

## Tests

`courses/tests/test_admin_theme.py` renders the home, a list, a filtered list, an
empty list, an edit screen, an add screen, the login page and the signed-out
shell, and asserts the shape above — a template that loses a block or a tag that
stops existing fails there. `objectstore/tests/` covers the storage screens;
`courses/tests/test_admin.py` covers the scoping.
