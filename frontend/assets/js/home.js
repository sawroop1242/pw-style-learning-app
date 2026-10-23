/** Home page: categories, trending batches, tests, testimonials, FAQ. */

import { $, esc, initials, live } from './core.js';
import {
  mountChrome, batchCard, testCard, icon, emptyState, skeletonBatchGrid, renderFooter, toast
} from './ui.js';
import { CATEGORIES, COURSES, TESTS, TESTIMONIALS, FAQS } from './data.js';

mountChrome('home');

/* ------------------------------------------------------------------ */
/* Categories                                                         */
/* ------------------------------------------------------------------ */

function renderCategories() {
  const host = $('#category-rail');
  if (!host) return;
  host.innerHTML = CATEGORIES.map(
    (cat) => `
    <a class="category-tile" href="courses.html?exam=${encodeURIComponent(cat.label)}">
      <span class="cat-icon">${icon(cat.icon)}</span>
      <strong>${esc(cat.label)}</strong>
      <small>${esc(cat.sub)}</small>
    </a>`
  ).join('');
}

/* ------------------------------------------------------------------ */
/* Batches                                                            */
/* ------------------------------------------------------------------ */

function normaliseCourse(raw, index = 0) {
  const fixture = COURSES.find((c) => c.id === raw.id) || {};
  return {
    ...fixture,
    ...raw,
    slug: raw.slug || fixture.slug || `course-${raw.id}`,
    faculty: fixture.faculty || [],
    rating: fixture.rating || 4.7,
    ratingCount: fixture.ratingCount || 0,
    learners: fixture.learners || 0,
    lessons: raw.lesson_count ?? fixture.lessons ?? 0,
    tests: fixture.tests ?? 0,
    language: fixture.language || 'Hinglish',
    mrp: fixture.mrp || (raw.price ? Math.round(Number(raw.price) * 2.4) : 0),
    exam: fixture.exam || raw.subject || 'General',
    badge: fixture.badge || null,
    durationMonths: fixture.durationMonths || null,
    rank: index
  };
}

async function renderTrending() {
  const host = $('#trending-rail');
  if (!host) return;
  host.innerHTML = `<div class="skeleton" style="height:420px;border-radius:20px"></div>`.repeat(3);

  const { data } = await live('/courses/?page_size=6', COURSES);
  const list = (Array.isArray(data) ? data : data.results || []).map(normaliseCourse);

  if (!list.length) {
    host.innerHTML = emptyState({
      title: 'No batches published yet',
      body: 'Once a batch is published it will appear here.',
      iconName: 'layers'
    });
    return;
  }

  host.innerHTML = list.slice(0, 6).map(batchCard).join('');

  // Rail arrows
  const rail = host;
  document.querySelector('[data-rail-prev]')?.addEventListener('click', () =>
    rail.scrollBy({ left: -320, behavior: 'smooth' })
  );
  document.querySelector('[data-rail-next]')?.addEventListener('click', () =>
    rail.scrollBy({ left: 320, behavior: 'smooth' })
  );
}

/* ------------------------------------------------------------------ */
/* Tests                                                              */
/* ------------------------------------------------------------------ */

async function renderTests() {
  const host = $('#home-tests');
  if (!host) return;
  host.innerHTML = `<div class="skeleton" style="height:250px;border-radius:20px"></div>`.repeat(3);

  const { data } = await live('/quizzes/?page_size=6', TESTS);
  const rows = Array.isArray(data) ? data : data.results || [];

  const list = rows.map((quiz, i) => {
    const fixture = TESTS.find((t) => t.id === quiz.id) || TESTS[i] || TESTS[0];
    return {
      ...fixture,
      id: quiz.id ?? fixture.id,
      title: quiz.title || fixture.title,
      duration: quiz.duration_minutes || fixture.duration,
      questions: quiz.question_count ?? fixture.questions,
      startsAt: quiz.opens_at || fixture.startsAt,
      price: quiz.price ?? fixture.price
    };
  });

  host.innerHTML = list.slice(0, 3).map(testCard).join('');
}

/* ------------------------------------------------------------------ */
/* Testimonials & FAQ                                                 */
/* ------------------------------------------------------------------ */

function renderTestimonials() {
  const host = $('#testimonials');
  if (!host) return;
  host.innerHTML = TESTIMONIALS.map(
    (t) => `
    <figure class="card card-pad" style="display:grid;gap:14px;margin:0">
      <div class="rating">${icon('star')}${icon('star')}${icon('star')}${icon('star')}${icon('star')}</div>
      <blockquote style="margin:0;font-size:14px;line-height:1.75;color:var(--text)">“${esc(t.quote)}”</blockquote>
      <figcaption class="row" style="gap:10px">
        <span class="avatar avatar-${t.tone === 'violet' ? '' : t.tone}">${esc(t.initials)}</span>
        <span>
          <strong style="display:block;font-size:13px;color:var(--text-strong)">${esc(t.name)}</strong>
          <small class="tiny subtle">${esc(t.meta)}</small>
        </span>
      </figcaption>
    </figure>`
  ).join('');
}

function renderFaq() {
  const host = $('#faq-list');
  if (!host) return;
  host.innerHTML = FAQS.map(
    (item, i) => `
    <div class="acc-item">
      <button class="acc-head" aria-expanded="${i === 0}" aria-controls="faq-panel-${i}" id="faq-btn-${i}">
        <span class="acc-title">${esc(item.q)}</span>
        <svg class="acc-chevron"><use href="#i-chevron-down"/></svg>
      </button>
      <div class="acc-panel" id="faq-panel-${i}" role="region" aria-labelledby="faq-btn-${i}" ${i === 0 ? '' : 'hidden'}>
        <p style="padding:4px 16px 16px;font-size:14px;line-height:1.75;color:var(--text-muted);margin:0">${esc(item.a)}</p>
      </div>
    </div>`
  ).join('');

  host.addEventListener('click', (e) => {
    const btn = e.target.closest('.acc-head');
    if (!btn) return;
    const open = btn.getAttribute('aria-expanded') === 'true';
    host.querySelectorAll('.acc-head').forEach((b) => {
      b.setAttribute('aria-expanded', 'false');
      b.nextElementSibling.hidden = true;
    });
    if (!open) {
      btn.setAttribute('aria-expanded', 'true');
      btn.nextElementSibling.hidden = false;
    }
  });
}

/* ------------------------------------------------------------------ */
/* Hero search & PWA install                                          */
/* ------------------------------------------------------------------ */

$('#hero-search')?.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = new FormData(e.currentTarget).get('q')?.toString().trim();
  location.href = q ? `courses.html?q=${encodeURIComponent(q)}` : 'courses.html';
});

let installPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  installPrompt = e;
});

document.addEventListener('click', async (e) => {
  if (!e.target.closest('[data-install-pwa]')) return;
  if (!installPrompt) {
    toast('Use your browser menu → “Install app” to add StudySpace.', 'info');
    return;
  }
  installPrompt.prompt();
  const { outcome } = await installPrompt.userChoice;
  if (outcome === 'accepted') toast('StudySpace installed.', 'success');
  installPrompt = null;
});

/* ------------------------------------------------------------------ */
/* Boot                                                               */
/* ------------------------------------------------------------------ */

renderCategories();
renderTestimonials();
renderFaq();
renderTrending();
renderTests();

