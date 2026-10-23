/** Test series listing with exam filters. */

import { $, esc, live, compact, countdown, shortDate } from './core.js';
import { mountChrome, testCard, emptyState, icon } from './ui.js';
import { TESTS } from './data.js';

mountChrome('tests');

const state = { exam: 'all', all: [] };

const FALLBACK_FIELDS = (quiz, index) => {
  const fixture = TESTS.find((t) => t.id === quiz.id) || TESTS[index] || TESTS[0];
  return {
    ...fixture,
    id: quiz.id ?? fixture.id,
    title: quiz.title || fixture.title,
    exam: fixture.exam,
    kind: fixture.kind,
    duration: quiz.duration_minutes || fixture.duration,
    questions: quiz.question_count ?? fixture.questions,
    attempts: fixture.attempts,
    startsAt: quiz.opens_at || fixture.startsAt,
    price: quiz.price ?? fixture.price,
    badge: fixture.badge
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
  state.all = rows.map(FALLBACK_FIELDS);
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

renderSteps();
load();
