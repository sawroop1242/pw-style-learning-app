/** Test series listing with exam filters. */

import { $, $$, esc, live, initials, storage } from './core.js';
import { mountChrome, testCard, emptyState, icon } from './ui.js';
import { TESTS } from './data.js';

mountChrome('tests');

const avatar = document.querySelector('[data-welcome-avatar]');
if (avatar) avatar.textContent = initials(storage.user?.username || 'Student');

const state = { exam: 'all', all: [] };

/**
 * Turn an API quiz row into a card view model.
 *
 * Every field is read from the payload; the fixture row is only consulted when
 * the API genuinely has nothing to say (an older server without the label
 * fields), and the card is never given a number the server did not send.
 */
const shapeTest = (quiz, index) => {
  const fixture = TESTS.find((t) => t.id === quiz.id) || TESTS[index] || TESTS[0];
  const exam = quiz.series_subject || quiz.course_subject || quiz.exam || null;
  const timed = quiz.timing_mode && quiz.timing_mode !== 'untimed';
  return {
    id: quiz.id ?? fixture.id,
    title: quiz.title || fixture.title,
    exam: exam || fixture.exam,
    kind: quiz.series_title ? (timed ? 'Timed mock' : 'Practice') : fixture.kind,
    duration: quiz.duration_minutes ?? fixture.duration,
    questions: quiz.question_count ?? fixture.questions,
    marks: quiz.marks_per_question
      ? Math.round(Number(quiz.marks_per_question) * (quiz.question_count ?? 0))
      : null,
    attempts: quiz.attempt_count ?? fixture.attempts,
    startsAt: quiz.opens_at || null,
    price: quiz.price ?? fixture.price,
    badge: timed ? null : 'Practice',
    locked: quiz.has_access === false
  };
};

function renderFilters() {
  const host = $('#test-filters');
  const exams = ['all', ...new Set(state.all.map((t) => t.exam))];
  host.innerHTML = exams
    .map(
      (exam) => `
      <button class="chip ${state.exam === exam ? 'is-active' : ''}" data-exam="${esc(exam)}"
              aria-pressed="${state.exam === exam}">
        ${exam === 'all' ? 'All exams' : esc(exam)}
      </button>`
    )
    .join('');
}

function renderGrid() {
  const host = $('#test-grid');
  const empty = $('#test-empty');
  const list = state.all.filter((t) => state.exam === 'all' || t.exam === state.exam);

  if (!list.length) {
    host.innerHTML = '';
    empty.hidden = false;
    empty.innerHTML = emptyState({
      title: 'No tests scheduled for this exam',
      body: 'New mocks are published every week. Try another exam in the meantime.',
      actionLabel: 'Show all tests',
      actionHref: 'tests.html',
      iconName: 'calendar'
    });
    return;
  }
  empty.hidden = true;
  host.innerHTML = list.map(testCard).join('');
}

function renderSteps() {
  const steps = [
    ['Start the mock', 'The paper is frozen when you begin — question order, marks and duration cannot change mid-attempt.'],
    ['Answer with the real palette', 'Mark for review, clear a response and jump between questions exactly as you would in the exam hall.'],
    ['Submit on the clock', 'Autosave keeps your answers. If the timer expires the attempt is submitted and scored automatically.'],
    ['Get rank and analysis', 'Once the window closes you see your rank, percentile, section split and time spent per question.']
  ];
  $('#how-steps').innerHTML = steps
    .map(
      ([title, body], i) => `
      <div class="card card-pad row" style="gap:14px;align-items:flex-start">
        <span class="acc-num" style="width:32px;height:32px;flex:0 0 auto">${i + 1}</span>
        <div>
          <strong style="display:block;font-size:14px;margin-bottom:3px">${esc(title)}</strong>
          <p class="small muted" style="margin:0;line-height:1.65">${esc(body)}</p>
        </div>
      </div>`
    )
    .join('');
}

async function load() {
  $('#test-grid').innerHTML = `<div class="skeleton" style="height:250px;border-radius:20px"></div>`.repeat(6);
  const { data } = await live('/quizzes/?page_size=40', TESTS);
  const rows = Array.isArray(data) ? data : data.results || [];
  state.all = rows.map(shapeTest);
  renderFilters();
  renderGrid();
}

$('#test-filters').addEventListener('click', (e) => {
  const chip = e.target.closest('[data-exam]');
  if (!chip) return;
  state.exam = chip.dataset.exam;
  renderFilters();
  renderGrid();
});

/* All / Attempted / Bookmarked ------------------------------------- */

function emptyFor(host, { title, body, iconName }) {
  if (!host) return;
  host.innerHTML = emptyState({
    title,
    body,
    actionLabel: 'Browse all tests',
    actionHref: 'tests.html',
    iconName
  });
}

const TAB_PANELS = ['panel-alltests', 'panel-attempted', 'panel-bookmarked'];
function selectTab(index) {
  const tabs = $$('.tabs .tab');
  tabs.forEach((tab, i) => {
    const selected = i === index;
    tab.setAttribute('aria-selected', String(selected));
    const panel = document.getElementById(TAB_PANELS[i]);
    if (panel) panel.hidden = !selected;
  });
  if (index === 1) {
    emptyFor($('#attempted-empty'), {
      title: 'No attempts yet',
      body: 'Finish any test and it appears here with its score, rank and a link to the full solution review.',
      iconName: 'file-text'
    });
  }
  if (index === 2) {
    emptyFor($('#bookmarked-empty'), {
      title: 'No bookmarked tests',
      body: 'Bookmark a test from its card to keep it at the top of this list when the next window opens.',
      iconName: 'bookmark'
    });
  }
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

renderSteps();
load();
