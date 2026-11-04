/**
 * Catalogue: faceted search, sorting and pagination.
 *
 * Every control is a server query — `search`, `exam`, `subject`, `level`,
 * `pricing_mode`, `mine`, `ordering`, `page` — so the grid can only ever show
 * rows the API returned. The filter counts come from `/api/courses/facets/`,
 * which counts each group with every *other* group applied, so a ticked value
 * never hides its siblings and every number answers "what would this add?".
 *
 * The state lives in the URL: the page can be reloaded, bookmarked or sent to
 * a friend and the same filters come back.
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

/** The checkbox groups, in the order the panel prints them. */
const FACET_GROUPS = [
  ['exam', 'Exam'],
  ['subject', 'Subject'],
  ['level', 'Level']
];

const PRICE_LABELS = { free: 'Free', paid: 'Paid' };

/** Every value chosen for one facet: `?exam=JEE&exam=NEET`. */
const chosen = (key) => new URLSearchParams(location.search).getAll(key);

const state = {
  query: qsParam('q') || '',
  selected: {
    exam: new Set(chosen('exam')),
    subject: new Set(chosen('subject')),
    level: new Set(chosen('level'))
  },
  price: PRICE_LABELS[qsParam('price')] ? qsParam('price') : 'all',
  mine: qsParam('mine') === '1',
  sort: SORTS[qsParam('sort')] ? qsParam('sort') : 'position',
  page: Math.max(1, Number(qsParam('page')) || 1),
  count: 0,
  all: [],
  facets: null
};

/** Ticked boxes + a price band: what the Filters badge counts. */
function filterCount() {
  return (
    FACET_GROUPS.reduce((total, [field]) => total + state.selected[field].size, 0) +
    (state.price === 'all' ? 0 : 1)
  );
}

function hasFilters() {
  return filterCount() > 0 || Boolean(state.query) || state.mine;
}


/* ------------------------------------------------------------------ */
/* Queries                                                            */
/* ------------------------------------------------------------------ */

/**
 * The query the API is asked.
 *
 * `apiQuery` sets one value per key, but a checkbox group is a list:
 * `?subject=Physics&subject=Biology` means "either", which is exactly what
 * ticking two boxes means. So the string is built here.
 */
function catalogQuery({ withPage = true } = {}) {
  const params = new URLSearchParams();
  if (withPage) {
    params.set('page', String(state.page));
    params.set('page_size', String(PAGE_SIZE));
  }
  if (withPage) params.set('ordering', SORTS[state.sort]);
  if (state.query) params.set('search', state.query);
  if (state.mine) params.set('mine', '1');
  if (state.price !== 'all') params.set('pricing_mode', state.price);
  for (const [field] of FACET_GROUPS) {
    for (const value of state.selected[field]) params.append(field, value);
  }
  return `?${params.toString()}`;
}

async function fetchCourses(query) {
  const payload = await getJson(`/courses/${query}`);
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
    // The grid and the counts are asked together: a panel that lags the list by
    // a request is a panel that disagrees with what is on screen.
    const [list, facets] = await Promise.all([
      fetchCourses(catalogQuery()),
      getJson(`/courses/facets/${catalogQuery({ withPage: false })}`)
    ]);
    state.all = list.list;
    state.count = list.count;
    state.facets = facets;
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
  renderFacetPanel();
  renderChips();
  render();
  syncUrl();
}

function render() {
  const grid = $('#course-grid');
  const empty = $('#course-empty');
  if (!state.all.length) {
    grid.innerHTML = '';
    empty.hidden = false;
    empty.innerHTML = hasFilters()
      ? `<div class="empty-state">
          ${icon('search')}
          <h3>No batches match these filters</h3>
          <p>Every filter narrows the catalogue. Widen one, or clear them all and start again.</p>
          <button class="btn btn-primary" type="button" data-clear-filters>Clear filters</button>
        </div>`
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
/* The filter panel and the chips                                     */
/* ------------------------------------------------------------------ */

function optionRow({ field, value, label, count, checked, type }) {
  return `
    <label>
      <span>${esc(label)}</span>
      <span class="filter-option-end">
        <span class="filter-count">${count}</span>
        <input type="${type}" name="${field}" value="${esc(value)}"
               data-filter="${field}"${checked ? ' checked' : ''}>
      </span>
    </label>`;
}

/**
 * Draw the groups from the server's counts.
 *
 * A group with no values is not drawn at all: an empty "Exam" heading with
 * nothing under it is a promise the catalogue cannot keep. A value that is
 * ticked but no longer matches (because another filter narrowed the set) stays
 * visible, because a filter you cannot see is a filter you cannot remove.
 */
function renderFacetPanel() {
  const host = $('#facet-groups');
  if (!host) return;
  const facets = state.facets?.facets || {};

  host.innerHTML = FACET_GROUPS.map(([field, label]) => {
    const values = facets[field] || [];
    const extra = [...state.selected[field]]
      .filter((value) => !values.some((row) => row.value.toLowerCase() === value.toLowerCase()))
      .map((value) => ({ value, count: 0 }));
    if (!values.length && !extra.length) return '';
    return `
      <div class="filter-group">
        <h2>${label}</h2>
        <div class="filter-list">
          ${values
            .map((row) =>
              optionRow({
                field,
                value: row.value,
                label: row.value,
                count: row.count,
                checked: state.selected[field].has(row.value),
                type: 'checkbox'
              })
            )
            .join('')}
          ${extra
            .map((row) =>
              optionRow({ field, value: row.value, label: row.value, count: 0, checked: true, type: 'checkbox' })
            )
            .join('')}
        </div>
      </div>`;
  }).join('');

  const priceHost = $('#facet-price');
  if (priceHost) {
    const rows = facets.pricing_mode || [];
    const total = rows.reduce((sum, row) => sum + row.count, 0);
    priceHost.innerHTML =
      optionRow({ field: 'price', value: 'all', label: 'All batches', count: total, checked: state.price === 'all', type: 'radio' }) +
      rows
        .map((row) =>
          optionRow({
            field: 'price',
            value: row.value,
            label: PRICE_LABELS[row.value] || row.value,
            count: row.count,
            checked: state.price === row.value,
            type: 'radio'
          })
        )
        .join('');
  }
  updateBadge();
}

/** The chips above the grid: one per active filter, each one removable. */
function renderChips() {
  const host = $('#active-filters');
  if (!host) return;

  const chips = [];
  for (const [field, label] of FACET_GROUPS) {
    for (const value of state.selected[field]) chips.push({ field, value, label: `${label}: ${value}` });
  }
  if (state.price !== 'all') {
    chips.push({ field: 'price', value: state.price, label: `Price: ${PRICE_LABELS[state.price]}` });
  }
  if (state.query) chips.push({ field: 'search', value: state.query, label: `Search: “${state.query}”` });

  host.hidden = chips.length === 0;
  host.innerHTML =
    chips
      .map(
        (chip) => `
      <button class="filter-chip" type="button" data-remove="${chip.field}" data-value="${esc(chip.value)}"
              aria-label="Remove filter ${esc(chip.label)}">
        ${esc(chip.label)} ${icon('x')}
      </button>`
      )
      .join('') +
    (chips.length > 1
      ? `<button class="filter-chip filter-chip--clear" type="button" data-clear-filters>Clear all</button>`
      : '');
  updateBadge();
}

function updateBadge() {
  const badge = $('#filter-badge');
  if (!badge) return;
  const total = filterCount();
  badge.hidden = total === 0;
  badge.textContent = String(total);
}

/** Keep the address bar in step, so a filtered catalogue can be shared. */
function syncUrl() {
  const params = new URLSearchParams();
  if (state.query) params.set('q', state.query);
  if (state.mine) params.set('mine', '1');
  if (state.price !== 'all') params.set('price', state.price);
  if (state.sort !== 'position') params.set('sort', state.sort);
  if (state.page > 1) params.set('page', String(state.page));
  for (const [field] of FACET_GROUPS) {
    for (const value of state.selected[field]) params.append(field, value);
  }
  const query = params.toString();
  try {
    history.replaceState(null, '', `courses.html${query ? `?${query}` : ''}`);
  } catch (err) {
    /* A sandboxed frame can refuse this; the filters still work. */
  }
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

const panel = $('#filter-panel');
const toggle = $('#filter-toggle');

function setFiltersOpen(open) {
  if (!panel || !toggle) return;
  panel.classList.toggle('is-open', open);
  toggle.setAttribute('aria-expanded', String(open));
  if (open) panel.focus();
}

toggle?.addEventListener('click', () => {
  setFiltersOpen(!panel.classList.contains('is-open'));
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && panel?.classList.contains('is-open')) {
    setFiltersOpen(false);
    toggle?.focus();
  }
});

panel?.addEventListener('change', (event) => {
  const input = event.target.closest('input[data-filter]');
  if (!input) return;
  const field = input.dataset.filter;
  if (field === 'price') {
    state.price = input.value;
  } else if (input.checked) {
    state.selected[field].add(input.value);
  } else {
    state.selected[field].delete(input.value);
  }
  state.page = 1;
  loadCourses();
});

/** One reset, used by the sidebar button, the chips and the empty state. */
function clearFilters() {
  Object.values(state.selected).forEach((set) => set.clear());
  state.price = 'all';
  state.query = '';
  state.mine = false;
  state.page = 1;
  if (search) search.value = '';
  setFiltersOpen(false);
  loadCourses();
}

$('#clear-filters')?.addEventListener('click', clearFilters);

document.addEventListener('click', (event) => {
  if (event.target.closest('[data-clear-filters]')) {
    clearFilters();
    return;
  }
  const chip = event.target.closest('[data-remove]');
  if (!chip) return;
  const field = chip.dataset.remove;
  if (field === 'price') {
    state.price = 'all';
  } else if (field === 'search') {
    state.query = '';
    if (search) search.value = '';
  } else {
    state.selected[field].delete(chip.dataset.value);
  }
  state.page = 1;
  loadCourses();
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
