/**
 * Exam interface.
 *
 * Full attempt lifecycle: question palette, per-question state machine,
 * countdown, autosave, submit confirmation, server-style scoring and a
 * solution review. Everything is computed locally from the bundled paper so
 * the static preview behaves exactly like the product, with the same status
 * vocabulary the API uses.
 */

import { $, $$, esc, mmss, qsParam, clamp } from './core.js';
import { mountSprite, icon, toast } from './ui.js';
import { EXAM_QUESTIONS } from './data.js';

mountSprite();

const DURATION_SECONDS = Number(qsParam('duration') || 180) * 60;
const PAPER = EXAM_QUESTIONS;
const LETTERS = ['A', 'B', 'C', 'D', 'E'];

/** not_visited → not_answered → answered, with an independent `marked` flag. */
const answerState = new Map(
  PAPER.map((q) => [q.id, { selected: null, visited: false, marked: false, seconds: 0 }])
);

const app = {
  index: 0,
  remaining: DURATION_SECONDS,
  ticker: null,
  startedAt: Date.now(),
  submitted: false
};

/* ------------------------------------------------------------------ */
/* Timer                                                              */
/* ------------------------------------------------------------------ */

function startTimer() {
  const timerEl = $('#exam-timer');
  const valueEl = $('#timer-value');

  const tick = () => {
    if (app.submitted) return;
    app.remaining = Math.max(0, DURATION_SECONDS - Math.floor((Date.now() - app.startedAt) / 1000));
    valueEl.textContent = mmss(app.remaining);
    timerEl.classList.toggle('is-critical', app.remaining <= 300);

    if (app.remaining <= 0) {
      clearInterval(app.ticker);
      toast('Time is up. Your attempt was submitted automatically.', 'error', 6000);
      submitAttempt(true);
    }
  };

  timerEl.setAttribute('aria-live', 'off');
  app.ticker = setInterval(tick, 1000);
  tick();

  // Attribute time spent to the question currently on screen.
  app.secondsTicker = setInterval(() => {
    if (!app.submitted) {
      const state = answerState.get(PAPER[app.index].id);
      state.seconds += 1;
    }
  }, 1000);
}

/* ------------------------------------------------------------------ */
/* Rendering                                                          */
/* ------------------------------------------------------------------ */

function statusOf(q) {
  const state = answerState.get(q.id);
  if (state.marked) return 'is-marked';
  if (state.selected !== null) return 'is-answered';
  if (state.visited) return 'is-not-answered';
  return '';
}

function renderQuestion() {
  const q = PAPER[app.index];
  const state = answerState.get(q.id);
  state.visited = true;

  $('#q-index').textContent = app.index + 1;
  $('#q-of').textContent = app.index + 1;
  $('#q-total').textContent = PAPER.length;
  $('#q-type').textContent = q.type === 'single' ? 'Single choice' : 'Multiple choice';
  $('#q-marks').textContent = q.marks;
  $('#q-neg').textContent = q.negative;
  $('#q-section').textContent = q.section;
  $('#question-text').textContent = q.prompt;

  $('#options').innerHTML = q.options
    .map(
      (text, i) => `
      <label class="option">
        <input type="radio" name="option" value="${i}" ${state.selected === i ? 'checked' : ''}>
        <span class="option-key">${LETTERS[i]}</span>
        <span class="option-text">${esc(text)}</span>
      </label>`
    )
    .join('');


  $('#mark-btn').classList.toggle('btn-soft', state.marked);
  $('#mark-btn').innerHTML = `<svg><use href="#i-flag"/></svg> ${state.marked ? 'Marked for review' : 'Mark for review'}`;

  $('#prev-btn').disabled = app.index === 0;
  $('#next-btn').innerHTML =
    app.index === PAPER.length - 1
      ? 'Review <svg><use href="#i-check"/></svg>'
      : 'Save &amp; next <svg><use href="#i-arrow-right"/></svg>';

  renderPalette();
  updateSummary();
  $('#question-text').scrollIntoView({ block: 'nearest' });
}

function renderPalette() {
  const host = $('#palette');
  host.innerHTML = PAPER.map((q, i) => {
    const cls = statusOf(q);
    const current = i === app.index ? 'is-current' : '';
    return `<button class="pal-btn ${cls} ${current}" data-jump="${i}"
              aria-label="Question ${i + 1}" ${current ? 'aria-current="true"' : ''}>${i + 1}</button>`;
  }).join('');
}

function updateSummary() {
  const values = [...answerState.values()];
  const answered = values.filter((s) => s.selected !== null).length;
  const marked = values.filter((s) => s.marked).length;
  const unvisited = values.filter((s) => !s.visited).length;
  const unanswered = PAPER.length - answered;

  const set = (id, value) => {
    const node = $(id);
    if (node) node.textContent = value;
  };
  set('#sum-answered', answered);
  set('#sum-unanswered', unanswered);
  set('#sum-marked', marked);
  set('#sum-unvisited', unvisited);

  // Submit modal mirrors
  set('#m-answered', answered);
  set('#m-unanswered', unanswered);
  set('#m-marked', marked);
  set('#m-unvisited', unvisited);

  const warn = $('#m-warning');
  if (warn) {
    warn.textContent =
      unanswered > 0
        ? `You still have ${unanswered} unanswered question${unanswered === 1 ? '' : 's'}.`
        : 'All questions answered. You are ready to submit.';
  }
}

function flashSaved() {
  const el = $('#autosave-state');
  if (!el) return;
  el.textContent = 'Saved just now';
  el.style.color = 'var(--success-600)';
  clearTimeout(flashSaved._t);
  flashSaved._t = setTimeout(() => {
    el.textContent = 'Answers save automatically';
    el.style.color = '';
  }, 1800);
}

/* ------------------------------------------------------------------ */
/* Navigation                                                         */
/* ------------------------------------------------------------------ */

function goTo(index) {
  app.index = clamp(index, 0, PAPER.length - 1);
  renderQuestion();
}

$('#palette').addEventListener('click', (e) => {
  const btn = e.target.closest('[data-jump]');
  if (!btn) return;
  goTo(Number(btn.dataset.jump));
});

$('#next-btn').addEventListener('click', () => {
  const state = answerState.get(PAPER[app.index].id);
  if (state.selected !== null) flashSaved();
  if (app.index === PAPER.length - 1) {
    openModal('#submit-modal');
    updateSummary();
    return;
  }
  goTo(app.index + 1);
});

$('#prev-btn').addEventListener('click', () => goTo(app.index - 1));

$('#mark-btn').addEventListener('click', () => {
  const state = answerState.get(PAPER[app.index].id);
  state.marked = !state.marked;
  renderQuestion();
});

$('#clear-btn').addEventListener('click', () => {
  const state = answerState.get(PAPER[app.index].id);
  state.selected = null;
  renderQuestion();
  flashSaved();
});

document.addEventListener('keydown', (e) => {
  if (app.submitted || /input|textarea|select/i.test(document.activeElement.tagName)) return;
  if (e.key === 'ArrowRight') goTo(app.index + 1);
  if (e.key === 'ArrowLeft') goTo(app.index - 1);
  if (['1', '2', '3', '4'].includes(e.key)) {
    const idx = Number(e.key) - 1;
    const q = PAPER[app.index];
    if (idx < q.options.length) {
      answerState.get(q.id).selected = idx;
      renderQuestion();
      flashSaved();
    }
  }
});

/* ------------------------------------------------------------------ */
/* Modals                                                             */
/* ------------------------------------------------------------------ */

function openModal(selector) {
  const modal = $(selector);
  modal.classList.add('is-open');
  document.body.classList.add('is-locked');
  modal.querySelector('button, [tabindex]')?.focus();
}

function closeModal(modal) {
  modal.classList.remove('is-open');
  document.body.classList.remove('is-locked');
}

document.addEventListener('click', (e) => {
  const modal = e.target.closest('.modal');
  if (e.target.closest('[data-close-modal]')) {
    closeModal(modal);
  } else if (e.target === modal) {
    closeModal(modal);
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') $$('.modal.is-open').forEach(closeModal);
});

$('#pause-btn').addEventListener('click', () => openModal('#info-modal'));
$('#submit-btn').addEventListener('click', () => {
  updateSummary();
  openModal('#submit-modal');
});
$('#confirm-submit').addEventListener('click', () => submitAttempt(false));

/* A single delegated listener — re-binding inside renderQuestion() would
   leave stale handlers bound to earlier questions' state objects. */
$('#options').addEventListener('change', (e) => {
  const input = e.target.closest('input[name="option"]');
  if (!input || app.submitted) return;
  const state = answerState.get(PAPER[app.index].id);
  state.selected = Number(input.value);
  state.visited = true;
  renderPalette();
  updateSummary();
  flashSaved();
});

/* ------------------------------------------------------------------ */
/* Scoring                                                            */
/* ------------------------------------------------------------------ */

function scoreAttempt() {
  let score = 0;
  let max = 0;
  let correct = 0;
  let wrong = 0;
  let skipped = 0;
  const sections = new Map();

  for (const q of PAPER) {
    const state = answerState.get(q.id);
    max += q.marks;

    if (!sections.has(q.section)) {
      sections.set(q.section, { name: q.section, correct: 0, wrong: 0, skipped: 0, score: 0, max: 0 });
    }
    const bucket = sections.get(q.section);
    bucket.max += q.marks;

    if (state.selected === null) {
      skipped += 1;
      bucket.skipped += 1;
      continue;
    }
    if (state.selected === q.answer) {
      score += q.marks;
      correct += 1;
      bucket.correct += 1;
      bucket.score += q.marks;
    } else {
      score -= q.negative;
      wrong += 1;
      bucket.wrong += 1;
      bucket.score -= q.negative;
    }
  }

  const attempted = correct + wrong;
  return {
    score: Math.max(0, score),
    max,
    correct,
    wrong,
    skipped,
    attempted,
    accuracy: attempted ? Math.round((correct / attempted) * 100) : 0,
    sections: [...sections.values()]
  };
}

function submitAttempt(auto) {
  if (app.submitted) return;
  app.submitted = true;
  clearInterval(app.ticker);
  clearInterval(app.secondsTicker);
  $$('.modal.is-open').forEach(closeModal);

  const result = scoreAttempt();
  const timeSpent = DURATION_SECONDS - app.remaining;

  $('#exam-mode').hidden = true;
  $('#result-mode').hidden = false;
  window.scrollTo({ top: 0, behavior: 'instant' });

  renderResult(result, timeSpent);
  if (auto) toast('Attempt submitted automatically at the deadline.', 'info', 5000);
}

/* ------------------------------------------------------------------ */
/* Result                                                             */
/* ------------------------------------------------------------------ */

function renderResult(result, timeSpent) {
  const pct = result.max ? result.score / result.max : 0;
  const circumference = 2 * Math.PI * 70;

  $('#score-circle').style.strokeDasharray = String(circumference);
  $('#score-circle').style.strokeDashoffset = String(circumference);
  $('#score-value').textContent = result.score;
  $('#score-max').textContent = result.max;

  requestAnimationFrame(() => {
    $('#score-circle').style.strokeDashoffset = String(circumference * (1 - pct));
  });

  $('#result-summary').textContent =
    `You answered ${result.attempted} of ${PAPER.length} questions in ${mmss(timeSpent)}.`;
  $('#stat-correct').textContent = result.correct;
  $('#stat-wrong').textContent = result.wrong;
  $('#stat-skipped').textContent = result.skipped;
  $('#stat-accuracy').textContent = `${result.accuracy}%`;

  // Rank is derived for the demo; the product computes it from all attempts.
  const percentile = clamp(35 + pct * 62, 12, 99.4);
  const rank = Math.max(1, Math.round((100 - percentile) * 32));
  $('#stat-percentile').textContent = `${percentile.toFixed(1)}`;
  $('#stat-rank').textContent = `#${rank}`;
  $('#stat-time').textContent = mmss(timeSpent);

  renderSections(result);
  renderTimeBreakdown();
  renderSolutions();
}

function renderSections(result) {
  $('#section-breakdown').innerHTML = result.sections
    .map((s) => {
      const pct = s.max ? Math.round((Math.max(0, s.score) / s.max) * 100) : 0;
      return `
        <div class="section-row">
          <div>
            <div class="sr-name">${esc(s.name)}</div>
            <div class="progress" style="margin-top:6px;height:5px"><span style="width:${pct}%"></span></div>
          </div>
          <div class="sr-score">${Math.max(0, s.score)} / ${s.max}</div>
          <div class="sr-pct" style="color:${pct >= 60 ? 'var(--success-600)' : pct >= 35 ? 'var(--amber-600)' : 'var(--danger-600)'}">${pct}%</div>
        </div>`;
    })
    .join('');
}

function renderTimeBreakdown() {
  const rows = PAPER.map((q) => ({ q, seconds: answerState.get(q.id).seconds }))
    .sort((a, b) => b.seconds - a.seconds)
    .slice(0, 5);

  const worst = rows[0]?.seconds || 1;

  $('#time-breakdown').innerHTML = rows
    .map(({ q, seconds }) => {
      const width = Math.max(6, Math.round((seconds / worst) * 100));
      const slow = seconds > 90;
      return `
        <div>
          <div class="row-between tiny" style="margin-bottom:4px">
            <span class="truncate" style="max-width:70%">Q${PAPER.indexOf(q) + 1} · ${esc(q.section)}</span>
            <strong style="color:${slow ? 'var(--danger-600)' : 'var(--text-muted)'}">${mmss(seconds)}</strong>
          </div>
          <div class="progress" style="height:5px">
            <span style="width:${width}%;background:${slow ? 'var(--danger-500)' : 'var(--grad-brand)'}"></span>
          </div>
        </div>`;
    })
    .join('');
}

function renderSolutions() {
  const onlyWrong = $('#only-wrong')?.checked;
  const items = PAPER.filter((q) => {
    if (!onlyWrong) return true;
    const state = answerState.get(q.id);
    return state.selected === null || state.selected !== q.answer;
  });

  $('#solutions').innerHTML = items
    .map((q) => {
      const state = answerState.get(q.id);
      const correct = state.selected === q.answer;
      const skipped = state.selected === null;
      const statusClass = correct ? 'ok' : skipped ? 'skip' : 'no';
      const statusIcon = correct ? 'check' : skipped ? 'minus' : 'x';

      return `
        <article class="solution-item">
          <div class="solution-head">
            <span class="solution-mark ${statusClass}">${icon(statusIcon)}</span>
            <strong style="font-size:13px;flex:1">Q${PAPER.indexOf(q) + 1} · ${esc(q.section)}</strong>
            <span class="tiny ${correct ? '' : skipped ? 'subtle' : ''}" style="color:${correct ? 'var(--success-600)' : skipped ? 'var(--text-subtle)' : 'var(--danger-600)'};font-weight:700">
              ${correct ? `+${q.marks}` : skipped ? '0' : `−${q.negative}`}
            </span>
          </div>
          <div class="solution-body">
            <p style="font-size:13px;line-height:1.65;color:var(--text);margin:0">${esc(q.prompt)}</p>
            ${q.options
              .map((text, i) => {
                const isCorrect = i === q.answer;
                const isChosen = i === state.selected;
                const cls = isCorrect ? 'is-correct' : isChosen ? 'is-wrong' : '';
                return `<div class="solution-opt ${cls}">${LETTERS[i]}. ${esc(text)}</div>`;
              })
              .join('')}
            <div class="solution-exp"><strong>Why:</strong> ${esc(q.explanation)}</div>
          </div>
        </article>`;
    })
    .join('');

  if (!items.length) {
    $('#solutions').innerHTML = `
      <div class="empty-state">
        ${icon('check-circle')}
        <h3>Nothing to review</h3>
        <p>Every question was answered correctly. Try a harder paper next.</p>
      </div>`;
  }
}

$('#only-wrong')?.addEventListener('change', renderSolutions);

/* ------------------------------------------------------------------ */
/* Retake                                                             */
/* ------------------------------------------------------------------ */

$('#retake-btn')?.addEventListener('click', () => {
  location.reload();
});

/* ------------------------------------------------------------------ */
/* Boot                                                               */
/* ------------------------------------------------------------------ */

const testName = qsParam('test');
if (testName) {
  $('#exam-name').textContent = `JEE Main Full Mock #${testName}`;
}
$('#exam-sub').textContent = `Section A · ${PAPER.length} questions · ${mmss(DURATION_SECONDS)}`;

renderQuestion();
startTimer();
