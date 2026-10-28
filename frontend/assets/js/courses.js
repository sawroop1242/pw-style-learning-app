/**
 * Catalogue: search, subject/price filters, sorting and pagination.
 *
 * Every control is a server query — `search`, `subject`, `pricing_mode`,
 * `mine`, `ordering`, `page` — so the grid can only ever show rows the API
 * returned. Facets are built from those rows, and the result count is the
 * server's `count`, not the number of cards on screen.
 */

import {
  $, $$, esc, getJson, rows, apiQuery, qsParam, debounce, initials, storage,
  isSignedIn, adaptCourse
} from './core.js';
import {
  mountChrome, batchCard, emptyState, errorState, skeletonBatchGrid, icon, wireRetry
} from './ui.js';

mountChrome('courses');

const avatar = document.querySelector('[data-welcome-avatar]');
if (avatar) avatar.textContent = initials(storage.user?.username || 'Student').slice(0, 1);

const PAGE_SIZE = 9;

/** Sort keys the API advertises in `CourseViewSet.ordering_fields`. */
const SORTS = {
  position: 'position',
  newest: '-created_at',
  title: 'title',
  price: 'price'
};

const state = {
  query: qsParam('q') || '',
  subjects: new Set(),
  price: 'all',
  mine: qsParam('mine') === '1',
  sort: SORTS[qsParam('sort')] ? qsParam('sort') : 'position',
  page: 1,
  count: 0,
  all: []
};

/* ------------------------------------------------------------------ */
/* Queries                                                            */
/* ------------------------------------------------------------------ */

function listQuery() {
  const params = {
    page: state.page,
    page_size: PAGE_SIZE,
    ordering: SORTS[state.sort],
    search: state.query || undefined,
    subject: [...state.subjects][0] || undefined,
    mine: state.mine ? 1 : undefined
  };
  if (state.price === 'free') params.pricing_mode = 'free';
  if (state.price === 'paid') params.pricing_mode = 'paid';
  return apiQuery(params);
}

async function fetchCourses(params) {
  const payload = await getJson(`/courses/${params}`);
  return { list: rows(payload).map(adaptCourse), count: payload.count ?? rows(payload).length };
}

/* ------------------------------------------------------------------ */
/* The main grid                                                      */
/* ------------------------------------------------------------------ */

async function loadCourses() {
  const grid = $('#course-grid');
  const empty = $('#course-empty');
  grid.innerHTML = skeletonBatchGrid(PAGE_SIZE);
  empty.hidden = true;
  $('#result-count').textContent = 'Loading batches…';

  try {
    const { list, count } = await fetchCourses(listQuery());
    state.all = list;
    state.count = count;
  } catch (err) {
    grid.innerHTML = '';
    $('#result-count').textContent = '';
    empty.hidden = false;
    empty.innerHTML = errorState({
      title: 'Catalogue unavailable',
      body: err?.message || 'The batch list could not be loaded.'
    });
    return;
  }

  $('#result-count').textContent = `${state.count} ${state.count === 1 ? 'batch' : 'batches'}`;
  buildFacets();
  render();
}

function render() {
  const grid = $('#course-grid');
  const empty = $('#course-empty');
  const filtered = Boolean(state.query || state.subjects.size || state.price !== 'all' || state.mine);

  if (!state.all.length) {
    grid.innerHTML = '';
    empty.hidden = false;
    empty.innerHTML = filtered
      ? emptyState({
          title: 'No batches match these filters',
          body: 'Clear a filter, or search for a different subject.',
          actionLabel: 'Reset filters',
          actionHref: 'courses.html',
          iconName: 'search'
        })
      : emptyState({
          title: 'No batches published yet',
          body: 'The catalogue is empty. A published batch appears here immediately.',
          iconName: 'book'
        });
    renderPager();
    return;
  }

  empty.hidden = true;
  grid.innerHTML = state.all.map(batchCard).join('');
  renderPager();
}

function renderPager() {
  const pager = $('#course-pager');
  if (!pager) return;
  const pages = Math.max(1, Math.ceil(state.count / PAGE_SIZE));
  pager.innerHTML =
    pages < 2
      ? ''
      : `
    <div class="row" style="gap:10px;justify-content:center;align-items:center">
      <button class="btn btn-ghost btn-sm" type="button" data-page="prev" ${state.page === 1 ? 'disabled' : ''}>
        ${icon('chevron-left')} Previous
      </button>
      <span class="small muted">Page ${state.page} of ${pages}</span>
      <button class="btn btn-ghost btn-sm" type="button" data-page="next" ${state.page >= pages ? 'disabled' : ''}>
        Next ${icon('chevron-right')}
      </button>
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Facets                                                             */
/* ------------------------------------------------------------------ */

function buildFacets() {
  const host = $('#filter-subject');
  const counts = state.all.reduce((acc, course) => {
    if (course.subject) acc.set(course.subject, (acc.get(course.subject) || 0) + 1);
    return acc;
  }, new Map());

  if (!counts.size) {
    host.innerHTML = '<p class="tiny subtle" style="margin:0">No subjects on this page.</p>';
    return;
  }

  host.innerHTML = [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(
      ([subject, n]) => `
      <label>
        <span>${esc(subject)}</span>
        <span style="display:flex;align-items:center;gap:8px">
          <span class="filter-count">${n}</span>
          <input type="checkbox" value="${esc(subject)}" data-subject ${state.subjects.has(subject) ? 'checked' : ''}>
        </span>
      </label>`
    )
    .join('');
}

/* ------------------------------------------------------------------ */
/* Controls                                                           */
/* ------------------------------------------------------------------ */

const search = $('#course-search');
if (search) {
  search.value = state.query;
  search.addEventListener(
    'input',
    debounce(() => {
      state.query = search.value.trim();
      state.page = 1;
      loadCourses();
    }, 320)
  );
}

$('#course-sort')?.addEventListener('change', (event) => {
  state.sort = event.target.value;
  state.page = 1;
  loadCourses();
});

$('#filter-subject')?.addEventListener('change', (event) => {
  const input = event.target.closest('input[data-subject]');
  if (!input) return;
  // One subject per request: the API filters on a single value.
  state.subjects.clear();
  if (input.checked) state.subjects.add(input.value);
  state.page = 1;
  loadCourses();
});

$('#filter-price')?.addEventListener('change', (event) => {
  const input = event.target.closest('input[data-price]');
  if (!input) return;
  state.price = input.value;
  state.page = 1;
  loadCourses();
});

$('#clear-filters')?.addEventListener('click', () => {
  state.query = '';
  state.subjects.clear();
  state.price = 'all';
  state.mine = false;
  state.page = 1;
  if (search) search.value = '';
  $$('#filter-price input').forEach((input) => {
    input.checked = input.value === 'all';
  });
  selectTab(0);
  loadCourses();
});

document.addEventListener('click', (event) => {
  const page = event.target.closest('[data-page]');
  if (!page) return;
  state.page += page.dataset.page === 'next' ? 1 : -1;
  loadCourses();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

/* ------------------------------------------------------------------ */
/* Tabs: all batches / my batches                                     */
/* ------------------------------------------------------------------ */

const TABS = [
  ['panel-all', 'all'],
  ['panel-mine', 'mine']
];

function selectTab(index) {
  $$('.tabs .tab').forEach((tab, i) => {
    const selected = i === index;
    tab.setAttribute('aria-selected', String(selected));
    const panel = document.getElementById(TABS[i][0]);
    if (panel) panel.hidden = !selected;
  });
  if (TABS[index][1] === 'mine') loadMine();
}

$$('.tabs .tab').forEach((tab, i) => {
  tab.addEventListener('click', () => selectTab(i));
  tab.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const tabs = $$('.tabs .tab');
    const next = (i + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    selectTab(next);
  });
});

/**
 * My batches = published free batches plus paid batches this account holds an
 * active grant for. Signed out, there is no "mine", so the tab says so instead
 * of showing everything twice.
 */
async function loadMine() {
  const grid = $('#my-grid');
  const empty = $('#my-empty');
  if (!grid) return;

  if (!isSignedIn()) {
    grid.innerHTML = '';
    empty.hidden = false;
    empty.innerHTML = emptyState({
      title: 'Sign in to see your batches',
      body: 'Every free batch is open to you without an account. Signing in also shows the paid batches you have unlocked.',
      actionLabel: 'Sign in',
      actionHref: 'login.html?next=courses.html',
      iconName: 'user'
    });
    return;
  }

  grid.innerHTML = skeletonBatchGrid(3);
  empty.hidden = true;
  try {
    const { list } = await fetchCourses(apiQuery({ page_size: 60, mine: 1 }));
    if (!list.length) {
      grid.innerHTML = '';
      empty.hidden = false;
      empty.innerHTML = emptyState({
        title: 'No batches yet',
        body: 'Redeem an access code on a batch page to unlock it, or start with any free batch.',
        actionLabel: 'Browse the catalogue',
        actionHref: 'courses.html',
        iconName: 'book'
      });
      return;
    }
    grid.innerHTML = list.map(batchCard).join('');
  } catch (err) {
    grid.innerHTML = '';
    empty.hidden = false;
    empty.innerHTML = errorState({ title: 'Your batches could not be loaded', body: err?.message });
  }
}

wireRetry();
if (state.mine) selectTab(1);
loadCourses();
