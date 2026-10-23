/** Catalogue: filtering, sorting, search and pagination over the batch list. */

import { $, $$, esc, live, qsParam, debounce } from './core.js';
import {
  mountChrome, batchCard, emptyState, skeletonBatchGrid, icon, thumbTone
} from './ui.js';
import { COURSES } from './data.js';

mountChrome('courses');

const PAGE_SIZE = 9;

const state = {
  query: qsParam('q') || '',
  exams: new Set(qsParam('exam') ? [qsParam('exam')] : []),
  subjects: new Set(qsParam('subject') ? [qsParam('subject')] : []),
  languages: new Set(qsParam('language') ? [qsParam('language')] : []),
  price: 'all',
  sort: qsParam('sort') || 'popular',
  page: 1,
  all: []
};

/* ------------------------------------------------------------------ */
/* Data                                                               */
/* ------------------------------------------------------------------ */

function normalise(raw, index) {
  const fixture =
    COURSES.find((c) => c.id === raw.id) ||
    COURSES.find((c) => c.slug === raw.slug) ||
    {};
  const subject = raw.subject || fixture.subject || 'General';
  return {
    ...fixture,
    ...raw,
    slug: raw.slug || fixture.slug || `course-${raw.id}`,
    subject,
    exam: fixture.exam || subject,
    faculty: fixture.faculty || [],
    rating: fixture.rating || 4.6,
    ratingCount: fixture.ratingCount || 0,
    learners: fixture.learners || 0,
    lessons: raw.lesson_count ?? fixture.lessons ?? 0,
    tests: fixture.tests ?? 0,
    language: fixture.language || raw.language || 'Hinglish',
    mrp: fixture.mrp || (raw.price ? Math.round(Number(raw.price) * 2.4) : 0),
    badge: fixture.badge || null,
    durationMonths: fixture.durationMonths || null,
    startsOn: fixture.startsOn || null,
    order: index
  };
}

async function loadCourses() {
  const grid = $('#course-grid');
  grid.innerHTML = skeletonBatchGrid(PAGE_SIZE);
  const { data } = await live('/courses/?page_size=60', COURSES);
  const rows = Array.isArray(data) ? data : data.results || [];
  state.all = rows.map(normalise);
  buildFacets();
  render();
}

/* ------------------------------------------------------------------ */
/* Facets                                                             */
/* ------------------------------------------------------------------ */

function buildFacets() {
  const count = (key) =>
    state.all.reduce((acc, course) => {
      const value = course[key];
      if (value) acc.set(value, (acc.get(value) || 0) + 1);
      return acc;
    }, new Map());

  renderFacet($('#filter-exam'), 'exams', count('exam'), state.exams);
  renderFacet($('#filter-subject'), 'subjects', count('subject'), state.subjects);
  renderFacet($('#filter-language'), 'languages', count('language'), state.languages);

  // Header quick chips
  const chips = $('#exam-chips');
  const exams = [...count('exam').keys()];
  chips.innerHTML = exams
    .map(
      (exam) =>
        `<button class="chip" data-chip-exam="${esc(exam)}" aria-pressed="${state.exams.has(exam)}">
           ${esc(exam)}
         </button>`
    )
    .join('');
}

function renderFacet(host, group, counts, selected) {
  if (!host) return;
  const entries = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  host.innerHTML = entries
    .map(
      ([value, n]) => `
      <label>
        <span>${esc(value)}</span>
        <span style="display:flex;align-items:center;gap:8px">
          <span class="filter-count">${n}</span>
          <input type="checkbox" value="${esc(value)}" data-facet="${group}" ${selected.has(value) ? 'checked' : ''}>
        </span>
      </label>`
    )
    .join('');

  host.addEventListener('change', (e) => {
    const input = e.target.closest('input[data-facet]');
    if (!input) return;
    const set = state[group];
    input.checked ? set.add(input.value) : set.delete(input.value);
    state.page = 1;
    render();
    syncChips();
  });
}

/* ------------------------------------------------------------------ */
/* Filtering                                                          */
/* ------------------------------------------------------------------ */

function matches(course) {
  if (state.query) {
    const haystack = `${course.title} ${course.subject} ${course.exam} ${course.description || ''}`.toLowerCase();
    if (!haystack.includes(state.query.toLowerCase())) return false;
  }
  if (state.exams.size && !state.exams.has(course.exam)) return false;
  if (state.subjects.size && !state.subjects.has(course.subject)) return false;
  if (state.languages.size && !state.languages.has(course.language)) return false;
  if (state.price === 'free' && Number(course.price) > 0) return false;
  if (state.price === 'paid' && Number(course.price) <= 0) return false;
  return true;
}

function sorted(list) {
  const copy = [...list];
  switch (state.sort) {
    case 'price-asc':
      return copy.sort((a, b) => Number(a.price) - Number(b.price));
    case 'price-desc':
      return copy.sort((a, b) => Number(b.price) - Number(a.price));
    case 'rating':
      return copy.sort((a, b) => b.rating - a.rating);
    case 'newest':
      return copy.sort((a, b) => new Date(b.startsOn || 0) - new Date(a.startsOn || 0));
    default:
      return copy.sort((a, b) => (b.learners || 0) - (a.learners || 0));
  }
}

/* ------------------------------------------------------------------ */
/* Render                                                             */
/* ------------------------------------------------------------------ */

function render() {
  const grid = $('#course-grid');
  const empty = $('#results-empty');
  const list = sorted(state.all.filter(matches));

  $('#result-count').innerHTML = `<strong>${list.length}</strong> batch${list.length === 1 ? '' : 'es'} found`;

  if (!list.length) {
    grid.innerHTML = '';
    empty.hidden = false;
    empty.innerHTML = emptyState({
      title: 'No batches match those filters',
      body: 'Try removing a filter or searching for a different exam.',
      actionLabel: 'Clear filters',
      actionHref: 'courses.html',
      iconName: 'filter'
    });
    $('#pagination').innerHTML = '';
    renderActiveFilters();
    return;
  }

  empty.hidden = true;
  const pages = Math.ceil(list.length / PAGE_SIZE);
  state.page = Math.min(state.page, pages);
  const start = (state.page - 1) * PAGE_SIZE;
  const pageItems = list.slice(start, start + PAGE_SIZE);

  grid.innerHTML = pageItems.map(batchCard).join('');
  renderPagination(pages);
  renderActiveFilters();
}

function renderPagination(pages) {
  const host = $('#pagination');
  if (!host) return;
  if (pages <= 1) {
    host.innerHTML = '';
    return;
  }
  const buttons = [];
  buttons.push(
    `<button class="page-btn" data-page="${state.page - 1}" ${state.page === 1 ? 'disabled' : ''} aria-label="Previous page">
       <svg style="width:15px;height:15px"><use href="#i-chevron-left"/></svg>
     </button>`
  );
  for (let i = 1; i <= pages; i += 1) {
    buttons.push(
      `<button class="page-btn" data-page="${i}" ${i === state.page ? 'aria-current="page"' : ''}>${i}</button>`
    );
  }
  buttons.push(
    `<button class="page-btn" data-page="${state.page + 1}" ${state.page === pages ? 'disabled' : ''} aria-label="Next page">
       <svg style="width:15px;height:15px"><use href="#i-chevron-right"/></svg>
     </button>`
  );
  host.innerHTML = buttons.join('');
}

function renderActiveFilters() {
  const host = $('#active-filters');
  if (!host) return;
  const chips = [];
  const add = (label, type, value) =>
    chips.push(
      `<button class="chip is-active" data-remove="${type}" data-value="${esc(value)}">
         ${esc(label)} ${icon('x')}
       </button>`
    );

  if (state.query) add(`“${state.query}”`, 'query', state.query);
  state.exams.forEach((v) => add(v, 'exams', v));
  state.subjects.forEach((v) => add(v, 'subjects', v));
  state.languages.forEach((v) => add(v, 'languages', v));
  if (state.price !== 'all') add(state.price === 'free' ? 'Free only' : 'Paid only', 'price', state.price);

  host.innerHTML = chips.join('');
}

function syncChips() {
  $$('[data-chip-exam]').forEach((chip) => {
    chip.setAttribute('aria-pressed', String(state.exams.has(chip.dataset.chipExam)));
  });
}

/* ------------------------------------------------------------------ */
/* Events                                                             */
/* ------------------------------------------------------------------ */

$('#sort-select')?.addEventListener('change', (e) => {
  state.sort = e.target.value;
  state.page = 1;
  render();
});

$('#clear-filters')?.addEventListener('click', () => {
  state.query = '';
  state.exams.clear();
  state.subjects.clear();
  state.languages.clear();
  state.price = 'all';
  state.page = 1;
  $$('#filter-panel input[type="checkbox"]').forEach((i) => (i.checked = false));
  const all = document.querySelector('input[name="price"][value="all"]');
  if (all) all.checked = true;
  history.replaceState(null, '', 'courses.html');
  render();
  syncChips();
});

$('#open-filters')?.addEventListener('click', () => {
  $('#filter-panel')?.classList.toggle('is-open');
});

$('#exam-chips')?.addEventListener('click', (e) => {
  const chip = e.target.closest('[data-chip-exam]');
  if (!chip) return;
  const exam = chip.dataset.chipExam;
  state.exams.has(exam) ? state.exams.delete(exam) : state.exams.add(exam);
  state.page = 1;
  $$('#filter-exam input').forEach((input) => {
    if (input.value === exam) input.checked = state.exams.has(exam);
  });
  syncChips();
  render();
});

$('#active-filters')?.addEventListener('click', (e) => {
  const chip = e.target.closest('[data-remove]');
  if (!chip) return;
  const { remove, value } = chip.dataset;
  if (remove === 'query') state.query = '';
  else if (remove === 'price') {
    state.price = 'all';
    const all = document.querySelector('input[name="price"][value="all"]');
    if (all) all.checked = true;
  } else state[remove].delete(value);
  state.page = 1;
  $$('#filter-panel input[type="checkbox"]').forEach((input) => {
    const group = input.dataset.facet;
    if (group && state[group]) input.checked = state[group].has(input.value);
  });
  syncChips();
  render();
});

$('#pagination')?.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-page]');
  if (!btn || btn.disabled) return;
  state.page = Number(btn.dataset.page);
  render();
  document.querySelector('.catalog-toolbar')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

document.querySelectorAll('input[name="price"]').forEach((input) => {
  input.addEventListener('change', (e) => {
    state.price = e.target.value;
    state.page = 1;
    render();
  });
});

// Live search from the header on desktop.
const headerSearch = document.querySelector('[data-global-search]');
if (headerSearch && state.query) headerSearch.value = state.query;
headerSearch?.addEventListener('input', debounce((e) => {
  state.query = e.target.value.trim();
  state.page = 1;
  render();
}, 260));

loadCourses();
