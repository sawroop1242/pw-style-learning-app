/**
 * Printed-style question paper.
 *
 * The paper renders in full, like a textbook exercise: numbered questions,
 * marks in the margin, options as A/B/C/D rows. State is held per question and
 * persisted to sessionStorage so a refresh does not lose an attempt.
 */

import { $, $$, esc, mmss, qsParam, clamp, storage } from './core.js';
import { mountSprite, icon, toast } from './ui.js';
import { EXAM_QUESTIONS, TESTS } from './data.js';

mountSprite();

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];

/* A card links here as ?test=<id>&duration=<minutes>; both are optional so the
   page still works when opened directly. */
const CHOSEN = TESTS.find((t) => String(t.id) === qsParam('test')) || null;
const ALLOWED_MINUTES = clamp(Number(qsParam('duration')) || CHOSEN?.duration || 180, 1, 240);
const DURATION_SECONDS = ALLOWED_MINUTES * 60;

const PAPER = EXAM_QUESTIONS.map((q, i) => ({ ...q, no: i + 1 }));
const SECTIONS = [...new Set(PAPER.map((q) => q.section))];

/* Group by section and renumber, so a paper never shows questions out of
   order when the API returns sections interleaved. */
{
  const ordered = SECTIONS.flatMap((section) => PAPER.filter((q) => q.section === section));
  PAPER.length = 0;
  PAPER.push(...ordered);
  PAPER.forEach((q, i) => { q.no = i + 1; });
}

const MAX_MARKS = PAPER.reduce((sum, q) => sum + Number(q.marks || 0), 0);

const SAVE_KEY = 'studyspace.attempt.preview';

/** questionId → { selected: number|null, marked: boolean, seconds: number } */
const state = new Map(
  PAPER.map((q) => [q.id, { selected: null, marked: false, seconds: 0 }])
);

const app = {
  remaining: DURATION_SECONDS,
  startedAt: Date.now(),
  submitted: false,
  current: 0
};

/* ------------------------------------------------------------------ */
/* Restore a previous attempt                                         */
/* ------------------------------------------------------------------ */

function restore() {
  const raw = storage.attempt;
  if (!raw || raw.duration !== DURATION_SECONDS) return;
  try {
    const saved = JSON.parse(raw);
    if (saved?.answers) {
      for (const [id, value] of Object.entries(saved.answers)) {
        const target = state.get(Number(id));
        if (target && value?.selected !== undefined) {
          target.selected = value.selected;
          target.marked = Boolean(value.marked);
        }
      }
      if (saved.startedAt) app.startedAt = Number(saved.startedAt);
      toast('Restored the attempt you had in progress.', 'info');
    }
  } catch {
    /* a corrupt entry is simply ignored */
  }
}

function persist() {
  if (app.submitted) return;
  const answers = {};
  for (const [id, value] of state) {
    if (value.selected !== null || value.marked) answers[id] = value;
  }
  storage.attempt = JSON.stringify({ duration: DURATION_SECONDS, startedAt: app.startedAt, answers });
}

/* ------------------------------------------------------------------ */
/* Render the paper                                                   */
/* ------------------------------------------------------------------ */

function renderPaper() {
  const body = $('#paper-body');

  body.innerHTML = SECTIONS.map((section) => {
    const questions = PAPER.filter((q) => q.section === section);
    const marks = questions.reduce((sum, q) => sum + Number(q.marks || 0), 0);

    return `
      <section class="paper-section">
        <h2>
          ${esc(section)}
          <small>Questions ${questions[0].no}–${questions[questions.length - 1].no} · ${marks} marks</small>
        </h2>
        ${questions.map(questionMarkup).join('')}
      </section>`;
  }).join('');

  $('#meta-count').textContent = PAPER.length;
  $('#meta-marks').textContent = MAX_MARKS;
  $('#meta-time').textContent = `${Math.round(DURATION_SECONDS / 60)} minutes`;
  // Reflect anything restored from sessionStorage.
  for (const q of PAPER) {
    const value = state.get(q.id);
    if (value.selected !== null) {
      const input = document.querySelector(`input[name="q-${q.id}"][value="${value.selected}"]`);
      if (input) input.checked = true;
    }
    if (value.marked) {
      const button = document.querySelector(`[data-mark="${q.id}"]`);
      if (button) {
        button.classList.add('is-on');
        button.querySelector('span').textContent = 'Marked for review';
      }
    }
  }

  $('#instruction-list').innerHTML = [
    `The paper has ${SECTIONS.length} sections. Answer every question; each carries the marks shown in the margin.`,
    'A wrong answer carries a negative mark. An unanswered question scores zero.',
    'Select one option per question. You can change an answer until you submit.',
    'The question map on the side shows what is answered, marked and still pending.'
  ].map((line) => `<li>${esc(line)}</li>`).join('');
}

function questionMarkup(q) {
  const mark = Number(q.marks || 0);
  const neg = Number(q.negative || 0);

  return `
    <article class="question" id="q-${q.id}" data-question="${q.id}" tabindex="-1">
      <div class="q-head">
        <span class="q-number">${q.no}.</span>
        <span class="q-marks">
          <span class="pos">+${mark}</span>${neg ? ` <span class="neg">−${neg}</span>` : ''}
          · ${esc(q.type === 'single' ? 'Single choice' : 'Multiple choice')}
        </span>
      </div>
      <p class="q-text" id="q-${q.id}-text">${esc(q.prompt)}</p>
      <div class="options" role="radiogroup" aria-labelledby="q-${q.id}-text">
        ${q.options.map(
          (text, i) => `
          <label class="option">
            <input type="radio" name="q-${q.id}" value="${i}" data-option="${q.id}">
            <span class="option-key">${LETTERS[i]}</span>
            <span class="option-text">${esc(text)}</span>
          </label>`
        ).join('')}
      </div>
      <div class="q-tools">
        <button class="q-tool" type="button" data-mark="${q.id}">
          ${icon('flag')} <span>Mark for review</span>
        </button>
        <button class="q-tool" type="button" data-clear="${q.id}">
          ${icon('refresh')} <span>Clear answer</span>
        </button>
      </div>
    </article>`;
}

/* ------------------------------------------------------------------ */
/* Palette                                                            */
/* ------------------------------------------------------------------ */

function statusOf(id) {
  const value = state.get(id);
  if (value.marked) return 'is-marked';
  if (value.selected !== null) return 'is-answered';
  return '';
}

function renderPalette() {
  const host = $('#palette');
  if (!host) return;

  host.innerHTML = PAPER.map(
    (q) => `<button class="pal-btn ${statusOf(q.id)} ${q.no - 1 === app.current ? 'is-current' : ''}"
              type="button" data-jump="${q.no - 1}"
              aria-label="Go to question ${q.no}">${q.no}</button>`
  ).join('');

  const answered = [...state.values()].filter((s) => s.selected !== null).length;
  const marked = [...state.values()].filter((s) => s.marked).length;

  const set = (sel, value) => {
    const node = $(sel);
    if (node) node.textContent = value;
  };
  set('#sum-answered', answered);
  set('#sum-unanswered', PAPER.length - answered);
  set('#sum-marked', marked);
  set('#modal-answered', answered);
  set('#modal-unanswered', PAPER.length - answered);
  set('#modal-marked', marked);
}

/* ------------------------------------------------------------------ */
/* Answering                                                          */
/* ------------------------------------------------------------------ */

$('#paper-body').addEventListener('change', (e) => {
  if (app.submitted) return;
  const input = e.target.closest('[data-option]');
  if (!input) return;

  const id = Number(input.dataset.option);
  const value = state.get(id);
  if (!value) return;

  value.selected = Number(input.value);
  persist();
  renderPalette();
  flashSaved();
});

$('#paper-body').addEventListener('click', (e) => {
  if (app.submitted) return;

  const mark = e.target.closest('[data-mark]');
  if (mark) {
    const id = Number(mark.dataset.mark);
    const value = state.get(id);
    value.marked = !value.marked;
    mark.classList.toggle('is-on', value.marked);
    mark.querySelector('span').textContent = value.marked ? 'Marked for review' : 'Mark for review';
    persist();
    renderPalette();
    flashSaved();
    return;
  }

  const clear = e.target.closest('[data-clear]');
  if (clear) {
    const id = Number(clear.dataset.clear);
    const value = state.get(id);
    value.selected = null;
    const input = document.querySelector(`input[name="q-${id}"]:checked`);
    if (input) input.checked = false;
    persist();
    renderPalette();
    flashSaved();
  }
});

/* Jump from the map */
$('#palette').addEventListener('click', (e) => {
  const btn = e.target.closest('[data-jump]');
  if (!btn) return;
  const index = Number(btn.dataset.jump);
  const q = PAPER[index];
  document.getElementById(`q-${q.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  app.current = index;
  renderPalette();
  closeMap();
});

let savedTimer;
function flashSaved() {
  const node = $('#autosave-state');
  if (!node) return;
  node.textContent = 'Saved';
  node.style.color = 'var(--success-600)';
  clearTimeout(savedTimer);
  savedTimer = setTimeout(() => {
    node.textContent = 'Answers save as you go';
    node.style.color = '';
  }, 1600);
}

/* ------------------------------------------------------------------ */
/* Timer                                                              */
/* ------------------------------------------------------------------ */

function startTimer() {
  const timer = $('#exam-timer');
  const value = $('#timer-value');

  const tick = () => {
    if (app.submitted) return;
    app.remaining = Math.max(0, DURATION_SECONDS - Math.floor((Date.now() - app.startedAt) / 1000));
    value.textContent = mmss(app.remaining);
    timer.classList.toggle('is-critical', app.remaining <= 300);

    if (app.remaining <= 0) {
      clearInterval(app.ticker);
      toast('Time is up. The paper was submitted automatically.', 'error', 6000);
      submitAttempt(true);
    }
  };

  timer.setAttribute('role', 'timer');
  timer.setAttribute('aria-live', 'off');
  app.ticker = setInterval(tick, 1000);
  tick();
}

/* ------------------------------------------------------------------ */
/* Submit                                                             */
/* ------------------------------------------------------------------ */

function openSubmit() {
  renderPalette();
  $('#submit-modal').classList.add('is-open');
  document.body.classList.add('is-locked');
  $('#confirm-submit').focus();
}

function closeSubmit() {
  $('#submit-modal').classList.remove('is-open');
  document.body.classList.remove('is-locked');
}

$('#submit-btn').addEventListener('click', openSubmit);
$('#submit-btn-foot').addEventListener('click', openSubmit);
$('#confirm-submit').addEventListener('click', () => submitAttempt(false));

document.addEventListener('click', (e) => {
  if (e.target.closest('[data-close-modal]')) closeSubmit();
  if (e.target.id === 'submit-modal') closeSubmit();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && $('#submit-modal').classList.contains('is-open')) closeSubmit();
});

function scoreAttempt() {
  let score = 0;
  let correct = 0;
  let wrong = 0;
  let skipped = 0;
  const bySection = new Map(SECTIONS.map((s) => [s, { scored: 0, max: 0, correct: 0, total: 0 }]));

  for (const q of PAPER) {
    const value = state.get(q.id);
    const bucket = bySection.get(q.section);
    const marks = Number(q.marks || 0);

    bucket.max += marks;
    bucket.total += 1;

    if (value.selected === null) {
      skipped += 1;
    } else if (value.selected === q.answer) {
      score += marks;
      correct += 1;
      bucket.scored += marks;
      bucket.correct += 1;
    } else {
      score -= Number(q.negative || 0);
      wrong += 1;
      bucket.scored -= Number(q.negative || 0);
    }
  }

  const attempted = correct + wrong;
  return {
    score: Math.max(0, Math.round(score * 100) / 100),
    correct,
    wrong,
    skipped,
    attempted,
    accuracy: attempted ? Math.round((correct / attempted) * 100) : 0,
    bySection
  };
}

function submitAttempt(auto) {
  if (app.submitted) return;
  app.submitted = true;
  clearInterval(app.ticker);

  const result = scoreAttempt();
  const secondsUsed = Math.min(DURATION_SECONDS, Math.floor((Date.now() - app.startedAt) / 1000));

  closeSubmit();
  persist();
  renderResult(result, secondsUsed, auto);
}

/* ------------------------------------------------------------------ */
/* Result                                                             */
/* ------------------------------------------------------------------ */

let lastResult = null;

function renderResult(result, secondsUsed, auto) {
  lastResult = result;

  $('#paper-view').hidden = true;
  $('#qmap').hidden = true;
  $('#qmap-toggle').hidden = true;
  $('#submit-btn').hidden = true;
  $('#result-view').hidden = false;

  $('#result-sub').textContent = auto
    ? 'Time ran out, so the paper was submitted automatically. Every question is reviewed below.'
    : 'Every question is reviewed below. Use the filter to see only the ones you got wrong.';

  const percent = MAX_MARKS ? Math.round((result.score / MAX_MARKS) * 1000) / 10 : 0;

  $('#score-rows').innerHTML = `
    <tr><th scope="row">Marks obtained</th><td>${result.score} <span class="muted" style="font-weight:400">out of ${MAX_MARKS}</span></td></tr>
    <tr><th scope="row">Percentage</th><td>${percent}%</td></tr>
    <tr><th scope="row">Correct · Incorrect · Unattempted</th><td>${result.correct} · ${result.wrong} · ${result.skipped}</td></tr>
    <tr><th scope="row">Time used</th><td>${mmss(secondsUsed)}</td></tr>`;

  $('#result-stats').innerHTML = [
    ['Accuracy', `${result.accuracy}%`],
    ['Attempted', `${result.attempted}/${PAPER.length}`],
    ['Section best', bestSection(result.bySection)],
    ['Marks lost', `${result.wrong} question${result.wrong === 1 ? '' : 's'}`]
  ].map(([label, value]) => `<div class="result-stat"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`).join('');

  $('#section-breakdown').innerHTML = [...result.bySection.entries()]
    .map(([section, data]) => {
      const pct = data.max ? clamp((data.scored / data.max) * 100, 0, 100) : 0;
      return `
        <div class="section-bar-row">
          <span>${esc(section)}</span>
          <div class="section-track"><i style="width:${pct}%"></i></div>
          <b>${round1(data.scored)} / ${data.max}</b>
        </div>`;
    })
    .join('');

  renderSolutions();

  $('#result-view').scrollIntoView({ block: 'start' });
  document.title = `${result.score}/${MAX_MARKS} — answer sheet · StudySpace`;
}

function bestSection(bySection) {
  let best = null;
  for (const [section, data] of bySection) {
    const pct = data.max ? data.scored / data.max : 0;
    if (!best || pct > best.pct) best = { section, pct };
  }
  return best ? best.section : '—';
}

const round1 = (value) => (Math.round(value * 10) / 10).toString();

function renderSolutions() {
  const onlyWrong = $('#only-wrong')?.checked;
  const host = $('#solutions');

  const rows = PAPER.filter((q) => {
    if (!onlyWrong) return true;
    const value = state.get(q.id);
    return value.selected !== q.answer;
  });

  if (!rows.length) {
    host.innerHTML = `
      <div class="empty-state" style="padding:24px">
        ${icon('check-circle')}
        <h3>Nothing to review</h3>
        <p>Every question was answered correctly.</p>
      </div>`;
    return;
  }

  host.innerHTML = rows.map((q) => {
    const value = state.get(q.id);
    const skipped = value.selected === null;
    const correct = !skipped && value.selected === q.answer;
    const status = correct ? 'Correct' : skipped ? 'Not attempted' : 'Incorrect';
    const markClass = correct ? 'ok' : skipped ? 'skip' : 'no';

    return `
      <article class="solution">
        <div class="solution-head">
          <strong>Q${q.no}. ${esc(q.section)}</strong>
          <span class="solution-mark ${markClass}">
            ${icon(correct ? 'check-circle' : skipped ? 'minus' : 'x-circle')} ${status}
          </span>
        </div>
        <p class="q-text" style="margin:0;font-size:var(--text-base)">${esc(q.prompt)}</p>
        <div class="options" style="gap:6px">
          ${q.options.map((text, i) => {
            const isCorrect = i === q.answer;
            const isChosen = !skipped && value.selected === i;
            const cls = isCorrect ? 'is-correct' : isChosen ? 'is-wrong' : '';
            return `<div class="solution-opt ${cls}">
              ${LETTERS[i]}. ${esc(text)}
              ${isChosen && !isCorrect ? ' · your answer' : isCorrect ? ' · correct answer' : ''}
            </div>`;
          }).join('')}
        </div>
        ${q.explanation ? `<p class="solution-explanation">${esc(q.explanation)}</p>` : ''}
      </article>`;
  }).join('');
}

$('#only-wrong')?.addEventListener('change', renderSolutions);

$('#retake-btn')?.addEventListener('click', () => {
  storage.attempt = null;
  location.reload();
});

/* ------------------------------------------------------------------ */
/* Question map (mobile)                                              */
/* ------------------------------------------------------------------ */

function openMap() {
  $('#qmap').classList.add('is-open');
  $('#qmap-toggle').setAttribute('aria-expanded', 'true');
}

function closeMap() {
  $('#qmap').classList.remove('is-open');
  $('#qmap-toggle').setAttribute('aria-expanded', 'false');
}

$('#qmap-toggle')?.addEventListener('click', () => {
  const open = $('#qmap').classList.contains('is-open');
  open ? closeMap() : openMap();
});

$('#qmap-close')?.addEventListener('click', closeMap);

/* Track which question is on screen */
function watchScroll() {
  if (!('IntersectionObserver' in window)) return;

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      app.current = Number(visible.target.dataset.questionIndex);
      renderPalette();
    },
    { rootMargin: '-15% 0px -60% 0px', threshold: [0.1, 0.5, 1] }
  );

  $$('.question').forEach((node, index) => {
    node.dataset.questionIndex = index;
    observer.observe(node);
  });
}

/* ------------------------------------------------------------------ */
/* Boot                                                               */
/* ------------------------------------------------------------------ */

const paperTitle = CHOSEN?.title || 'Practice question paper';
$('#exam-name').textContent = paperTitle;
$('#paper-title').textContent = paperTitle;
$('#print-btn')?.addEventListener('click', () => {
  if (typeof window.print === 'function') window.print();
});

$('#exam-sub').textContent = CHOSEN
  ? `${CHOSEN.exam} · ${CHOSEN.kind}`
  : `${PAPER.length} questions · ${ALLOWED_MINUTES} minutes`;
if (CHOSEN) document.title = `${CHOSEN.title} — StudySpace`;
$('#paper-sub').textContent = SECTIONS.join(' · ');

restore();
renderPaper();
renderPalette();
startTimer();
watchScroll();
persist();
