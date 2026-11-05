/**
 * Home page.
 *
 * Four API reads, four renders: the learner's timetable, the published
 * catalogue, the published tests and the announcement feed. Nothing is
 * pre-filled — an empty catalogue renders an empty state, and a failed request
 * renders an error with a retry, because both are more useful than invented
 * rows.
 */

import {
  $, $$, esc, getJson, rows, initials, storage, isSignedIn, adaptCourse, adaptTest
} from './core.js';
import {
  mountChrome, batchCard, testCard, scheduleRow, icon, toast, errorState, emptyState,
  wireRetry
} from './ui.js';
import { FAQS } from './content.js';

mountChrome('home');

/* ------------------------------------------------------------------ */
/* Welcome line                                                       */
/* ------------------------------------------------------------------ */

function renderWelcome() {
  const user = storage.user;
  const name = user?.username || 'Student';
  const avatar = document.querySelector('[data-welcome-avatar]');
  if (avatar) avatar.textContent = initials(name).slice(0, 1);
  const title = $('#welcome-title');
  if (title) {
    const first = name.split(/[\s._-]/)[0] || 'Student';
    // An inline icon, not an emoji: a host without an emoji font paints 👋 as
    // an empty box, and the sprite always renders.
    title.innerHTML = `Hello, ${esc(first.charAt(0).toUpperCase() + first.slice(1))}! ${icon('sparkles')}`;
  }
  const sub = document.querySelector('[data-welcome-sub]');
  if (sub && user) sub.textContent = 'Your batches, tests and notes are on your dashboard.';
}

/* ------------------------------------------------------------------ */
/* Sections                                                           */
/* ------------------------------------------------------------------ */

function fill(host, html, { empty, emptyBody, actionLabel, actionHref, iconName = 'book' }) {
  if (!host) return;
  host.innerHTML = html || emptyState({ title: empty, body: emptyBody, actionLabel, actionHref, iconName });
}

/**
 * "Today's classes" is a timetable, not a feed of uploads.
 *
 * It used to list lessons *created* today, so a recording pushed at 11pm for
 * next week's class counted as today's and the class being taught this evening
 * did not appear at all. `/schedule/` answers the real question — what is on,
 * when — and marks a class live only inside its own window.
 *
 * The seven-day payload is requested once and rendered in three parts: today,
 * "later this week", and nothing at all. A quiet day is stated as a quiet day,
 * with the next class named rather than a made-up row.
 */
async function loadSchedule() {
  const host = $('#schedule-list');
  if (!host) return;
  const summary = $('#schedule-summary');

  if (!isSignedIn()) {
    if (summary) summary.textContent = '';
    host.innerHTML = emptyState({
      title: 'Sign in to see your timetable',
      body: 'Classes appear here for the batches you have joined. A guest has no batches yet.',
      actionLabel: 'Sign in',
      actionHref: 'login.html?next=index.html',
      iconName: 'calendar'
    });
    return;
  }

  let payload;
  try {
    payload = await getJson('/schedule/?days=7');
  } catch (err) {
    if (summary) summary.textContent = '';
    host.innerHTML = errorState({
      title: 'Timetable unavailable',
      body: err?.message || 'The schedule could not be loaded.'
    });
    return;
  }

  const groups = Array.isArray(payload.groups) ? payload.groups : [];
  const today = groups.find((group) => group.is_today);
  const todays = today ? today.classes : [];
  const later = groups
    .flatMap((group) => group.classes)
    .filter((entry) => entry.status !== 'ended' && !todays.includes(entry))
    .slice(0, 3);

  if (summary) {
    const counts = payload.counts || {};
    summary.textContent = !counts.total
      ? 'Nothing scheduled in the next seven days'
      : [
          `${counts.today} ${counts.today === 1 ? 'class' : 'classes'} today`,
          counts.live ? `${counts.live} live now` : '',
          counts.upcoming ? `${counts.upcoming} still to come this week` : ''
        ].filter(Boolean).join(' · ');
  }

  if (!(payload.counts || {}).total) {
    host.innerHTML = emptyState({
      title: 'Nothing on the timetable',
      body: 'No class in your batches has an air time in the next seven days. Joined a batch recently? Its schedule shows up here as soon as faculty sets one.',
      actionLabel: 'Open my batches',
      actionHref: 'courses.html',
      iconName: 'calendar'
    });
    return;
  }

  const dayHead = (label, isToday) =>
    `<p class="schedule-day ${isToday ? 'is-today' : ''}">${esc(label)}</p>`;

  // Rows print on the batch clock, the same one the day headings were cut on.
  const zone = payload.timezone || '';

  const parts = [];
  if (todays.length) {
    parts.push(dayHead(today.is_today ? 'Today' : today.label, true));
    parts.push(todays.map((entry) => scheduleRow(entry, { timeZone: zone })).join(''));
  } else {
    parts.push(`<p class="schedule-quiet">No classes today.</p>`);
  }
  if (later.length) {
    parts.push(dayHead('Later this week', false));
    parts.push(later.map((entry) => scheduleRow(entry, { timeZone: zone })).join(''));
  }
  host.innerHTML = parts.join('');
}

async function loadBatches() {
  const host = $('#trending-grid');
  if (!host) return;
  try {
    const payload = await getJson('/courses/?page_size=3');
    const list = rows(payload).map(adaptCourse);
    fill(host, list.map(batchCard).join(''), {
      empty: 'No batches published yet',
      emptyBody: 'The catalogue is empty. Once a batch is published it shows up here.',
      actionLabel: 'Open the catalogue',
      actionHref: 'courses.html'
    });
  } catch {
    host.innerHTML = errorState({ title: 'Catalogue unavailable' });
  }
}

async function loadTests() {
  const host = $('#home-tests');
  if (!host) return;
  try {
    const payload = await getJson('/quizzes/?page_size=3');
    const list = rows(payload).map(adaptTest);
    fill(host, list.map(testCard).join(''), {
      empty: 'No tests published yet',
      emptyBody: 'Timed mocks appear here once a paper is published.',
      actionLabel: 'All tests',
      actionHref: 'tests.html',
      iconName: 'file-text'
    });
  } catch {
    host.innerHTML = errorState({ title: 'Tests unavailable' });
  }
}

async function loadNotices() {
  const host = $('#home-notices');
  if (!host) return;
  try {
    const payload = await getJson('/community/?page_size=3');
    const list = rows(payload);
    if (!list.length) {
      host.innerHTML = `<li class="notice-item"><span class="notice-icon">${icon('bell')}</span>
        <div><strong>No announcements yet</strong><p>Batch notices from your faculty will appear here.</p></div></li>`;
      return;
    }
    host.innerHTML = list
      .map(
        (item) => `
      <li class="notice-item">
        <span class="notice-icon">${icon(item.pinned ? 'bell' : 'megaphone')}</span>
        <div>
          <strong>${esc(item.title)}</strong>
          <p>${esc(item.body)}</p>
        </div>
      </li>`
      )
      .join('');
  } catch {
    host.innerHTML = `<li class="notice-item"><span class="notice-icon">${icon('alert')}</span>
      <div><strong>Announcements unavailable</strong><p>The feed could not be loaded right now.</p></div></li>`;
  }
}

/* ------------------------------------------------------------------ */
/* FAQ (editorial copy, not data)                                     */
/* ------------------------------------------------------------------ */

function renderFaq() {
  const host = $('#faq-list');
  if (!host) return;

  host.innerHTML = FAQS.map(
    (item, i) => `
    <div class="acc-item">
      <button class="acc-head" type="button" aria-expanded="${i === 0}" aria-controls="faq-panel-${i}">
        <span class="acc-title">${esc(item.q)}</span>
        <svg class="acc-chevron"><use href="#i-chevron-down"/></svg>
      </button>
      <div class="acc-panel" id="faq-panel-${i}" ${i === 0 ? '' : 'hidden'}>
        <p class="acc-text">${esc(item.a)}</p>
      </div>
    </div>`
  ).join('');

  host.addEventListener('click', (e) => {
    const head = e.target.closest('.acc-head');
    if (!head) return;
    const isOpen = head.getAttribute('aria-expanded') === 'true';
    $$('.acc-head', host).forEach((other) => {
      const panel = document.getElementById(other.getAttribute('aria-controls'));
      other.setAttribute('aria-expanded', 'false');
      if (panel) panel.hidden = true;
    });
    if (!isOpen) {
      head.setAttribute('aria-expanded', 'true');
      const panel = document.getElementById(head.getAttribute('aria-controls'));
      if (panel) panel.hidden = false;
    }
  });
}

/* ------------------------------------------------------------------ */
/* Install prompt                                                     */
/* ------------------------------------------------------------------ */

let installEvent = null;
window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  installEvent = event;
});

document.addEventListener('click', async (e) => {
  if (!e.target.closest('[data-install-pwa]')) return;
  if (installEvent) {
    installEvent.prompt();
    const { outcome } = await installEvent.userChoice;
    toast(outcome === 'accepted' ? 'Installing StudySpace…' : 'You can install any time from the menu.', 'info');
    installEvent = null;
  } else {
    toast('Use your browser menu → “Install app” or “Add to Home screen”.', 'info', 6000);
  }
});

/* ------------------------------------------------------------------ */
/* Boot                                                               */
/* ------------------------------------------------------------------ */

renderWelcome();
renderFaq();
wireRetry();
loadSchedule();
loadBatches();
loadTests();
loadNotices();
