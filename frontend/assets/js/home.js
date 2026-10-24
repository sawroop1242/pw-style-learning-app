/**
 * Home page — welcome, hero, today's classes, Khazana, recommended batches,
 * free mocks, announcements and FAQ. Catalogue reads go through `live()` so
 * the page works against the API or the bundled fixtures.
 */

import { $, $$, esc, live, initials, storage, adaptCourse, adaptTest } from './core.js';
import { mountChrome, batchCard, testCard, todayClassCard, icon, toast } from './ui.js';
import { COURSES, TESTS, FAQS, TODAY_CLASSES, SUBJECTS, COMMUNITY } from './data.js';

mountChrome('home');

/* ------------------------------------------------------------------ */
/* Welcome line                                                       */
/* ------------------------------------------------------------------ */

function renderWelcome() {
  const user = storage.user;
  const name = user?.username || 'Student';
  const avatar = document.querySelector('[data-welcome-avatar]');
  if (avatar) avatar.textContent = initials(name);
  const title = $('#welcome-title');
  if (title) {
    const first = name.split(/[\s._-]/)[0];
    title.innerHTML = `Hello, ${esc(first.charAt(0).toUpperCase() + first.slice(1))}! <span aria-hidden="true">👋</span>`;
  }
}

/* ------------------------------------------------------------------ */
/* Today's classes                                                    */
/* ------------------------------------------------------------------ */

function renderToday() {
  const host = $('#today-grid');
  if (!host) return;
  host.innerHTML = TODAY_CLASSES.map(todayClassCard).join('');
}

/* ------------------------------------------------------------------ */
/* Khazana — subject tiles with chapter and lecture counts            */
/* ------------------------------------------------------------------ */

function renderKhazana() {
  const host = $('#khazana-grid');
  if (!host) return;
  host.innerHTML = SUBJECTS.slice(0, 8)
    .map(
      (subject) => `
      <a class="subject-tile" href="khazana.html?subject=${encodeURIComponent(subject.name)}">
        <span class="subject-icon tone-${subject.tone}">${icon(subject.icon)}</span>
        <span class="subject-body">
          <strong>${esc(subject.name)}</strong>
          <small>${subject.chapters} ${subject.chapters === 1 ? 'chapter' : 'chapters'} · ${subject.lectures} ${subject.lectures === 1 ? 'lecture' : 'lectures'}</small>
        </span>
      </a>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Announcements                                                      */
/* ------------------------------------------------------------------ */

function renderNotices() {
  const host = $('#home-notices');
  if (!host) return;
  const ICON = ['megaphone', 'calendar', 'sparkles'];
  host.innerHTML = COMMUNITY.announcements
    .map(
      (item, i) => `
      <li class="notice-item">
        <span class="notice-icon">${icon(ICON[i % ICON.length])}</span>
        <div>
          <strong>${esc(item.title)}</strong>
          <p>${esc(item.body)}</p>
        </div>
      </li>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Trending batches & free mocks                                      */
/* ------------------------------------------------------------------ */

async function renderTrending() {
  const host = $('#trending-grid');
  if (!host) return;

  const { data } = await live('/courses/?page_size=3&sort=-learners', COURSES);
  const rows = (Array.isArray(data) ? data : data.results || []).slice(0, 3);
  host.innerHTML = rows.map((course) => batchCard(adaptCourse(course))).join('');
}

async function renderTests() {
  const host = $('#home-tests');
  if (!host) return;

  const { data } = await live('/quizzes/?page_size=3&sort=-attempts', TESTS);
  const rows = (Array.isArray(data) ? data : data.results || []).slice(0, 3);
  host.innerHTML = rows.map((test) => testCard(adaptTest(test))).join('');
}

/* ------------------------------------------------------------------ */
/* FAQ                                                                */
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
    // Single-open accordion keeps the page calm.
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
/* Search                                                             */
/* ------------------------------------------------------------------ */

const searchForm = $('#hero-search');
searchForm?.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = new FormData(searchForm).get('q')?.toString().trim();
  location.href = q ? `courses.html?q=${encodeURIComponent(q)}` : 'courses.html';
});

/* ------------------------------------------------------------------ */
/* Boot                                                               */
/* ------------------------------------------------------------------ */

renderWelcome();
renderToday();
renderKhazana();
renderNotices();
renderTrending();
renderTests();
renderFaq();
