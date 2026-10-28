/**
 * Test series listing.
 *
 * One API read (`/quizzes/`), plus the caller's own attempts when signed in.
 * Filters are built from the subjects the server actually returned, so a chip
 * can never point at an exam with no papers behind it.
 */

import { $, $$, esc, getJson, rows, initials, storage, isSignedIn, adaptTest } from './core.js';
import { mountChrome, testCard, emptyState, errorState, icon, wireRetry } from './ui.js';
import { HOW_IT_WORKS } from './content.js';

mountChrome('tests');

const avatar = document.querySelector('[data-welcome-avatar]');
if (avatar) avatar.textContent = initials(storage.user?.username || 'Student').slice(0, 1);

const state = { subject: 'all', all: [], attempts: [], loaded: false };

/* ------------------------------------------------------------------ */
/* Filters                                                            */
/* ------------------------------------------------------------------ */

function renderFilters() {
  const host = $('#test-filters');
  const subjects = ['all', ...new Set(state.all.map((t) => t.subject).filter(Boolean))];
  host.innerHTML = subjects
    .map(
      (subject) => `
      <button class="chip ${state.subject === subject ? 'is-active' : ''}" data-exam="${esc(subject)}"
              aria-pressed="${state.subject === subject}">
        ${subject === 'all' ? 'All papers' : esc(subject)}
      </button>`
    )
    .join('');
}

function renderGrid() {
  const host = $('#test-grid');
  const empty = $('#test-empty');
  const list = state.all.filter((t) => state.subject === 'all' || t.subject === state.subject);

  if (!list.length) {
    host.innerHTML = '';
    empty.hidden = false;
    empty.innerHTML = emptyState({
      title: state.all.length ? 'No papers for this subject yet' : 'No tests published yet',
      body: state.all.length
        ? 'Pick another subject, or check back once the next paper is published.'
        : 'A published test appears here immediately, with its duration and marking scheme.',
      actionLabel: state.all.length ? 'Show all papers' : 'Browse batches',
      actionHref: state.all.length ? 'tests.html' : 'courses.html',
      iconName: 'file-text'
    });
    return;
  }
  empty.hidden = true;
  host.innerHTML = list.map(testCard).join('');
}

/* ------------------------------------------------------------------ */
/* Attempt history (signed in only — a guest's history is on the device) */
/* ------------------------------------------------------------------ */

const STATUS_LABEL = {
  in_progress: 'In progress',
  submitted: 'Submitted',
  expired: 'Time expired'
};

function renderAttempts() {
  const host = $('#attempted-empty');
  if (!host) return;

  if (!isSignedIn()) {
    host.innerHTML = emptyState({
      title: 'Sign in to keep your attempt history',
      body: 'You can sit any open paper without an account. Signing in stores the attempt on your profile so it survives a cleared browser.',
      actionLabel: 'Sign in',
      actionHref: 'login.html?next=tests.html',
      iconName: 'user'
    });
    return;
  }

  if (!state.attempts.length) {
    host.innerHTML = emptyState({
      title: 'No attempts yet',
      body: 'Finish a paper and it appears here with its score and a link to the review.',
      actionLabel: 'Browse papers',
      actionHref: 'tests.html',
      iconName: 'file-text'
    });
    return;
  }

  host.innerHTML = `
    <div class="stack" style="gap:10px">
      ${state.attempts
        .map(
          (attempt) => `
        <a class="continue-card" href="test-player.html?test=${attempt.quiz}&attempt=${attempt.id}">
          <span class="continue-thumb">${icon('file-text')}</span>
          <div class="continue-body">
            <h3>${esc(attempt.quiz_title || `Test #${attempt.quiz}`)}</h3>
            <small class="tiny subtle">${esc(STATUS_LABEL[attempt.status] || attempt.status)} · started ${esc(
              new Date(attempt.started_at).toLocaleString('en-IN')
            )}</small>
            <div class="continue-meta">
              <span>${
                attempt.score === null || attempt.score === undefined
                  ? 'Not scored yet'
                  : `Score ${Number(attempt.score)}${attempt.max_score ? ` / ${Number(attempt.max_score)}` : ''}`
              }</span>
              <span class="row" style="gap:4px;color:var(--violet-600);font-weight:700">
                Open ${icon('arrow-right')}
              </span>
            </div>
          </div>
        </a>`
        )
        .join('')}
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Boot                                                              */
/* ------------------------------------------------------------------ */

async function load() {
  const grid = $('#test-grid');
  grid.innerHTML = `<div class="skeleton" style="height:250px;border-radius:20px"></div>`.repeat(6);
  try {
    const payload = await getJson('/quizzes/?page_size=60');
    state.all = rows(payload).map(adaptTest);
    state.loaded = true;
  } catch {
    grid.innerHTML = '';
    $('#test-empty').hidden = false;
    $('#test-empty').innerHTML = errorState({ title: 'Tests unavailable' });
    return;
  }
  renderFilters();
  renderGrid();
  if (isSignedIn()) await loadAttempts();
  renderAttempts();
}

async function loadAttempts() {
  try {
    const payload = await getJson('/quiz-attempts/?page_size=50');
    const list = rows(payload);
    const quizzes = new Map(state.all.map((t) => [t.id, t.title]));
    state.attempts = list.map((attempt) => ({
      ...attempt,
      quiz_title: quizzes.get(attempt.quiz) || attempt.quiz_title
    }));
    // The list endpoint returns the attempt without the quiz title; resolve the
    // ones we do not have a card for in a single extra read.
    const missing = [...new Set(state.attempts.filter((a) => !a.quiz_title).map((a) => a.quiz))];
    if (missing.length) {
      const extra = await getJson('/quizzes/?page_size=60');
      for (const quiz of rows(extra)) quizzes.set(quiz.id, quiz.title);
      state.attempts.forEach((attempt) => {
        attempt.quiz_title = attempt.quiz_title || quizzes.get(attempt.quiz);
      });
    }
  } catch {
    state.attempts = [];
  }
}

$('#test-filters').addEventListener('click', (e) => {
  const chip = e.target.closest('[data-exam]');
  if (!chip) return;
  state.subject = chip.dataset.exam;
  renderFilters();
  renderGrid();
});

/* Tabs ------------------------------------------------------------- */

const TAB_PANELS = ['panel-alltests', 'panel-attempted', 'panel-open'];
function selectTab(index) {
  const tabs = $$('.tabs .tab');
  tabs.forEach((tab, i) => {
    const selected = i === index;
    tab.setAttribute('aria-selected', String(selected));
    const panel = document.getElementById(TAB_PANELS[i]);
    if (panel) panel.hidden = !selected;
  });
  if (index === 1) renderAttempts();
  if (index === 2) renderSuggestions();
}

/**
 * The third tab was "Bookmarked" with no way to bookmark a test. It now shows
 * the papers that are open but not yet attempted — a real, derivable list.
 */
function renderSuggestions() {
  const host = $('#open-list');
  if (!host) return;
  const done = new Set(state.attempts.map((a) => a.quiz));
  const open = state.all.filter((t) => !t.locked && !done.has(t.id));
  if (!open.length) {
    host.innerHTML = emptyState({
      title: 'Nothing outstanding',
      body: 'You have attempted every open paper, or no paper is open right now.',
      actionLabel: 'All papers',
      actionHref: 'tests.html',
      iconName: 'check-circle'
    });
    return;
  }
  host.innerHTML = `<div class="stack" style="gap:10px">${open.map(testCard).join('')}</div>`;
}

$$('.tabs .tab').forEach((tab, i) => {
  tab.addEventListener('click', () => selectTab(i));
  tab.addEventListener('keydown', (e) => {
    const tabs = $$('.tabs .tab');
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const next = (i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    selectTab(next);
  });
});
if (location.hash === '#attempted') selectTab(1);

function renderSteps() {
  $('#how-steps').innerHTML = HOW_IT_WORKS.map(
    ([title, body], i) => `
      <div class="card card-pad row" style="gap:14px;align-items:flex-start">
        <span class="acc-num" style="width:32px;height:32px;flex:0 0 auto">${i + 1}</span>
        <div>
          <strong style="display:block;font-size:14px;margin-bottom:3px">${esc(title)}</strong>
          <p class="small muted" style="margin:0;line-height:1.65">${esc(body)}</p>
        </div>
      </div>`
  ).join('');
}

renderSteps();
wireRetry();
load();
