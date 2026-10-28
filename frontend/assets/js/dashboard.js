/**
 * My learning.
 *
 * Every panel resolves from an endpoint that actually returns the data:
 * `/courses/?mine=1`, `/progress/`, `/quiz-attempts/`, `/quizzes/`,
 * `/notes/` and `/study-tasks/`. A guest is asked to sign in rather than shown
 * a borrowed student's figures.
 */

import {
  $, esc, storage, isSignedIn, request, getJson, rows, apiQuery, initials,
  shortDate, money
} from './core.js';
import { mountChrome, icon, emptyState, errorState, toast, wireRetry, thumbTone } from './ui.js';

mountChrome('dashboard');

const signedIn = isSignedIn();

/* ------------------------------------------------------------------ */
/* Small helpers                                                      */
/* ------------------------------------------------------------------ */

const settle = async (path) => {
  try {
    return { ok: true, payload: await getJson(path) };
  } catch (err) {
    return { ok: false, err };
  }
};

function block(host, markup) {
  const node = $(host);
  if (node) node.innerHTML = markup;
}

function signInPrompt(title, body, iconName = 'user') {
  return emptyState({
    title,
    body,
    actionLabel: 'Sign in',
    actionHref: 'login.html?next=dashboard.html',
    iconName
  });
}

/* ------------------------------------------------------------------ */
/* Head                                                               */
/* ------------------------------------------------------------------ */

function renderGreeting() {
  const name = storage.user?.username;
  const hour = new Date().getHours();
  const part = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  $('#greeting').textContent = name ? `${part}, ${name}` : part;

  const sub = $('#greeting-sub');
  if (!signedIn) {
    sub.innerHTML = 'You are signed out. <a class="link" href="login.html?next=dashboard.html">Sign in</a> to see your batches, attempts and notes.';
  } else {
    sub.textContent = 'Your batches, attempts and notes, straight from the database.';
  }
}

function figure(label, value) {
  return `
    <div class="dash-figure">
      <strong>${value === null || value === undefined ? '—' : esc(String(value))}</strong>
      <span>${esc(label)}</span>
    </div>`;
}

function renderFigures({ courses, progress, attempts, notes }) {
  $('#dash-figures').innerHTML = [
    figure('Batches', courses),
    figure('Lessons done', progress),
    figure('Attempts', attempts),
    figure('Notes', notes)
  ].join('');
}

/* ------------------------------------------------------------------ */
/* Continue learning                                                  */
/* ------------------------------------------------------------------ */

function renderContinue(progressRows, lessonMap) {
  const host = $('#continue-list');

  if (!progressRows.length) {
    host.innerHTML = signedIn
      ? emptyState({
          title: 'No lesson started yet',
          body: 'Open a batch and start a lesson — it shows up here so you can pick it straight back up.',
          actionLabel: 'Browse batches',
          actionHref: 'courses.html',
          iconName: 'play'
        })
      : signInPrompt('Sign in to track lessons', 'Progress is kept per account, so this panel fills once you sign in.', 'play');
    return;
  }

  host.innerHTML = progressRows
    .slice(0, 3)
    .map((row) => {
      const lesson = lessonMap.get(row.lesson) || {};
      const title = row.lesson_title || lesson.title || `Lesson ${row.lesson}`;
      return `
        <a class="continue-card" href="player.html?lesson=${row.lesson}">
          <span class="continue-thumb ${thumbTone(lesson.course_title || '')}">${esc(initials(title))}</span>
          <div class="continue-body">
            <h3>${esc(title)}</h3>
            <small class="tiny subtle">${esc(lesson.course_title || 'Batch lesson')}</small>
            <div class="continue-meta">
              <span class="tiny subtle">${row.completed ? 'Completed' : 'Opened'}${
                row.updated_at ? ` · ${shortDate(row.updated_at)}` : ''
              }</span>
              <span class="link" style="font-size:var(--text-xs)">${row.completed ? 'Revisit' : 'Continue'} ${icon('arrow-right')}</span>
            </div>
            <div class="progress"><span style="width:${row.completed ? 100 : 40}%"></span></div>
          </div>
        </a>`;
    })
    .join('');
}

/* ------------------------------------------------------------------ */
/* Score trend                                                        */
/* ------------------------------------------------------------------ */

function renderTrend(attemptRows, quizMap) {
  const host = $('#chart-bars');
  const graded = attemptRows
    .filter((row) => row.status !== 'in_progress' && Number(row.max_score) > 0)
    .slice(0, 6)
    .reverse();

  if (!graded.length) {
    host.innerHTML = `<p class="tiny muted" style="margin:0">${
      signedIn ? 'No submitted paper yet — the chart fills after your first submit.' : 'Sign in to see your own score trend.'
    }</p>`;
    return;
  }

  const points = graded.map((row) => ({
    label: quizMap.get(row.quiz)?.title || `Attempt ${row.id}`,
    percent: Math.round((Number(row.score) / Number(row.max_score)) * 100)
  }));

  const last = points[points.length - 1];

  // One paper is not a trend. A lone bar of height 0% reads as a broken chart,
  // so show the single result as a figure and say what it will become.
  if (points.length === 1) {
    host.innerHTML = `
      <div class="chart-single">
        <span class="chart-single-score">${last.percent}%</span>
        <span class="chart-single-body">
          <strong>${esc(last.label)}</strong>
          <small>Your first submitted paper. Take another and each attempt gets its own bar here.</small>
        </span>
      </div>`;
    const singleBadge = $('#trend-badge');
    if (singleBadge) {
      singleBadge.hidden = false;
      singleBadge.textContent = `Latest ${last.percent}%`;
    }
    const singleNote = $('#trend-note');
    if (singleNote) singleNote.textContent = 'Across 1 submitted paper.';
    return;
  }

  const best = Math.max(...points.map((point) => point.percent));
  host.innerHTML = points
    .map(
      (point) => `
      <div class="chart-bar" title="${esc(point.label)}: ${point.percent}%">
        <span class="bar ${point.percent === best ? 'is-best' : ''}" style="height:${Math.max(
        4,
        Math.round((Math.min(100, Math.max(0, point.percent)) / 100) * 112)
      )}px"></span>
        <small>${point.percent}%</small>
      </div>`
    )
    .join('');

  const badge = $('#trend-badge');
  if (badge) {
    badge.hidden = false;
    badge.textContent = `Latest ${last.percent}%`;
  }
  const note = $('#trend-note');
  if (note) note.textContent = `Across ${points.length} submitted ${points.length === 1 ? 'paper' : 'papers'}, newest last.`;
}

/* ------------------------------------------------------------------ */
/* Upcoming tests                                                     */
/* ------------------------------------------------------------------ */

function renderUpcoming(quizRows) {
  const host = $('#upcoming-list');
  const now = Date.now();
  const upcoming = quizRows
    .filter((quiz) => quiz.opens_at && Date.parse(quiz.opens_at) > now)
    .sort((a, b) => Date.parse(a.opens_at) - Date.parse(b.opens_at))
    .slice(0, 3);

  if (!upcoming.length) {
    host.innerHTML = emptyState({
      title: 'Nothing scheduled',
      body: 'No paper has a future opening time right now. Open papers are on the tests page.',
      actionLabel: 'Open papers',
      actionHref: 'tests.html',
      iconName: 'file-text'
    });
    return;
  }

  host.innerHTML = upcoming
    .map(
      (quiz) => `
      <a class="upcoming-item" href="${quiz.has_access === false ? 'courses.html' : `test-player.html?test=${quiz.id}`}">
        <span class="upcoming-date">
          <strong>${new Date(quiz.opens_at).getDate()}</strong>
          <span>${new Date(quiz.opens_at).toLocaleDateString('en-IN', { month: 'short' })}</span>
        </span>
        <span class="upcoming-body">
          <strong>${esc(quiz.title)}</strong>
          <small>${quiz.question_count} questions · ${quiz.duration_minutes || 0} min · opens ${new Date(
            quiz.opens_at
          ).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}</small>
        </span>
        ${quiz.has_access === false ? '<span class="badge badge-paid">Enrol</span>' : '<span class="badge badge-new">Open</span>'}
      </a>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Notes                                                              */
/* ------------------------------------------------------------------ */

function noteCard(note) {
  return `
    <article class="note-preview">
      <div class="row-between">
        <h3>${esc(note.title || 'Untitled note')}</h3>
        <span class="tiny subtle">${note.updated_at ? shortDate(note.updated_at) : ''}</span>
      </div>
      <p>${esc(note.body || '')}</p>
      ${note.lesson_title ? `<small class="tiny subtle">${esc(note.lesson_title)}</small>` : ''}
    </article>`;
}

function renderNotes(noteRows) {
  const host = $('#notes-list');
  if (!signedIn) {
    host.innerHTML = signInPrompt('Sign in to keep notes', 'Notes are private to your account, so they only appear here once you are signed in.', 'note');
    return;
  }
  if (!noteRows.length) {
    host.innerHTML = emptyState({
      title: 'No notes yet',
      body: 'Write one with the button above — it is saved to your account, not just this tab.',
      iconName: 'note'
    });
    return;
  }
  host.innerHTML = noteRows.slice(0, 3).map(noteCard).join('');
}

/* ------------------------------------------------------------------ */
/* Sidebars                                                           */
/* ------------------------------------------------------------------ */

function renderBatches(courseRows) {
  const host = $('#batch-progress');
  if (!signedIn) {
    host.innerHTML = '<p class="tiny muted" style="margin:0">Sign in to see the batches on your account.</p>';
    return;
  }
  if (!courseRows.length) {
    host.innerHTML = '<p class="tiny muted" style="margin:0">No batch on your account yet. <a class="link" href="courses.html">Browse batches</a>.</p>';
    return;
  }
  host.innerHTML = courseRows
    .slice(0, 4)
    .map(
      (course) => `
      <a class="row-between tiny" href="course.html?slug=${encodeURIComponent(course.slug)}" style="gap:10px">
        <span class="truncate strong" style="max-width:70%;font-size:12px">${esc(course.title)}</span>
        <span class="subtle">${esc(course.pricing_mode === 'paid' ? money(course.price) : 'Free')}</span>
      </a>`
    )
    .join('');
}

function renderTasks(taskRows) {
  const host = $('#task-list');
  if (!signedIn) {
    host.innerHTML = '<p class="tiny muted" style="margin:0">Sign in to plan study tasks.</p>';
    return;
  }
  if (!taskRows.length) {
    host.innerHTML = '<p class="tiny muted" style="margin:0">No study task yet. Tasks you add in the API appear here.</p>';
    return;
  }
  host.innerHTML = taskRows
    .slice(0, 4)
    .map(
      (task) => `
      <div class="row-between tiny" style="gap:10px">
        <span class="truncate ${task.is_completed ? 'subtle' : 'strong'}" style="max-width:70%;font-size:12px">
          ${task.is_completed ? '✓ ' : ''}${esc(task.title)}
        </span>
        <span class="subtle">${task.due_at ? shortDate(task.due_at) : ''}</span>
      </div>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Note composer                                                      */
/* ------------------------------------------------------------------ */

function wireNoteModal() {
  const modal = $('#note-modal');
  const open = () => {
    if (!signedIn) {
      location.href = 'login.html?next=dashboard.html';
      return;
    }
    modal.classList.add('is-open');
    document.body.classList.add('is-locked');
    $('#note-heading')?.focus();
  };
  const close = () => {
    modal.classList.remove('is-open');
    document.body.classList.remove('is-locked');
  };

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-new-note]')) open();
    if (event.target.closest('[data-close-modal]') || event.target === modal) close();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('is-open')) close();
  });

  $('#note-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const error = $('#note-error');
    const button = form.querySelector('button[type="submit"]');
    const fields = new FormData(form);
    const title = String(fields.get('title') || '').trim();
    const body = String(fields.get('body') || '').trim();
    if (!title || !body) return;

    error.hidden = true;
    button.disabled = true;
    button.textContent = 'Saving…';
    try {
      const note = await request('/notes/', { method: 'POST', body: { title, body } });
      $('#notes-list').insertAdjacentHTML('afterbegin', noteCard(note));
      form.reset();
      close();
      toast('Note saved to your account.', 'success');
    } catch (err) {
      error.hidden = false;
      error.textContent = err.message || 'The note could not be saved.';
    } finally {
      button.disabled = false;
      button.textContent = 'Save note';
    }
  });
}

/* ------------------------------------------------------------------ */
/* Boot                                                               */
/* ------------------------------------------------------------------ */

async function boot() {
  renderGreeting();
  renderFigures({});
  wireNoteModal();

  // Personal endpoints are only asked when there is an account to ask about:
  // an anonymous request for them is not an empty answer, it is a 401.
  const personal = (path) => (signedIn ? settle(path) : Promise.resolve({ ok: false }));
  const [courses, progress, attempts, quizzes, notes, tasks] = await Promise.all([
    personal(`/courses/${apiQuery({ mine: 1, page_size: 20 })}`),
    personal(`/progress/${apiQuery({ page_size: 20 })}`),
    personal(`/quiz-attempts/${apiQuery({ page_size: 20 })}`),
    settle(`/quizzes/${apiQuery({ page_size: 60 })}`),
    personal(`/notes/${apiQuery({ page_size: 10 })}`),
    personal(`/study-tasks/${apiQuery({ page_size: 20 })}`)
  ]);

  const pick = (result, fallback = []) => (result.ok ? rows(result.payload) : fallback);
  const count = (result) =>
    result.ok && typeof result.payload?.count === 'number' ? result.payload.count : result.ok ? rows(result.payload).length : null;

  const courseRows = pick(courses);
  const progressRows = pick(progress);
  const attemptRows = pick(attempts);
  const quizRows = pick(quizzes);
  const noteRows = pick(notes);
  const taskRows = pick(tasks);

  renderFigures({
    courses: count(courses),
    progress: count(progress),
    attempts: count(attempts),
    notes: count(notes)
  });

  const lessonMap = new Map();
  if (signedIn && progressRows.length) {
    const lessons = await settle(`/lessons/${apiQuery({ page_size: 60 })}`);
    if (lessons.ok) rows(lessons.payload).forEach((lesson) => lessonMap.set(lesson.id, lesson));
  }
  renderContinue(progressRows, lessonMap);

  const quizMap = new Map(quizRows.map((quiz) => [quiz.id, quiz]));
  renderTrend(attemptRows, quizMap);
  renderUpcoming(quizRows);
  renderNotes(noteRows);
  renderBatches(courseRows);
  renderTasks(taskRows);

  // A signed-in account whose endpoints all failed is a real outage; say so.
  if (signedIn && [courses, progress, attempts].every((result) => !result.ok)) {
    block('#continue-list', errorState({ title: 'Your learning could not load', body: 'The API did not answer.' }));
  }
}

wireRetry();
boot();
