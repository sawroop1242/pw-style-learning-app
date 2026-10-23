/** Student dashboard: progress, streak, mock trend, upcoming tests and notes. */

import { $, esc, storage, isSignedIn, live } from './core.js';
import { mountChrome, icon, toast } from './ui.js';
import { DASHBOARD, COURSES } from './data.js';

mountChrome('dashboard');

const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

/* ------------------------------------------------------------------ */
/* Greeting                                                           */
/* ------------------------------------------------------------------ */

function renderGreeting() {
  const user = storage.user;
  const name = user?.username || DASHBOARD.student.name.split(' ')[0];
  const hour = new Date().getHours();
  const part = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  $('#greeting').textContent = `${part}, ${name}`;
  if (!isSignedIn()) {
    $('#greeting-sub').innerHTML =
      'You are browsing the demo account. <a href="login.html" style="color:var(--amber-400);text-decoration:underline">Sign in</a> to keep your own progress.';
  }

  const stats = DASHBOARD.stats;
  $('#dash-figures').innerHTML = [
    ['Courses', stats.courses],
    ['Lessons', stats.lessonsDone],
    ['Tests', stats.testsTaken],
    ['Notes', stats.notes]
  ]
    .map(
      ([label, value]) => `
      <div class="dash-figure">
        <strong>${value}</strong>
        <span>${label}</span>
      </div>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Continue learning                                                  */
/* ------------------------------------------------------------------ */

function renderContinue() {
  const host = $('#continue-list');
  host.innerHTML = DASHBOARD.continue
    .map((item) => {
      const course = COURSES.find((c) => c.slug === item.courseSlug) || COURSES[0];
      return `
        <a class="continue-card" href="course.html?slug=${encodeURIComponent(item.courseSlug)}">
          <span class="continue-thumb">${esc(item.glyph)}</span>
          <div class="continue-body">
            <h3>${esc(item.title)}</h3>
            <small class="tiny subtle">${esc(item.chapter)}</small>
            <div class="progress"><span style="width:${item.percent}%"></span></div>
            <div class="continue-meta">
              <span>${item.percent}% complete · ${esc(course.title.split('—')[0].trim())}</span>
              <span class="row" style="gap:4px;color:var(--violet-600);font-weight:700">
                Resume ${icon('arrow-right')}
              </span>
            </div>
          </div>
        </a>`;
    })
    .join('');
}

/* ------------------------------------------------------------------ */
/* Streak                                                             */
/* ------------------------------------------------------------------ */

function renderStreak() {
  const streak = DASHBOARD.student.streak;
  $('#streak-value').textContent = streak;

  const today = new Date().getDay(); // 0 = Sunday
  const mondayIndex = (today + 6) % 7;

  $('#streak-days').innerHTML = DAY_LABELS.map((label, i) => {
    const isToday = i === mondayIndex;
    const done = i < mondayIndex || (i === mondayIndex && streak > 0);
    return `
      <div class="streak-day">
        <div class="streak-dot ${isToday ? 'is-today' : done ? 'is-done' : ''}">
          ${done ? icon('check') : ''}
        </div>
        <small>${label}</small>
      </div>`;
  }).join('');
}

/* ------------------------------------------------------------------ */
/* Chart                                                              */
/* ------------------------------------------------------------------ */

function renderChart() {
  const data = DASHBOARD.performance;
  const max = 100;
  const best = Math.max(...data.map((d) => d.value));

  $('#chart-bars').innerHTML = data
    .map(
      (point) => `
      <div class="chart-bar">
        <span class="tiny strong" style="font-size:10px">${point.value}</span>
        <div class="bar ${point.value === best ? 'is-best' : ''}" style="height:${(point.value / max) * 100}%"
             role="img" aria-label="${point.label}: ${point.value} percent"></div>
        <small>${esc(point.label)}</small>
      </div>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Upcoming                                                           */
/* ------------------------------------------------------------------ */

function renderUpcoming() {
  $('#upcoming-list').innerHTML = DASHBOARD.upcoming
    .map(
      (item) => `
      <a class="upcoming-item" href="test-player.html?test=1">
        <span class="upcoming-date">
          <strong>${esc(item.day)}</strong>
          <span>${esc(item.month)}</span>
        </span>
        <span class="upcoming-body">
          <strong>${esc(item.title)}</strong>
          <small>${esc(item.meta)}</small>
        </span>
        <span class="badge badge-outline">Remind me</span>
      </a>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Batch progress                                                     */
/* ------------------------------------------------------------------ */

function renderBatchProgress() {
  const rows = DASHBOARD.continue.map((c) => ({
    ...c,
    course: COURSES.find((x) => x.slug === c.courseSlug) || COURSES[0]
  }));

  $('#batch-progress').innerHTML = rows
    .map(
      (row) => `
      <div>
        <div class="row-between tiny" style="margin-bottom:5px">
          <span class="truncate strong" style="max-width:70%;font-size:12px">${esc(row.course.exam)} batch</span>
          <span class="subtle">${row.percent}%</span>
        </div>
        <div class="progress" style="height:5px"><span style="width:${row.percent}%"></span></div>
      </div>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Notes                                                              */
/* ------------------------------------------------------------------ */

async function renderNotes() {
  const host = $('#notes-list');
  const { data } = await live('/notes/?page_size=3', DASHBOARD.recentNotes);
  const rows = Array.isArray(data) ? data : data.results || [];

  if (!rows.length) {
    host.innerHTML = `<div class="empty-state" style="padding:24px">${icon('note')}<h3>No notes yet</h3><p>Notes you write on a lesson appear here.</p></div>`;
    return;
  }

  host.innerHTML = rows
    .map(
      (note) => `
      <article class="note-preview">
        <div class="row-between">
          <h3>${esc(note.title || 'Untitled note')}</h3>
          <span class="tiny subtle">${esc(note.at || 'Just now')}</span>
        </div>
        <p>${esc(note.body || '')}</p>
      </article>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Note composer                                                      */
/* ------------------------------------------------------------------ */

function wireNoteModal() {
  const modal = $('#note-modal');
  const open = () => {
    modal.classList.add('is-open');
    document.body.classList.add('is-locked');
    $('#note-heading')?.focus();
  };
  const close = () => {
    modal.classList.remove('is-open');
    document.body.classList.remove('is-locked');
  };

  document.addEventListener('click', (e) => {
    if (e.target.closest('[data-new-note]')) open();
    if (e.target.closest('[data-close-modal]') || e.target === modal) close();
    if (e.target.closest('[data-ask-doubt]')) {
      toast('Doubt composer opened. Attach the question you are stuck on.', 'info');
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('is-open')) close();
  });

  $('#note-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const title = String(form.get('title') || '').trim();
    const body = String(form.get('body') || '').trim();
    if (!title || !body) return;

    $('#notes-list').insertAdjacentHTML(
      'afterbegin',
      `<article class="note-preview">
         <div class="row-between">
           <h3>${esc(title)}</h3>
           <span class="tiny subtle">Just now</span>
         </div>
         <p>${esc(body)}</p>
       </article>`
    );
    e.currentTarget.reset();
    close();
    toast('Note saved to your account.', 'success');
  });
}

/* ------------------------------------------------------------------ */
/* Boot                                                               */
/* ------------------------------------------------------------------ */

renderGreeting();
renderContinue();
renderStreak();
renderChart();
renderUpcoming();
renderBatchProgress();
renderNotes();
wireNoteModal();
