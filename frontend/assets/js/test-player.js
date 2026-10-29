/**
 * Exam window.
 *
 * Flow: instructions → test window → answer sheet. The paper comes from the
 * API and the attempt is created on the server, so this page has no sample
 * paper to fall back to — if the paper cannot be loaded it says so.
 *
 * An anonymous visitor can sit an open paper: `/quizzes/start/` returns a
 * `guest_token` once, which is kept on this device and sent back as
 * `X-Attempt-Token` for autosave, submit and the result. Signing in is never
 * required to attempt a test.
 */

import { $, $$, esc, qsParam, clamp, storage, request, isSignedIn } from './core.js';
import { mountSprite, icon, toast } from './ui.js';

mountSprite();

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];
const SAVE_KEY_NOTE = 'Saved just now';

/* ------------------------------------------------------------------ */
/* State                                                              */
/* ------------------------------------------------------------------ */

const requestedTest = qsParam('test');
const requestedAttempt = qsParam('attempt');

const state = {
  mode: 'intro',            // intro | exam | result
  ready: false,             // true once the API supplied the paper
  testId: requestedTest || null,          // identity for saved attempts and reloads
  apiId: /^\d+$/.test(requestedTest || '') ? requestedTest : null,   // only a numeric id can be a live quiz
  test: null,               // { id, title, exam, kind, duration, instructions }
  questions: [],            // normalised questions
  sections: [],             // [{ name, questions }]
  answers: new Map(),       // questionId → choiceId
  marked: new Set(),        // questionIds
  visited: new Set(),
  current: 0,
  attemptId: null,
  guestToken: null,         // issued once by /quizzes/start/ for a guest attempt
  deadline: null,           // epoch ms
  startedAt: null,
  durationMinutes: 180,
  submitted: false,
  result: null,
  loadError: null,
  released: true,
  paused: false,
  pauseStartedAt: null,
  questionMs: new Map(),     // questionId → accumulated ms on screen
  activeId: null,            // the question the clock is currently running for
  activeSince: null,         // ms timestamp that question went live
  reports: new Map()         // questionId → reason text
};

let ticker = null;
let warned = false;

/* ------------------------------------------------------------------ */
/* Small helpers                                                      */
/* ------------------------------------------------------------------ */

const pad = (n) => String(n).padStart(2, '0');

function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`;
}

/** Always HH:MM:SS — the exam clock never drops the hour field. */
function clockParts(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return {
    h: pad(Math.floor(s / 3600)),
    m: pad(Math.floor((s % 3600) / 60)),
    s: pad(s % 60)
  };
}

/** mm:ss for the per-question timer. */
function shortClock(ms) {
  const total = Math.max(0, Math.floor(ms / 1000));
  return `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;
}

const setText = (selector, value) => {
  const node = $(selector);
  if (node) node.textContent = value;
};

function minDuration(value) {
  return clamp(Number(value) || 180, 1, 300);
}

/* ------------------------------------------------------------------ */
/* Paper sources                                                      */
/* ------------------------------------------------------------------ */

function apiQuestion(question, quiz) {
  // A paper sets marks per question as a default; a single question may
  // override it. Both arrive as decimal strings, so parse before formatting.
  const marks = question.marks ?? quiz.marks_per_question ?? 0;
  const negative = question.negative_marks ?? quiz.negative_marks_per_wrong ?? 0;
  return {
    id: question.id,
    section: question.topic || 'All questions',
    prompt: question.prompt,
    options: (question.choices || []).map((choice) => ({ id: choice.id, text: choice.text })),
    marks: Number(marks),
    negative: Number(negative),
    type: question.question_type || 'single_choice',
    explanation: question.explanation || ''
  };
}

/** Order the API questions to match the attempt's frozen question order. */
function orderQuestions(questions, order) {
  if (!Array.isArray(order) || !order.length) return questions;
  const byId = new Map(questions.map((q) => [q.id, q]));
  const ordered = order.map((id) => byId.get(id)).filter(Boolean);
  return ordered.length ? ordered : questions;
}

function groupSections(questions) {
  const order = [];
  const bucket = new Map();

  for (const question of questions) {
    if (!bucket.has(question.section)) {
      bucket.set(question.section, []);
      order.push(question.section);
    }
    bucket.get(question.section).push(question);
  }

  return order.map((name) => ({ name, questions: bucket.get(name) }));
}

/* ------------------------------------------------------------------ */
/* Saved attempt                                                      */
/* ------------------------------------------------------------------ */

function readSaved() {
  const raw = storage.attempt;
  if (!raw) return null;
  try {
    const saved = JSON.parse(raw);
    if (!saved || String(saved.testId) !== String(state.testId)) return null;
    if (!Array.isArray(saved.questionIds)) return null;
    return saved;
  } catch {
    return null;
  }
}

function persist() {
  if (state.mode === 'result') {
    storage.attempt = null;
    return;
  }
  storage.attempt = JSON.stringify({
    testId: state.testId,
    attemptId: state.attemptId,
    startedAt: state.startedAt,
    deadline: state.deadline,
    current: state.current,
    questionIds: state.questions.map((q) => q.id),
    answers: Object.fromEntries(state.answers),
    marked: [...state.marked],
    visited: [...state.visited],
    questionMs: Object.fromEntries(state.questionMs),
    reports: Object.fromEntries(state.reports)
  });
}

function applySaved(saved) {
  state.attemptId = saved.attemptId ?? null;
  state.startedAt = saved.startedAt ?? Date.now();
  state.deadline = saved.deadline ?? state.startedAt + state.durationMinutes * 60000;
  state.current = clamp(Number(saved.current) || 0, 0, Math.max(0, state.questions.length - 1));

  for (const [id, choice] of Object.entries(saved.answers || {})) {
    const numeric = Number(id);
    if (state.questions.some((q) => q.id === numeric)) state.answers.set(numeric, choice);
  }
  for (const id of saved.marked || []) state.marked.add(Number(id));
  for (const id of saved.visited || []) state.visited.add(Number(id));
  for (const [id, ms] of Object.entries(saved.questionMs || {})) {
    if (Number.isFinite(Number(ms))) state.questionMs.set(Number(id), Number(ms));
  }
  for (const [id, saved] of Object.entries(saved.reports || {})) {
    // Older saves kept a bare string; accept both shapes.
    if (typeof saved === 'string') state.reports.set(Number(id), { reason: 'other', detail: saved });
    else if (saved && typeof saved === 'object') state.reports.set(Number(id), saved);
  }
}

/* ------------------------------------------------------------------ */
/* Boot: choose the paper                                             */
/* ------------------------------------------------------------------ */

async function loadPaper() {
  const intro = $('#intro-view');

  if (!requestedTest) {
    showPaperProblem({
      title: 'No test selected',
      body: 'Open the test series and pick a paper to attempt.',
      actionLabel: 'Browse tests',
      actionHref: 'tests.html'
    });
    return;
  }

  try {
    const quiz = await request(`/quizzes/${requestedTest}/`);

    if (quiz.has_access === false) {
      showPaperProblem({
        title: 'This paper is part of a paid batch',
        body: 'Redeem an access code on the batch page to unlock it. Nothing is charged here.',
        actionLabel: 'Open the batch',
        actionHref: quiz.course_slug ? `course.html?slug=${encodeURIComponent(quiz.course_slug)}` : 'courses.html'
      });
      return;
    }

    if (!Array.isArray(quiz.questions) || !quiz.questions.length) {
      showPaperProblem({
        title: 'This paper has no published questions',
        body: 'The paper exists but its questions are not published yet.',
        actionLabel: 'Other tests',
        actionHref: 'tests.html'
      });
      return;
    }

    state.ready = true;
    state.test = {
      id: quiz.id,
      title: quiz.title || 'Untitled paper',
      exam: quiz.series_subject || quiz.course_subject || 'General',
      kind: quiz.timing_mode === 'untimed' ? 'Practice' : 'Timed mock',
      duration: minDuration(quiz.duration_minutes),
      instructions: quiz.instructions || ''
    };
    state.durationMinutes = state.test.duration;
    state.questions = quiz.questions.map((question) => apiQuestion(question, quiz));
    state.marksPerQuestion = Number(quiz.marks_per_question ?? 0);
    state.negativeMarks = Number(quiz.negative_marks_per_wrong ?? 0);
    state.test.exam = quiz.series_subject || quiz.course_subject || 'General';

    if (requestedAttempt) await resumeAttempt(requestedAttempt);
    else renderIntro();
  } catch (err) {
    showPaperProblem({
      title: err.status === 404 ? 'Paper not found' : 'The paper could not be loaded',
      body:
        err.status === 404
          ? 'This test does not exist or is no longer published.'
          : err.message || 'The server did not answer.',
      actionLabel: 'All tests',
      actionHref: 'tests.html'
    });
  }
}

/** Deep link from "My attempts": continue an in-progress attempt. */
async function resumeAttempt(attemptId) {
  try {
    const attempt = await request(`/quiz-attempts/${attemptId}/`, {
      guestToken: storage.guestToken
    });
    if (attempt.status !== 'in_progress') {
      await showReleasedResult(attemptId);
      return;
    }
    state.attemptId = attempt.id;
    state.deadline = attempt.deadline ? Date.parse(attempt.deadline) : null;
    state.startedAt = attempt.started_at ? Date.parse(attempt.started_at) : Date.now();
    if (Array.isArray(attempt.question_order) && attempt.question_order.length) {
      state.questions = orderQuestions(state.questions, attempt.question_order);
    }
    if (attempt.rules_snapshot?.duration_minutes) {
      state.durationMinutes = minDuration(attempt.rules_snapshot.duration_minutes);
    }
    renderIntro();
    toast('Resumed your attempt.', 'info');
  } catch {
    renderIntro();
  }
}

/** A released result can be reopened from the attempts list. */
async function showReleasedResult(attemptId) {
  try {
    const result = await request(`/quiz-attempts/${attemptId}/result/`, {
      guestToken: storage.guestToken
    });
    state.submitted = true;
    state.result = normaliseServerResult(result);
    renderResult(false);
  } catch (err) {
    showPaperProblem({
      title: 'Result not available',
      body: err.status === 403 ? 'The result for this paper has not been released yet.' : err.message,
      actionLabel: 'My attempts',
      actionHref: 'tests.html#attempted'
    });
  }
}

function showPaperProblem({ title, body, actionLabel, actionHref }) {
  const host = $('#intro-view');
  host.hidden = false;
  const target = $('#intro-note') || host;
  target.hidden = false;
  target.className = 'intro-note is-warning';
  target.innerHTML = `
    <div class="empty-state is-error" role="alert">
      ${icon('alert')}
      <h3>${esc(title)}</h3>
      <p>${esc(body || '')}</p>
      ${actionHref ? `<a class="btn btn-primary" href="${esc(actionHref)}">${esc(actionLabel || 'Continue')}</a>` : ''}
    </div>`;
  const start = $('#start-btn');
  if (start) {
    start.disabled = true;
    start.hidden = true;
  }
  setText('#intro-title', title);
  setText('#intro-sub', '');
  setText('#intro-count', '—');
  setText('#intro-time', '—');
  setText('#intro-marks', '—');
}

/* ------------------------------------------------------------------ */
/* Intro                                                              */
/* ------------------------------------------------------------------ */

function renderIntro() {
  const total = state.questions.reduce((sum, q) => sum + q.marks, 0);
  const negatives = state.questions.map((q) => q.negative).filter((n) => n > 0);
  const marks = state.questions[0]?.marks ?? 0;

  setText('#intro-title', state.test.title);
  setText('#intro-sub', `${state.test.exam} · ${state.test.kind}`);
  setText('#intro-count', state.questions.length);
  setText('#intro-time', `${state.durationMinutes} minutes`);
  setText('#intro-marks', total);
  setText('#intro-marking', negatives.length ? `+${marks} · −${negatives[0]}` : `+${marks} · no negative marking`);

  // Faculty instructions replace the generic list when the paper carries any.
  const list = $('#intro-list');
  if (list && state.test.instructions) {
    list.innerHTML = String(state.test.instructions)
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => `<li>${esc(line.replace(/^[-*\d.\s]+/, ''))}</li>`)
      .join('');
  }

  const note = $('#intro-note');
  if (state.attemptId && state.deadline) {
    const left = Math.max(0, Math.round((state.deadline - Date.now()) / 60000));
    note.hidden = false;
    note.className = 'intro-note';
    note.innerHTML = `${icon('clock')}<span>This attempt is already running on the server — about ${left} minute${left === 1 ? '' : 's'} left. Starting continues where you stopped.</span>`;
  } else if (readSaved()) {
    note.hidden = false;
    note.className = 'intro-note';
    note.innerHTML = `${icon('refresh')}<span>You have an attempt in progress on this device. Starting resumes it with the time you have left.</span>`;
  } else if (!isSignedIn()) {
    note.hidden = false;
    note.className = 'intro-note';
    note.innerHTML = `${icon('info')}<span>You can attempt this paper without an account. Signing in keeps the attempt in your history. <a class="link" href="login.html?next=test-player.html%3Ftest%3D${state.testId}">Sign in</a></span>`;
  } else {
    note.hidden = true;
  }

  updateStartState();
}

function updateStartState() {
  const start = $('#start-btn');
  if (!start) return;
  const agree = $('#agree')?.checked ?? false;
  start.disabled = !agree || !state.ready;
  start.hidden = !state.ready;
  start.textContent = readSaved() || state.attemptId ? 'Resume test' : 'Start test';
}

$('#agree').addEventListener('change', updateStartState);

/* ------------------------------------------------------------------ */
/* Start                                                              */
/* ------------------------------------------------------------------ */

async function startTest() {
  // The attempt exists on the server or it does not exist at all: starting
  // means asking the API to create (or resume) it and taking the deadline and
  // question order the server hands back.
  const saved = readSaved();

  if (saved && state.attemptId) {
    applySaved(saved);
    enterExam();
    toast('Resumed your attempt.', 'info');
    return;
  }

  try {
    const attempt = await request('/quizzes/start/', {
      method: 'POST',
      body: { quiz_id: state.test.id },
      // A token from an earlier visit resumes that attempt instead of opening
      // a second one, and is how a guest keeps ownership of the paper.
      guestToken: isSignedIn() ? undefined : storage.guestToken
    });

    state.attemptId = attempt.id;
    if (!isSignedIn() && attempt.guest_token) storage.guestToken = attempt.guest_token;
    state.guestToken = isSignedIn() ? null : storage.guestToken;

    state.startedAt = attempt.started_at ? Date.parse(attempt.started_at) : Date.now();
    state.deadline = attempt.deadline
      ? Date.parse(attempt.deadline)
      : state.startedAt + state.durationMinutes * 60000;
    if (Array.isArray(attempt.question_order) && attempt.question_order.length) {
      state.questions = orderQuestions(state.questions, attempt.question_order);
    }
  } catch (err) {
    if (err.status === 403) {
      toast('This paper is part of a paid batch. Redeem an access code on the batch page.', 'error', 6000);
    } else if (err.status === 400) {
      toast(err.message || 'This paper cannot be started right now.', 'error', 6000);
    } else if (err.status === 429) {
      // Saying "the server did not answer" here would be a lie: it answered,
      // and the reason is worth passing on.
      toast('Too many papers started from this connection. Try again in a few minutes.', 'error', 6000);
    } else {
      toast('The server did not answer. Nothing was started — try again.', 'error', 6000);
    }
    updateStartState();
    return;
  }

  enterExam();
}

function enterExam() {
  state.mode = 'exam';
  state.sections = groupSections(state.questions);

  $('#intro-view').hidden = true;
  $('#exam-view').hidden = false;
  document.body.classList.add('is-exam');
  const skip = document.querySelector('.skip-link');
  if (skip) {
    skip.href = '#exam-main';
    skip.textContent = 'Skip to the question';
  }

  setText('#exam-name', state.test.title);
  setText('#exam-sub', `${state.test.exam} · ${state.test.kind}`);
  $('#attempt-badge').textContent = 'Server-scored';

  const name = storage.user?.username || 'Guest';
  setText('#candidate-name', name);
  setText('#candidate-avatar', name.slice(0, 2).toUpperCase());

  renderSections();
  renderQuestion();
  renderPalette();
  startTimer();
  persist();
}

$('#start-btn').addEventListener('click', () => {
  const button = $('#start-btn');
  button.disabled = true;
  startTest().catch(() => {
    button.disabled = false;
    toast('Could not start the test. Check your connection and try again.', 'error');
  });
});

/* ------------------------------------------------------------------ */
/* Sections                                                           */
/* ------------------------------------------------------------------ */

let activeSection = null;

function renderSections() {
  const host = $('#section-tabs');
  host.innerHTML = state.sections
    .map((section, index) => {
      const first = state.questions.findIndex((q) => q.section === section.name);
      return `<button class="exam-tab" type="button" role="tab" data-section="${index}"
                aria-selected="${index === 0}" data-first="${first}">${esc(section.name)}
                <span>${section.questions.length}</span></button>`;
    })
    .join('');

  activeSection = state.sections[0]?.name || null;
}

$('#section-tabs').addEventListener('click', (e) => {
  const tab = e.target.closest('[data-section]');
  if (!tab) return;
  const index = Number(tab.dataset.section);
  activeSection = state.sections[index]?.name || null;
  $$('#section-tabs .exam-tab').forEach((node, i) => node.setAttribute('aria-selected', String(i === index)));
  const target = Number(tab.dataset.first);
  if (Number.isInteger(target) && target >= 0) goTo(target);
});

function syncSectionTab() {
  if (!state.sections.length) return;
  const question = state.questions[state.current];
  const index = state.sections.findIndex((s) => s.name === question?.section);
  if (index < 0) return;
  activeSection = state.sections[index].name;
  $$('#section-tabs .exam-tab').forEach((node, i) => node.setAttribute('aria-selected', String(i === index)));
}

/* ------------------------------------------------------------------ */
/* Question panel                                                     */
/* ------------------------------------------------------------------ */

function currentQuestion() {
  return state.questions[state.current];
}

/* Per-question clock: time only accrues while the question is on screen and
   the paper is not paused, so a break never inflates the reading. */
/** Stop the per-question clock and credit the time to the question it ran for. */
function bankQuestionTime() {
  if (state.activeSince === null || state.activeId === null) return;
  const spent = Date.now() - state.activeSince;
  state.questionMs.set(state.activeId, (state.questionMs.get(state.activeId) || 0) + spent);
  state.activeSince = null;
  state.activeId = null;
}

function timeOnQuestion(q) {
  if (!q) return 0;
  const banked = state.questionMs.get(q.id) || 0;
  const running = q.id === state.activeId && state.activeSince !== null && !state.paused;
  return banked + (running ? Date.now() - state.activeSince : 0);
}

/** Inline SVG bar chart for data-interpretation passages. */
function barChart(chart) {
  if (!chart?.labels?.length) return '';
  const w = 520;
  const h = 220;
  const padL = 34;
  const padB = 26;
  const padT = 12;
  const max = Number(chart.max) || Math.max(...chart.values) || 1;
  const slot = (w - padL - 12) / chart.labels.length;
  const barW = Math.min(46, slot * 0.56);
  const ticks = Array.from({ length: 5 }, (_, i) => Math.round((max / 4) * i));

  return `
    <figure class="qchart">
      <svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(chart.alt || 'Bar chart')}">
        ${ticks
          .map((tick) => {
            const y = padT + (h - padT - padB) * (1 - tick / max);
            return `<g class="qchart-tick">
              <line x1="${padL}" x2="${w - 8}" y1="${y}" y2="${y}"/>
              <text x="${padL - 8}" y="${y + 4}" text-anchor="end">${tick}</text>
            </g>`;
          })
          .join('')}
        ${chart.values
          .map((value, i) => {
            const x = padL + slot * i + (slot - barW) / 2;
            const barH = ((h - padT - padB) * value) / max;
            const y = h - padB - barH;
            return `<g class="qchart-bar">
              <rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="3"><title>${esc(chart.labels[i])}: ${value}${esc(chart.unit || '')}</title></rect>
              <text class="qchart-label" x="${x + barW / 2}" y="${h - 8}" text-anchor="middle">${esc(chart.labels[i])}</text>
            </g>`;
          })
          .join('')}
        <line class="qchart-axis" x1="${padL}" x2="${w - 8}" y1="${h - padB}" y2="${h - padB}"/>
      </svg>
      ${chart.caption ? `<figcaption>${esc(chart.caption)}</figcaption>` : ''}
    </figure>`;
}

function renderComprehension(q) {
  const host = $('#comprehension');
  if (!host) return;
  const passage = q.comprehension;
  if (!passage) {
    host.hidden = true;
    host.innerHTML = '';
    document.body.classList.remove('has-passage');
    return;
  }
  host.hidden = false;
  document.body.classList.add('has-passage');
  host.innerHTML = `
    <header class="comprehension-head">
      <h2>${esc(passage.title || 'Comprehension')}</h2>
      ${passage.range ? `<span class="comprehension-range">${esc(passage.range)}</span>` : ''}
    </header>
    ${passage.text ? `<p class="comprehension-text">${esc(passage.text)}</p>` : ''}
    ${barChart(passage.chart)}`;
}

function renderQuestion({ focus = false } = {}) {
  const q = currentQuestion();
  if (!q) return;

  bankQuestionTime();

  const chosen = state.answers.get(q.id);
  const marked = state.marked.has(q.id);
  const number = state.current + 1;

  setText('#q-number', `Question No. ${number}`);
  setText('#q-marks', `+${q.marks}`);
  const negNode = $('#q-negative');
  if (negNode) {
    negNode.textContent = q.negative ? `-${q.negative}` : '';
    negNode.hidden = !q.negative;
  }
  setText('#q-time', shortClock(timeOnQuestion(q)));
  $('#report-btn')?.classList.toggle('is-reported', state.reports.has(q.id));

  renderComprehension(q);

  $('#qpanel').innerHTML = `
    <p class="qpanel-label">Question:</p>
    <p class="qpanel-text" id="qpanel-text">${esc(q.prompt)}</p>

    <div class="qpanel-options" role="radiogroup" aria-labelledby="qpanel-text">
      ${q.options
        .map(
          (option, i) => `
        <label class="qoption ${chosen === option.id ? 'is-selected' : ''}">
          <input type="radio" name="answer" value="${esc(option.id)}" data-choice="${esc(option.id)}"
                 ${chosen === option.id ? 'checked' : ''}>
          <span class="qoption-key" aria-hidden="true"></span>
          <span class="qoption-text">${esc(option.text)}</span>
        </label>`
        )
        .join('')}
    </div>

    <footer class="qpanel-foot">
      <span class="qpanel-state ${marked ? 'is-marked' : chosen !== undefined ? 'is-answered' : ''}">
        ${marked ? icon('flag') + ' Marked for review' : chosen !== undefined ? icon('check') + ' Answered' : 'Not answered'}
      </span>
      <span class="qpanel-hint">Press 1–${q.options.length} to answer, ← → to move</span>
    </footer>`;

  if (focus) $('#qpanel').focus({ preventScroll: true });
  state.visited.add(q.id);
  state.activeId = q.id;
  state.activeSince = state.paused ? null : Date.now();
  syncSectionTab();
  renderPalette();
  persist();
}

$('#qpanel').addEventListener('change', (e) => {
  const input = e.target.closest('[data-choice]');
  if (!input) return;
  const q = currentQuestion();
  const raw = input.value;
  const choice = Number.isNaN(Number(raw)) ? raw : Number(raw);
  state.answers.set(q.id, choice);

  /* Toggle classes in place: a full re-render would drop keyboard focus. */
  $$('#qpanel .qoption').forEach((label) => {
    const field = label.querySelector('[data-choice]');
    label.classList.toggle('is-selected', field?.checked ?? false);
  });
  const stateNode = $('#qpanel .qpanel-state');
  if (stateNode) {
    stateNode.className = `qpanel-state is-answered`;
    stateNode.innerHTML = `${icon('check')} Answered`;
  }

  renderPalette();
  saveAnswer(q.id);
});

function goTo(index) {
  if (index < 0 || index >= state.questions.length) return;
  state.current = index;
  renderQuestion({ focus: true });
  renderPalette();
  $('#qpanel').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/** Advance one question; syncSectionTab keeps the strip in step. */
function goNext() {
  if (state.current < state.questions.length - 1) goTo(state.current + 1);
  else openSubmit();
}

$('#next-btn').addEventListener('click', () => {
  state.visited.add(currentQuestion().id);
  goNext();
});

$('#prev-btn').addEventListener('click', () => goTo(state.current - 1));

$('#clear-btn').addEventListener('click', () => {
  const q = currentQuestion();
  state.answers.delete(q.id);
  renderQuestion();
  renderPalette();
  saveAnswer(q.id);
  toast('Response cleared.', 'info', 1800);
});

$('#mark-btn').addEventListener('click', () => {
  const q = currentQuestion();
  if (state.marked.has(q.id)) state.marked.delete(q.id);
  else state.marked.add(q.id);
  saveAnswer(q.id);
  renderQuestion();
  renderPalette();
  goNext();
});

/* ------------------------------------------------------------------ */
/* Palette                                                            */
/* ------------------------------------------------------------------ */

function statusOf(q) {
  const answered = state.answers.has(q.id);
  const marked = state.marked.has(q.id);
  if (marked && answered) return 'is-marked-answered';
  if (marked) return 'is-marked';
  if (answered) return 'is-answered';
  if (state.visited.has(q.id)) return 'is-not-answered';
  return 'is-unvisited';
}

function counts() {
  let answered = 0;
  let marked = 0;
  let visited = 0;
  let markedAnswered = 0;
  let markedOnly = 0;

  for (const q of state.questions) {
    const isAnswered = state.answers.has(q.id);
    const isMarked = state.marked.has(q.id);
    if (isAnswered) answered += 1;
    if (isMarked) marked += 1;
    if (state.visited.has(q.id)) visited += 1;
    if (isMarked && isAnswered) markedAnswered += 1;
    else if (isMarked) markedOnly += 1;
  }

  return {
    answered,
    marked,
    markedAnswered,
    markedOnly,
    visited,
    notAnswered: visited - answered,
    unvisited: state.questions.length - visited
  };
}

const LEGEND = [
  ['is-answered', 'Answered'],
  ['is-marked', 'Marked'],
  ['is-unvisited', 'Not Visited'],
  ['is-marked-answered', 'Marked and answered'],
  ['is-not-answered', 'Not Answered']
];

function renderLegend(c) {
  const host = $('#legend-counts');
  if (!host) return;
  const value = {
    'is-answered': c.answered,
    'is-marked': c.markedOnly,
    'is-unvisited': c.unvisited,
    'is-marked-answered': c.markedAnswered,
    'is-not-answered': c.notAnswered
  };
  host.innerHTML = LEGEND.map(
    ([cls, label]) => `<li><i class="lg ${cls}" aria-hidden="true"></i><span>${label}</span><b>${value[cls]}</b></li>`
  ).join('');
}

function renderPalette() {
  const host = $('#palette-groups');
  if (!host) return;

  // The rail mirrors the reference: only the section you are in is numbered.
  const section = state.sections.find((s) => s.name === activeSection) || state.sections[0];
  const name = section?.name || 'Questions';
  setText('#palette-section', name);

  host.innerHTML = section
    ? `<div class="palette-grid">
         ${section.questions
           .map((q) => {
             const index = state.questions.findIndex((row) => row.id === q.id);
             const status = statusOf(q);
             const human = status.replace('is-', '').replace(/-/g, ' ');
             return `<button class="pal-btn ${status} ${index === state.current ? 'is-current' : ''}"
                       type="button" data-jump="${index}"
                       aria-label="Question ${index + 1}, ${human}"
                       aria-current="${index === state.current ? 'true' : 'false'}">${index + 1}</button>`;
           })
           .join('')}
       </div>`
    : '';

  const c = counts();
  renderLegend(c);
  setText('#palette-progress', `${c.answered} of ${state.questions.length} answered`);
}

$('#palette-groups').addEventListener('click', (e) => {
  const button = e.target.closest('[data-jump]');
  if (!button) return;
  goTo(Number(button.dataset.jump));
});

/* ------------------------------------------------------------------ */
/* Saving                                                             */
/* ------------------------------------------------------------------ */

let saveTimer = null;
let saveChain = Promise.resolve();

function setSaveState(text, tone = '') {
  const node = $('#autosave-state');
  if (!node) return;
  node.textContent = text;
  node.dataset.tone = tone;
}

function saveAnswer(questionId) {
  persist();
  setSaveState('Saving…');

  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const q = state.questions.find((row) => row.id === questionId);
    if (!q) return;
    const choice = state.answers.get(q.id);

    if (!state.attemptId) {
      setSaveState('Not started');
      return;
    }

    saveChain = saveChain
      .then(() =>
        request(`/quiz-attempts/${state.attemptId}/autosave/`, {
          method: 'POST',
          body: {
            question_id: q.id,
            choice_ids: choice === undefined ? [] : [choice],
            marked_for_review: state.marked.has(q.id)
          },
          guestToken: state.guestToken || undefined
        })
      )
      .then(() => setSaveState(SAVE_KEY_NOTE))
      .catch((err) => {
        setSaveState('Saved on this device', 'warn');
        if (err.status === 404) toast('This attempt is no longer available on the server.', 'error', 5000);
      });
  }, 450);
}

/* ------------------------------------------------------------------ */
/* Timer                                                              */
/* ------------------------------------------------------------------ */

function paintClock(remaining) {
  const parts = clockParts(remaining);
  setText('#timer-h', parts.h);
  setText('#timer-m', parts.m);
  setText('#timer-s', parts.s);
  $('#exam-timer')?.classList.toggle('is-critical', remaining <= 300);
  const label = $('#exam-timer');
  if (label) label.setAttribute('aria-label', `Time left ${parts.h} hours ${parts.m} minutes`);
}

function remainingSeconds() {
  return Math.max(0, Math.floor((state.deadline - Date.now()) / 1000));
}

function startTimer() {
  if (ticker) clearInterval(ticker);
  warned = false;

  const tick = () => {
    if (state.submitted || state.paused) return;
    const remaining = remainingSeconds();
    paintClock(remaining);

    const q = currentQuestion();
    if (q) setText('#q-time', shortClock(timeOnQuestion(q)));

    if (remaining <= 300 && !warned) {
      warned = true;
      toast('Five minutes left. Finish the questions you have marked.', 'info', 5000);
    }

    if (remaining <= 0) {
      clearInterval(ticker);
      ticker = null;
      submitAttempt(true);
    }
  };

  tick();
  ticker = setInterval(tick, 1000);
}

/* ------------------------------------------------------------------ */
/* Pause, full screen, report, instructions                           */
/* ------------------------------------------------------------------ */

function pauseExam() {
  if (state.paused || state.mode !== 'exam' || state.submitted) return;
  bankQuestionTime();
  state.paused = true;
  state.pauseStartedAt = Date.now();
  state.activeSince = null;
  state.activeId = null;
  if (ticker) clearInterval(ticker);
  ticker = null;

  const veil = $('#pause-veil');
  if (veil) veil.hidden = false;
  document.body.classList.add('is-paused');
  $('#resume-btn')?.focus();
  persist();
}

function resumeExam() {
  if (!state.paused) return;
  const pausedFor = Date.now() - (state.pauseStartedAt || Date.now());
  // Push the local deadline by the pause duration so the candidate keeps the
  // time they did not use. A scheduled, server-scored test still expires on
  // the server's own deadline.
  state.deadline += pausedFor;
  state.paused = false;
  state.pauseStartedAt = null;
  state.activeId = currentQuestion()?.id ?? null;
  state.activeSince = Date.now();

  const veil = $('#pause-veil');
  if (veil) veil.hidden = true;
  document.body.classList.remove('is-paused');
  startTimer();
  $('#pause-btn')?.focus();
  persist();
}

$('#pause-btn')?.addEventListener('click', pauseExam);
$('#resume-btn')?.addEventListener('click', resumeExam);

/* Full screen — offered only where the browser supports it. */
const fullscreenBtn = $('#fullscreen-btn');
if (fullscreenBtn && document.documentElement.requestFullscreen) {
  fullscreenBtn.hidden = false;
  const syncFullscreenLabel = () => {
    fullscreenBtn.textContent = document.fullscreenElement ? 'Exit Full Screen' : 'Enter Full Screen';
  };
  fullscreenBtn.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      toast('This browser blocked full screen. Press F11 instead.', 'info');
    }
    syncFullscreenLabel();
  });
  document.addEventListener('fullscreenchange', syncFullscreenLabel);
  syncFullscreenLabel();
}

/* Instructions, available at any point during the paper. */
function instructionItems() {
  return [
    'The paper has several sections. Use the section tabs to move between them.',
    'Every question shows its marks and negative marking at the top of the panel.',
    'Save & Next records the answer and moves on. Mark for Review & Next flags it so you can return.',
    'Clear Response removes the answer you picked for this question.',
    'The palette shows the status of every question in the current section, and the legend counts the whole paper.',
    'When the timer reaches zero the paper is submitted automatically.'
  ];
}

$('#instructions-btn')?.addEventListener('click', () => {
  const list = $('#instruction-list');
  if (list) list.innerHTML = instructionItems().map((text) => `<li>${esc(text)}</li>`).join('');
  openModal('#instructions-modal');
});

/* ------------------------------------------------------------------ */
/* Report a question                                                   */
/* ------------------------------------------------------------------ */

/* The reason used to be parked in the autosave payload and dropped by the
   server. It is now a `QuestionReport` row, addressed by the same credential
   that submits the paper (bearer token, or the guest attempt token). */
const REPORT_LABELS = {
  wrong_answer: 'The marked answer looks wrong',
  ambiguous: 'The question is ambiguous',
  typo: 'Spelling or formatting problem',
  missing_info: 'Not enough information to answer',
  other: 'Something else'
};

$('#report-btn')?.addEventListener('click', () => {
  const q = currentQuestion();
  if (!q) return;
  setText('#report-context', `Question ${state.current + 1} · ${q.section}`);
  const existing = state.reports.get(q.id);
  const category = $('#report-category');
  const field = $('#report-reason');
  if (category) category.value = existing?.reason || 'wrong_answer';
  if (field) field.value = existing?.detail || '';
  const error = $('#report-error');
  if (error) error.hidden = true;
  openModal('#report-modal');
  category?.focus();
});

$('#report-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const q = currentQuestion();
  const reason = $('#report-category')?.value || 'other';
  const detail = ($('#report-reason')?.value || '').trim();
  const error = $('#report-error');
  const submit = $('#report-form button[type="submit"]');
  if (!q || !state.attemptId) return;

  if (submit) submit.disabled = true;
  if (error) error.hidden = true;
  try {
    await request('/question-reports/', {
      method: 'POST',
      body: {
        attempt: state.attemptId,
        question: q.id,
        reason,
        detail: detail.slice(0, 1000)
      },
      guestToken: state.guestToken || undefined
    });
    state.reports.set(q.id, { reason, detail });
    persist();
    $('#report-btn')?.classList.add('is-reported');
    closeModal('#report-modal');
    toast("Report sent. The paper's team can now see it.", "success");
  } catch (err) {
    if (error) {
      error.hidden = false;
      error.textContent =
        err?.status === 403
          ? 'This attempt can no longer be changed, so the report was not sent.'
          : err?.message || 'The report did not send. Try again in a moment.';
    }
  } finally {
    if (submit) submit.disabled = false;
  }
});

/* ------------------------------------------------------------------ */
/* Submit                                                             */
/* ------------------------------------------------------------------ */

function summaryBySection() {
  return state.sections.map((section) => {
    let answered = 0;
    let marked = 0;
    for (const q of section.questions) {
      if (state.answers.has(q.id)) answered += 1;
      if (state.marked.has(q.id)) marked += 1;
    }
    return { name: section.name, answered, marked, total: section.questions.length };
  });
}

function openSubmit() {
  const rows = summaryBySection();
  const c = counts();

  $('#summary-rows').innerHTML = rows
    .map(
      (row) => `<tr>
        <th scope="row">${esc(row.name)}</th>
        <td>${row.answered}</td>
        <td>${row.total - row.answered}</td>
        <td>${row.marked}</td>
      </tr>`
    )
    .join('');

  setText('#modal-answered', c.answered);
  setText('#modal-unanswered', c.notAnswered);
  setText('#modal-marked', c.marked);
  setText('#modal-unvisited', c.unvisited);

  openModal('#submit-modal');
  $('#confirm-submit')?.focus();
}

function openModal(selector) {
  const modal = $(selector);
  if (!modal) return;
  modal.classList.add('is-open');
  document.body.classList.add('is-locked');
}

function closeModal(selector) {
  const modal = $(selector);
  if (!modal) return;
  modal.classList.remove('is-open');
  document.body.classList.remove('is-locked');
}

$('#submit-btn').addEventListener('click', openSubmit);
$('#submit-rail-btn')?.addEventListener('click', openSubmit);
$('#confirm-submit').addEventListener('click', () => {
  closeModal('#submit-modal');
  submitAttempt(false);
});

document.addEventListener('click', (e) => {
  if (e.target.closest('[data-close-modal]')) closeModal('#submit-modal');
  if (e.target.closest('[data-close-paper]')) closeModal('#paper-modal');
  if (e.target.closest('[data-close-instructions]')) closeModal('#instructions-modal');
  if (e.target.closest('[data-close-report]')) closeModal('#report-modal');
  if (e.target.id === 'submit-modal') closeModal('#submit-modal');
  if (e.target.id === 'paper-modal') closeModal('#paper-modal');
  if (e.target.id === 'instructions-modal') closeModal('#instructions-modal');
  if (e.target.id === 'report-modal') closeModal('#report-modal');
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeModal('#submit-modal');
    closeModal('#paper-modal');
    closeModal('#instructions-modal');
    closeModal('#report-modal');
    return;
  }
  if (state.mode !== 'exam' || state.paused) return;
  if (e.target.matches('input, textarea, select')) return;

  if (e.key === 'ArrowRight') {
    e.preventDefault();
    goNext();
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    goTo(state.current - 1);
  } else if (/^[1-6]$/.test(e.key)) {
    const option = currentQuestion()?.options[Number(e.key) - 1];
    if (!option) return;
    e.preventDefault();
    state.answers.set(currentQuestion().id, option.id);
    renderQuestion();
    renderPalette();
    saveAnswer(currentQuestion().id);
  }
});

async function submitAttempt(auto) {
  if (state.submitted) return;
  state.submitted = true;
  if (ticker) clearInterval(ticker);
  ticker = null;
  bankQuestionTime();
  document.body.classList.remove('is-paused');

  setSaveState('Submitting…');

  const answers = state.questions.map((q) => ({
    question_id: q.id,
    choice_ids: state.answers.has(q.id) ? [state.answers.get(q.id)] : [],
    marked_for_review: state.marked.has(q.id)
  }));

  let serverResult = null;

  if (state.attemptId) {
    try {
      serverResult = await request(`/quiz-attempts/${state.attemptId}/submit/`, {
        method: 'POST',
        body: { answers },
        guestToken: state.guestToken || undefined
      });
      state.released = Boolean(serverResult?.answers_detail);
    } catch (err) {
      toast(
        err.status === 404
          ? 'This attempt is no longer on the server. Nothing was saved — reload the paper.'
          : 'The submission did not reach the server. Your answers are still on this device.',
        'error',
        6000
      );
      state.submitted = false;
      setSaveState('Not submitted', 'warn');
      return;
    }
  } else {
    toast('There is no server attempt for this paper, so it cannot be scored.', 'error', 6000);
    state.submitted = false;
    return;
  }

  state.result = normaliseServerResult(serverResult);
  state.result.releaseNote = !state.released;

  renderResult(auto);
}

function normaliseServerResult(payload) {
  const bySection = (payload.section_breakdown || []).map((row) => ({
    name: row.section || 'Questions',
    correct: row.correct,
    incorrect: row.incorrect,
    unanswered: row.unanswered,
    scored: Number(row.score),
    max: Number(row.max_score)
  }));

  return {
    score: Number(payload.score ?? 0),
    max: Number(payload.max_score ?? 0),
    percentage: Number(payload.percentage ?? 0),
    correct: payload.correct_count ?? 0,
    incorrect: payload.incorrect_count ?? 0,
    unattempted: payload.unanswered_count ?? 0,
    marked: payload.marked_for_review_count ?? 0,
    timeTaken: payload.time_taken_seconds ?? 0,
    passed: payload.passed,
    bySection,
    solutions: (payload.answers_detail || []).map((row) => {
      const question = state.questions.find((q) => q.id === row.question);
      return {
        question,
        selected: (row.selected_choices || []).map((c) => c.id),
        correctChoices: (row.correct_choices || []).map((c) => c.id),
        correct: Boolean(row.is_correct),
        answered: Boolean(row.answered),
        explanation: row.explanation || question?.explanation || ''
      };
    })
  };
}

/* ------------------------------------------------------------------ */
/* Result                                                             */
/* ------------------------------------------------------------------ */

let reviewFilter = 'all';

function renderResult(auto) {
  state.mode = 'result';
  storage.attempt = null;
  document.body.classList.remove('is-exam');

  $('#exam-view').hidden = true;
  $('#result-view').hidden = false;

  const r = state.result;
  const accuracy = r.accuracy ?? (r.correct + r.incorrect ? Math.round((r.correct / (r.correct + r.incorrect)) * 100) : 0);
  const attempted = r.correct + r.incorrect;

  $('#result-sub').textContent = !state.released
    ? auto
      ? 'Time ran out, so the paper was submitted automatically. The score above is final; solutions appear when the paper is released.'
      : 'Your paper was scored on the server. Solutions appear here once the paper is released.'
    : auto
      ? 'Time ran out, so the paper was submitted automatically. Every question is reviewed below.'
      : 'Every question is reviewed below, with the correct option and the explanation from the paper.';

  $('#result-hero').innerHTML = `
    <div class="result-score">
      <strong>${r.score}</strong>
      <span>out of ${r.max} marks</span>
    </div>
    <div class="result-hero-meta">
      <div><span>Percentage</span><b>${r.percentage}%</b></div>
      <div><span>Attempted</span><b>${attempted}/${state.questions.length}</b></div>
      <div><span>Time taken</span><b>${clock(r.timeTaken)}</b></div>
      <div><span>${r.passed === false ? 'Status' : r.passed === true ? 'Status' : 'Marking'}</span>
        <b>${r.passed === true ? 'Passed' : r.passed === false ? 'Below pass mark' : 'Negative marking applied'}</b></div>
    </div>`;

  $('#result-stats').innerHTML = [
    ['Correct', r.correct, 'ok'],
    ['Incorrect', r.incorrect, 'no'],
    ['Unattempted', r.unattempted, 'skip'],
    ['Accuracy', `${accuracy}%`, '']
  ]
    .map(
      ([label, value, tone]) => `<div class="result-stat ${tone}"><strong>${esc(String(value))}</strong><span>${esc(label)}</span></div>`
    )
    .join('');

  $('#section-breakdown').innerHTML = !r.bySection.length
    ? `<p class="small muted" style="margin:0">Section-wise detail is published with the solutions.</p>`
    : r.bySection
    .map((row) => {
      const pct = row.max ? clamp((row.scored / row.max) * 100, 0, 100) : 0;
      return `
        <div class="section-row">
          <div class="section-row-head">
            <strong>${esc(row.name)}</strong>
            <span>${row.correct} correct · ${row.incorrect} wrong · ${row.unanswered} left</span>
            <b>${Math.round(row.scored * 10) / 10} / ${row.max}</b>
          </div>
          <div class="section-track"><i style="width:${pct}%"></i></div>
        </div>`;
    })
    .join('');

  renderSolutions();
  $('#result-view').scrollIntoView({ block: 'start' });
  document.title = `${r.score}/${r.max} — answer sheet · StudySpace`;
}

function renderSolutions() {
  const host = $('#solutions');
  const rows = (state.result?.solutions || []).filter((row) => {
    if (reviewFilter === 'correct') return row.correct;
    if (reviewFilter === 'incorrect') return row.answered && !row.correct;
    if (reviewFilter === 'unattempted') return !row.answered;
    return true;
  });

  if (!rows.length) {
    host.innerHTML = state.released
      ? `<div class="empty-state" style="padding:24px">
      ${icon('check-circle')}
      <h3>Nothing to review here</h3>
      <p>Choose another filter to see the rest of the paper.</p>
    </div>`
      : `<div class="empty-state" style="padding:24px">
      ${icon('lock')}
      <h3>Solutions are not released yet</h3>
      <p>The paper owner publishes the correct options after the window closes.</p>
    </div>`;
    return;
  }

  host.innerHTML = rows
    .map((row) => {
      const q = row.question;
      if (!q) return '';
      const index = state.questions.findIndex((item) => item.id === q.id) + 1;
      const chosen = new Set(row.selected.map(Number));
      const correctSet = new Set(row.correctChoices.map(Number));

      const options = q.options
        .map((option, i) => {
          const isCorrect = correctSet.has(Number(option.id));
          const isChosen = chosen.has(Number(option.id));
          const cls = isCorrect ? 'is-correct' : isChosen ? 'is-wrong' : '';
          const label = isCorrect ? 'Correct answer' : isChosen ? 'Your answer' : '';
          return `<div class="solution-opt ${cls}">
            <span class="solution-key">${LETTERS[i]}</span>
            <span>${esc(option.text)}</span>
            ${label ? `<em>${label}</em>` : ''}
          </div>`;
        })
        .join('');

      return `
        <article class="solution">
          <header class="solution-head">
            <span class="solution-number">Q${index}</span>
            <span class="solution-section">${esc(q.section)}</span>
            <span class="solution-mark ${row.correct ? 'ok' : row.answered ? 'no' : 'skip'}">
              ${row.correct ? 'Correct' : row.answered ? 'Incorrect' : 'Not attempted'}
            </span>
          </header>
          <p class="solution-text">${esc(q.prompt)}</p>
          <div class="solution-options">${options}</div>
          ${row.explanation ? `<p class="solution-explanation"><strong>Explanation.</strong> ${esc(row.explanation)}</p>` : ''}
        </article>`;
    })
    .join('');
}

$$('.review-filter [data-filter]').forEach((button) => {
  button.addEventListener('click', () => {
    reviewFilter = button.dataset.filter;
    $$('.review-filter [data-filter]').forEach((node) => node.classList.toggle('is-active', node === button));
    renderSolutions();
  });
});

$('#retake-btn')?.addEventListener('click', () => {
  storage.attempt = null;
  location.href = 'tests.html';
});

$('#print-btn')?.addEventListener('click', () => {
  if (typeof window.print === 'function') window.print();
});

/* ------------------------------------------------------------------ */
/* Question-paper modal                                               */
/* ------------------------------------------------------------------ */

$('#paper-btn')?.addEventListener('click', () => {
  $('#paper-list').innerHTML = state.questions
    .map((q, index) => {
      const status = statusOf(q).replace('is-', '').replace('-', ' ');
      return `<button class="paper-row" type="button" data-goto="${index}">
        <span class="paper-row-no">${index + 1}</span>
        <span class="paper-row-text">${esc(q.prompt)}</span>
        <span class="paper-row-state">${status}</span>
      </button>`;
    })
    .join('');
  openModal('#paper-modal');
});

$('#paper-list')?.addEventListener('click', (e) => {
  const row = e.target.closest('[data-goto]');
  if (!row) return;
  closeModal('#paper-modal');
  goTo(Number(row.dataset.goto));
});

/* ------------------------------------------------------------------ */
/* Boot                                                               */
/* ------------------------------------------------------------------ */

(async function boot() {
  await loadPaper();
  if (!state.ready) return;      // loadPaper already rendered the reason

  const saved = readSaved();
  if (saved) state.questions = orderQuestions(state.questions, saved.questionIds);
  state.sections = groupSections(state.questions);

  renderIntro();
})();
