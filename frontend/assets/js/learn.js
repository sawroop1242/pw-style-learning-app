/**
 * My batch — the classroom.
 *
 * This is the page a learner lands on from **My batches**, and it is a
 * different page from `course.html` on purpose: the course page answers "what
 * is this batch and how do I get it", this one answers "what am I studying
 * today". It opens on the batch's **subjects**, each a card carrying the
 * chapters and classes behind it; a subject opens on `subject.html`, which
 * holds its chapters, the classes in them and the notes beside them.
 *
 * One read of `GET /courses/<id>/` feeds the whole page — the cards, the
 * aside and the tab counts all come from the same payload, so the numbers
 * cannot disagree with each other. The papers and the feed are the batch's own
 * rows (`?course=`), fetched only once the page is up: neither is a reason to
 * keep a learner waiting for the syllabus.
 */

import {
  $, $$, esc, getJson, rows, apiQuery, qsParam, initials, adaptTest
} from './core.js';
import {
  mountChrome, icon, thumbTone, emptyState, testCard, postCard,
  groupBySubject, subjectHref, subjectGrid, renderScheduleStrip
} from './ui.js';

mountChrome('courses');

const slug = qsParam('course') || '';

let batch = null;  // the detail payload, with `folders` guaranteed to be an array

/* ------------------------------------------------------------------ */
/* Load                                                               */
/* ------------------------------------------------------------------ */

async function load() {
  if (!slug) {
    renderMissing('No batch selected', 'Open My batches and pick one.');
    return;
  }

  try {
    // A slug is resolved by the list endpoint; the id then addresses the detail.
    const list = await getJson(`/courses/${apiQuery({ slug, page_size: 1 })}`);
    const match = rows(list)[0];
    if (!match) {
      renderMissing('Batch not found', 'This batch does not exist or is no longer published.');
      return;
    }

    const detail = await getJson(`/courses/${match.id}/`);
    batch = { ...detail, folders: detail.folders || [] };

    // The classroom is for batches on this account. A visitor who is not in
    // the batch gets a sentence and a door, not a syllabus they cannot open.
    if (detail.has_access === false) {
      renderJoin(detail);
      return;
    }

    render(detail);
  } catch (err) {
    renderMissing('Batch unavailable', err?.message || 'This batch could not be loaded.');
  }
}

function renderMissing(title, body) {
  const headline = $('#learn-title');
  if (headline) headline.textContent = title;
  const sub = $('#learn-sub');
  if (sub) sub.textContent = body;
  hideClassroom();
  const aside = $('#learn-aside');
  if (aside) {
    aside.innerHTML = emptyState({
      title,
      body,
      actionLabel: 'My batches',
      actionHref: 'courses.html?mine=1',
      iconName: 'book'
    });
  }
}

function hideClassroom() {
  $('#class-timetable')?.setAttribute('hidden', '');
  $('#learn-tabs')?.setAttribute('hidden', '');
  ['#panel-subjects', '#panel-tests', '#panel-announcements', '#panel-community'].forEach((selector) => {
    const node = $(selector);
    if (node) node.hidden = true;
  });
}

/**
 * Not on this account yet.
 *
 * The page names the batch and offers the two honest routes in — the public
 * page (where a free batch is joined, and a paid one takes a code) — rather
 * than duplicating the purchase card here, where it would be a second place to
 * keep the access rules right.
 */
function renderJoin(detail) {
  const overview = `course.html${apiQuery({ slug: detail.slug })}`;
  document.title = `${detail.title} — StudySpace`;
  $('#crumb-title').textContent = detail.title;

  const headline = $('#learn-title');
  if (headline) headline.textContent = detail.title;
  const sub = $('#learn-sub');
  if (sub) {
    sub.textContent = detail.pricing_mode === 'free'
      ? 'This free batch is not on your account yet — join it and its classes open here.'
      : 'This paid batch is not on your account yet. It unlocks with an access code from your institute.';
  }
  paintHead(detail);

  hideClassroom();
  const panel = $('#panel-subjects');
  if (panel) {
    panel.hidden = false;
    panel.innerHTML = emptyState({
      title: detail.pricing_mode === 'free' ? 'Join this batch to open it' : 'Redeem a code to open it',
      body: detail.pricing_mode === 'free'
        ? 'Free batches are joined, not handed out: one tap adds this batch to your account and unlocks its classes and notes.'
        : 'Press “Redeem access code” or “Get code” on the batch page. Once the code is accepted, the classes here are yours.',
      actionLabel: 'Open the batch page',
      actionHref: overview,
      iconName: 'lock'
    });
  }

  const aside = $('#learn-aside');
  if (aside) {
    aside.innerHTML = `
      <div class="facts-card">
        <strong style="display:block;margin-bottom:10px">${esc(detail.title)}</strong>
        <dl style="display:grid;gap:var(--sp-4);margin:0">
          <div class="facts-row"><dt>Subject</dt><dd>${esc(detail.subject || 'General')}</dd></div>
          <div class="facts-row"><dt>Access</dt><dd>Locked</dd></div>
        </dl>
        <a class="btn btn-primary btn-block" style="margin-top:var(--sp-4)" href="${esc(overview)}">Open the batch page</a>
        <a class="btn btn-ghost btn-block" style="margin-top:10px" href="courses.html?mine=1">My batches</a>
      </div>`;
  }
}

/* ------------------------------------------------------------------ */
/* Render                                                             */
/* ------------------------------------------------------------------ */

function counts(folders) {
  return {
    chapters: folders.length,
    classes: folders.reduce((n, folder) => n + (folder.lessons || []).length, 0),
    notes: folders.reduce((n, folder) => n + (folder.pdf_resources || []).length, 0)
  };
}

/** Cover, title, one identifying line and the badges the server can back. */
function paintHead(detail) {
  const cover = $('#learn-cover');
  if (cover) {
    cover.className = `learn-cover ${thumbTone(detail.subject || '')}`;
    cover.innerHTML = detail.image_url
      ? `<img class="batch-cover-img" src="${esc(detail.image_url)}" alt="" decoding="async" data-hide-on-error>`
      : esc(initials(detail.subject || detail.title || 'SS'));
  }

  const badges = $('#learn-badges');
  if (badges) {
    const facts = [
      detail.subject ? `<span class="badge badge-dark">${esc(detail.subject)}</span>` : '',
      detail.exam ? `<span class="badge badge-outline">${esc(detail.exam)}</span>` : '',
      detail.level ? `<span class="badge badge-outline">${esc(detail.level)}</span>` : ''
    ];
    badges.innerHTML = facts.filter(Boolean).join('');
  }

  const overview = $('#overview-link');
  if (overview) overview.href = `course.html${apiQuery({ slug: detail.slug })}`;
}

function render(detail) {
  document.title = `${detail.title} — My batch — StudySpace`;
  $('#crumb-title').textContent = detail.title;
  $('#learn-title').textContent = detail.title;
  paintHead(detail);

  const totals = counts(batch.folders);
  const groups = groupBySubject(batch.folders, detail.subject || '');
  const sub = $('#learn-sub');
  if (sub) {
    sub.innerHTML = esc(
      [
        `${totals.chapters} ${totals.chapters === 1 ? 'chapter' : 'chapters'}`,
        `${totals.classes} ${totals.classes === 1 ? 'class' : 'classes'}`,
        `${totals.notes} ${totals.notes === 1 ? 'note' : 'notes'}`
      ].join(' · ')
    );
  }

  renderSubjects(groups);
  renderFacultyLine(detail);
  renderAside(detail, totals, groups);
  renderCounts({ subjects: groups.length, tests: null });

  renderScheduleStrip($('#class-timetable'), { slug: detail.slug, weeklyLink: true });

  // Papers and the feed are secondary: the syllabus is already on screen when
  // they are asked for, and a failure there does not blank the page.
  loadTests(detail.id);
  loadFeed(detail.id);

  initTabs();
}

/** The syllabus, one card per subject — the same cards the batch page shows. */
function renderSubjects(groups) {
  const host = $('#panel-subjects');
  if (!host) return;

  if (!groups.length) {
    host.innerHTML = emptyState({
      title: 'No subjects published yet',
      body: 'Subjects, chapters, classes and notes appear here as soon as the faculty publishes them.',
      iconName: 'layers'
    });
    return;
  }

  host.innerHTML = subjectGrid(groups, (group) => subjectHref(batch.slug, group.subject));
}

/** The batch's papers, as the same cards the test series page uses. */
async function loadTests(courseId) {
  const host = $('#panel-tests');
  if (!host) return;
  try {
    const payload = await getJson(`/quizzes/${apiQuery({ course: courseId, page_size: 50 })}`);
    const list = rows(payload).map(adaptTest);
    host.innerHTML = list.length
      ? `<div class="test-grid">${list.map(testCard).join('')}</div>`
      : emptyState({
          title: 'No papers in this batch yet',
          body: 'A published paper appears here with its duration and marking scheme.',
          actionLabel: 'All papers',
          actionHref: 'tests.html',
          iconName: 'file-text'
        });
    renderCounts({ tests: list.length });
  } catch {
    host.innerHTML = emptyState({
      title: 'The papers could not be loaded',
      body: 'The rest of the batch is unaffected.',
      iconName: 'file-text'
    });
  }
}

/**
 * What faculty posted to this batch.
 *
 * One endpoint feeds both tabs, split by the one field the server gives us:
 * a **pinned** notice is an announcement — the faculty put it at the top to be
 * read — and everything, pinned included, is the feed. Two lists from one read,
 * so the counts on the two tabs add up rather than contradicting.
 */
async function loadFeed(courseId) {
  const feedHost = $('#panel-community');
  const noticeHost = $('#panel-announcements');
  if (!feedHost) return;

  try {
    const payload = await getJson(`/community/${apiQuery({ course: courseId, page_size: 20 })}`);
    const posts = rows(payload);
    const pinned = posts.filter((post) => post.pinned);

    if (noticeHost) {
      noticeHost.innerHTML = pinned.length
        ? `<div class="stack" style="gap:var(--sp-3)">${pinned.map((post) => postCard(post, { showCourse: false })).join('')}</div>
           <p class="tiny subtle" style="margin:var(--sp-3) 0 0">Pinned by the faculty. Everything else is under Community.</p>`
        : emptyState({
            title: 'No pinned notice yet',
            body: 'A notice the faculty pins to the top of this batch appears here. Everything posted so far is under Community.',
            iconName: 'megaphone'
          });
      renderCounts({ announcements: pinned.length });
    }

    feedHost.innerHTML = posts.length
      ? `<div class="stack" style="gap:var(--sp-3)">${posts.map((post) => postCard(post, { showCourse: false })).join('')}</div>
         <a class="link" style="display:inline-flex;margin-top:var(--sp-3)" href="community.html${apiQuery({ course: courseId })}">All posts for this batch ${icon('arrow-right')}</a>`
      : emptyState({
          title: 'Nothing posted in this batch yet',
          body: 'Notices and doubts from the faculty appear here, newest first.',
          actionLabel: 'Community',
          actionHref: 'community.html',
          iconName: 'message'
        });
    renderCounts({ community: posts.length });
  } catch {
    const markup = emptyState({
      title: 'The feed could not be loaded',
      body: 'The rest of the batch is unaffected.',
      iconName: 'message'
    });
    feedHost.innerHTML = markup;
    if (noticeHost) noticeHost.innerHTML = markup;
  }
}

/**
 * The people teaching the batch, in the header.
 *
 * The reference puts its faculty on the batch card, not behind a tab, and this
 * one does the same: a line of names under the badges, linking to the public
 * page's Teachers panel for the bios. Only the names the batch actually lists.
 */
function renderFacultyLine(detail) {
  const host = $('#learn-faculty');
  if (!host) return;
  const people = detail.faculty || [];
  if (!people.length) {
    host.hidden = true;
    return;
  }
  const names = people.map((person) => esc(person.name)).join(', ');
  host.hidden = false;
  host.innerHTML = `Taught by ${names} · <a class="link" href="course.html${apiQuery({ slug: detail.slug })}&tab=teachers">Faculty</a>`;
}

function renderAside(detail, totals, groups) {
  const host = $('#learn-aside');
  if (!host) return;
  const facts = [
    ['Subjects', String(groups.length)],
    ['Chapters', String(totals.chapters)],
    ['Classes', String(totals.classes)],
    ['Notes', String(totals.notes)]
  ];
  host.innerHTML = `
    <div class="facts-card">
      <strong style="display:block;margin-bottom:10px">This batch</strong>
      <dl style="display:grid;gap:var(--sp-4);margin:0">
        ${facts
          .map(
            ([label, value]) => `
          <div class="facts-row">
            <dt>${esc(label)}</dt>
            <dd>${esc(value)}</dd>
          </div>`
          )
          .join('')}
      </dl>
      <a class="btn btn-ghost btn-block" style="margin-top:var(--sp-4)" href="course.html${apiQuery({ slug: detail.slug })}">
        Batch page ${icon('arrow-right')}
      </a>
      <a class="btn btn-ghost btn-block" style="margin-top:10px" href="courses.html?mine=1">My batches</a>
    </div>`;
}

/**
 * Counts on the tabs, filled in as their panels arrive.
 *
 * A zero badge is noise, so a tab with nothing behind it shows no number —
 * and `null` means "not known yet", which leaves the badge as it was rather
 * than flashing a zero.
 */
function renderCounts(values) {
  Object.entries(values).forEach(([name, value]) => {
    if (value === null || value === undefined) return;
    const node = document.querySelector(`.tab-count[data-count="${name}"]`);
    if (!node) return;
    node.textContent = value > 0 ? String(value) : '';
    node.hidden = !(value > 0);
  });
}

/* ------------------------------------------------------------------ */
/* Tabs                                                               */
/* ------------------------------------------------------------------ */

const TABS = ['subjects', 'tests', 'announcements', 'community'];

function tabFromUrl() {
  const wanted = (qsParam('tab') || '').toLowerCase();
  return TABS.includes(wanted) ? wanted : 'subjects';
}

function writeTabToUrl(name, { push }) {
  const url = new URL(location.href);
  if (name === 'subjects') url.searchParams.delete('tab');
  else url.searchParams.set('tab', name);
  const next = `${url.pathname}${url.search}${url.hash}`;
  if (next === `${location.pathname}${location.search}${location.hash}`) return;
  if (push) history.pushState({ tab: name }, '', next);
  else history.replaceState({ tab: name }, '', next);
}

function selectTab(name, { push = true, focus = false } = {}) {
  const chosen = TABS.includes(name) ? name : 'subjects';
  $$('#learn-tabs .tab').forEach((tab) => {
    const selected = tab.dataset.tab === chosen;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
    const panel = document.getElementById(tab.getAttribute('aria-controls'));
    if (panel) panel.hidden = !selected;
  });
  writeTabToUrl(chosen, { push });
}

function initTabs() {
  const tabs = $$('#learn-tabs .tab');
  const nameOf = (tab) => tab.dataset.tab || 'subjects';

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => selectTab(nameOf(tab), { push: true }));
    tab.addEventListener('keydown', (event) => {
      const index = tabs.indexOf(tab);
      let next = null;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      if (next === null) return;
      event.preventDefault();
      selectTab(nameOf(tabs[next]), { push: true, focus: true });
    });
  });

  window.addEventListener('popstate', () => selectTab(tabFromUrl(), { push: false }));
  selectTab(tabFromUrl(), { push: false });
}

load();
