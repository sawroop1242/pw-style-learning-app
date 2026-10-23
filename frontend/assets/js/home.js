/**
 * Home page — featured batch, exam index, trending batches, free mocks, FAQ.
 * Reads go through `live()` so the page works against the API or the fixtures.
 */

import { $, $$, esc, live, money, compact, discountPercent, adaptCourse, adaptTest } from './core.js';
import { mountChrome, batchCard, testCard, icon, toast } from './ui.js';
import { CATEGORIES, COURSES, TESTS, FAQS } from './data.js';

mountChrome('home');

/* ------------------------------------------------------------------ */
/* Featured batch                                                     */
/* ------------------------------------------------------------------ */

async function renderFeatured() {
  const host = $('#featured-batch');
  if (!host) return;

  const { data } = await live('/courses/?page_size=1&sort=-learners', COURSES[0]);
  const course = Array.isArray(data) ? data[0] : data.results?.[0] || data;
  if (!course?.title) return;

  const off = discountPercent(course.price, course.mrp);

  host.innerHTML = `
    <div class="mc-head">
      <span>Featured batch</span>
      ${course.pricing_mode === 'free'
        ? '<span class="badge badge-free">Free</span>'
        : '<span class="badge badge-live">Enrolling</span>'}
    </div>
    <div class="mc-body">
      <p class="tiny subtle" style="letter-spacing:.08em;text-transform:uppercase">${esc(course.exam || '')}</p>
      <h2>${esc(course.title)}</h2>
      <div class="mc-meta">
        <div>${icon('play')} ${esc(course.lessons || 0)} lessons</div>
        <div>${icon('file-text')} ${esc(course.tests || 0)} tests</div>
        <div>${icon('users')} ${compact(course.learners)} enrolled</div>
      </div>
      <div class="mc-meta">
        <div>${icon('star')} ${(course.rating || 4.7).toFixed(1)} · ${compact(course.ratingCount)} ratings</div>
        <div>${icon('globe')} ${esc(course.language || 'English')}</div>
      </div>
    </div>
    <div class="mc-foot">
      <span class="mc-price">
        ${money(course.price)}
        ${course.mrp > course.price ? `<s>${money(course.mrp)}</s>` : ''}
        ${off ? `<span class="badge badge-hot" style="margin-left:8px">${off}% off</span>` : ''}
      </span>
      <a class="btn btn-primary btn-sm" href="course.html?slug=${encodeURIComponent(course.slug)}">
        View batch
      </a>
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Exam index                                                         */
/* ------------------------------------------------------------------ */

function renderCategories() {
  const host = $('#category-rail');
  if (!host) return;

  host.innerHTML = CATEGORIES.map(
    (cat) => `
    <a class="category-tile" href="courses.html?exam=${encodeURIComponent(cat.label)}">
      <span class="cat-icon">${icon(cat.icon)}</span>
      <span>
        <strong>${esc(cat.label)}</strong>
        <small>${esc(cat.sub)}</small>
      </span>
    </a>`
  ).join('');
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

renderCategories();
renderFeatured();
renderTrending();
renderTests();
renderFaq();
