/**
 * One subject of one batch.
 *
 * The batch page answers "what is in this batch" with a card per subject; this
 * page is the click. It reads the same detail payload (`GET /courses/<id>/`)
 * and keeps the chapters that file under the requested subject, so the two
 * screens can never disagree about what a subject contains — there is one
 * source, cut two ways.
 *
 * A chapter is a native `<details>`, so it opens with the keyboard, survives
 * find-in-page, and works even if this module never runs. Inside it, a class
 * is a card (a recording with a length and an hour) and a note is a row (a
 * file with a chapter). Both are hidden, not removed, when the search box
 * filters them — the open/closed state survives the search, which is what a
 * file manager has taught everyone to expect.
 */

import {
  $, $$, esc, getJson, rows, apiQuery, qsParam, initials
} from './core.js';
import {
  mountChrome, icon, thumbTone, emptyState, clockLabel, dayLabel
} from './ui.js';

mountChrome('courses');

const courseSlug = qsParam('course') || '';
const wantedSubject = (qsParam('subject') || '').trim();

let course = null;   // the adapted catalogue row
let timezone = '';   // the batch's clock, for every air time printed here
let subject = '';    // the label this page is about
let chapters = [];   // the folders filed under it
let applyFilter = () => {};

/* ------------------------------------------------------------------ */
/* Load                                                               */
/* ------------------------------------------------------------------ */

async function load() {
  if (!courseSlug) {
    renderMissing('No batch selected', 'Open a batch and pick a subject from it.');
    return;
  }

  try {
    const list = await getJson(`/courses/${apiQuery({ slug: courseSlug, page_size: 1 })}`);
    const match = rows(list)[0];
    if (!match) {
      renderMissing('Batch not found', 'This batch does not exist or is no longer published.');
      return;
    }

    const detail = await getJson(`/courses/${match.id}/`);
    course = {
      id: detail.id,
      slug: detail.slug || courseSlug,
      title: detail.title || 'Batch',
      subject: detail.subject || 'General',
      // Used only to name the teacher of *this* subject, and only when the
      // batch lists one whose subject matches — never as a guess per class.
      teachers: (detail.faculty || []).filter(
        (person) => (person.subject || '').trim().toLowerCase() === wantedSubject.toLowerCase()
      ).map((person) => person.name)
    };
    timezone = detail.timezone || '';

    const folders = detail.folders || [];
    // The same rule the batch page groups by: a chapter with no subject of its
    // own is filed under the batch's subject, never under a made-up heading.
    const groups = new Map();
    folders.forEach((folder) => {
      const name = (folder.subject || '').trim() || course.subject;
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(folder);
    });

    const found = [...groups.keys()].find(
      (name) => name.toLowerCase() === wantedSubject.toLowerCase()
    );
    if (!found) {
      renderMissing(
        wantedSubject ? 'Subject not found' : 'No subject selected',
        wantedSubject
          ? `${wantedSubject} is not part of ${course.title}. The batch page lists every subject it carries.`
          : `Open one of the subjects on ${course.title}.`
      );
      return;
    }

    subject = found;
    chapters = groups.get(found);
    render();
  } catch (err) {
    renderMissing('Subject unavailable', err?.message || 'This subject could not be loaded.');
  }
}

function renderMissing(title, body) {
  const headline = $('#subject-headline');
  if (headline) headline.textContent = title;
  const lead = $('#subject-lead');
  if (lead) lead.textContent = body;

  ['#panel-lectures', '#panel-notes'].forEach((selector) => {
    const node = $(selector);
    if (node) node.innerHTML = '';
  });
  const total = $('#subject-total');
  if (total) total.textContent = '';
  const search = $('#subject-search');
  if (search) search.closest('.tree-toolbar').hidden = true;

  const aside = $('#subject-aside');
  if (aside) {
    aside.innerHTML = emptyState({
      title,
      body,
      actionLabel: 'Browse batches',
      actionHref: 'courses.html',
      iconName: 'layers'
    });
  }
}

/* ------------------------------------------------------------------ */
/* Render                                                             */
/* ------------------------------------------------------------------ */

/** "2 chapters · 5 classes · 2 notes" — the same sentence the card carried. */
function counts(chapterList) {
  const classes = chapterList.reduce((n, folder) => n + (folder.lessons || []).length, 0);
  const notes = chapterList.reduce((n, folder) => n + (folder.pdf_resources || []).length, 0);
  const parts = [
    `${chapterList.length} ${chapterList.length === 1 ? 'chapter' : 'chapters'}`,
    `${classes} ${classes === 1 ? 'class' : 'classes'}`
  ];
  if (notes) parts.push(`${notes} ${notes === 1 ? 'note' : 'notes'}`);
  return { text: parts.join(' · '), classes, notes };
}

function render() {
  const summary = counts(chapters);
  document.title = `${subject} · ${course.title} — StudySpace`;

  const crumbBatch = $('#crumb-batch');
  if (crumbBatch) {
    crumbBatch.textContent = course.title;
    crumbBatch.href = `course.html${apiQuery({ slug: course.slug })}`;
  }
  const crumbSubject = $('#crumb-subject');
  if (crumbSubject) crumbSubject.textContent = subject;

  const headline = $('#subject-headline');
  if (headline) headline.textContent = subject;

  const lead = $('#subject-lead');
  if (lead) {
    // The batch names its teachers per subject; when it does, say who teaches
    // this one. A batch that lists nobody says nothing rather than inventing
    // a "By …" line on every card.
    const taught = course.teachers.length
      ? ` · Taught by ${course.teachers.join(' and ')}`
      : '';
    lead.textContent = `${course.title} · ${summary.text}${taught}`;
  }

  const iconHost = $('#subject-icon');
  if (iconHost) {
    iconHost.className = `subject-icon ${thumbTone(subject)}`;
    iconHost.innerHTML = icon(subjectIcon(subject));
  }

  const total = $('#subject-total');
  if (total) total.textContent = summary.text;

  renderLectures();
  renderNotes();
  renderAside(summary);
  renderCounts(summary);
  initTabs();
  initFilter();
}

/**
 * A guess at the icon that belongs to a subject name — decoration only, the
 * same table the batch page uses. A subject nobody has seen gets the generic
 * icon rather than the wrong one.
 */
const SUBJECT_ICONS = [
  [/physic|mechanic|optic|electric|magnet|kinemat|atomic|astro/i, 'atom'],
  [/chem|organic|inorganic|mole/i, 'flask'],
  [/maths?|mathemat|quant|aptitude|algebra|calculus|geometry|trigo/i, 'chart'],
  [/reason|logic|puzzle|mental ability/i, 'target'],
  [/biol|botany|zoolog|science/i, 'heart'],
  [/english|hindi|language|grammar|comprehension|literature/i, 'book'],
  [/computer|program|coding|python|java/i, 'cpu'],
  [/notice|announce|current affair|gk|general knowledge/i, 'megaphone']
];

function subjectIcon(name) {
  for (const [pattern, iconName] of SUBJECT_ICONS) {
    if (pattern.test(name)) return iconName;
  }
  return 'layers';
}

/** When a class airs, on the batch's clock — "5 Nov · 3:19 PM". */
function airTime(lesson) {
  if (!lesson.starts_at) return '';
  return `${dayLabel(lesson.starts_at, timezone)} · ${clockLabel(lesson.starts_at, timezone)}`;
}

/**
 * One class, as a card.
 *
 * The cover is the subject's own hue with its initials on it, because a
 * thumbnail would have to be a real frame of the recording and this product
 * has never claimed to have one. The length and the hour are the two facts
 * the API actually sends, and they are printed exactly as sent.
 */
function lectureCard(lesson) {
  const meta = [airTime(lesson), lesson.duration_minutes ? '' : lesson.description]
    .filter(Boolean)
    .join(' · ');

  const cover = `
        <span class="lecture-cover ${thumbTone(subject)}" aria-hidden="true">
          <span class="lecture-cover-initials">${esc(initials(subject))}</span>
          ${
            lesson.duration_minutes
              ? `<span class="lecture-duration">${icon('clock')}${lesson.duration_minutes} min</span>`
              : ''
          }
          ${
            lesson.is_locked
              ? '<span class="lecture-flag"><span class="badge badge-outline">Locked</span></span>'
              : ''
          }
        </span>`;

  const body = `
        <span class="lecture-body">
          <span class="lecture-title">${esc(lesson.title)}</span>
          ${meta ? `<span class="lecture-meta">${esc(meta)}</span>` : ''}
        </span>`;

  if (lesson.is_locked) {
    return `<div class="lecture-card is-locked" data-lesson="${lesson.id}">${cover}${body}</div>`;
  }
  return `<a class="lecture-card" data-lesson="${lesson.id}" href="player.html?lesson=${lesson.id}">${cover}${body}</a>`;
}

function lectureChapter(folder) {
  const lessons = folder.lessons || [];
  return `
    <details class="tree-chapter" open>
      <summary class="tree-chapter-head">
        <span class="tree-caret" aria-hidden="true"></span>
        <span class="tree-chapter-name">${esc(folder.title)}</span>
        <span class="tree-meta">${lessons.length} ${lessons.length === 1 ? 'class' : 'classes'}</span>
      </summary>
      ${folder.description ? `<p class="tree-chapter-note">${esc(folder.description)}</p>` : ''}
      ${
        lessons.length
          ? `<div class="lecture-grid">${lessons.map(lectureCard).join('')}</div>`
          : '<p class="tree-empty">No class published in this chapter yet.</p>'
      }
    </details>`;
}

/** One note: a PDF in a chapter. Locked notes are listed, never linked. */
function noteRow(note) {
  const locked = note.is_locked || !note.file_url;
  const label = `
        <span class="tree-file-icon" aria-hidden="true">${icon('note')}</span>
        <span class="tree-file-name">${esc(note.title)}${
          note.description ? `<small>${esc(note.description)}</small>` : ''
        }</span>
        <span class="tree-file-meta">PDF</span>`;

  if (locked) {
    return `<div class="tree-file is-locked" data-kind="note" data-file="${note.id}">
        ${label}
        <span class="tree-file-action"><span class="badge badge-outline">Locked</span></span>
      </div>`;
  }
  return `<a class="tree-file" data-kind="note" data-file="${note.id}" href="pdf.html?pdf=${note.id}">
        ${label}
        <span class="tree-file-action">Open ${icon('arrow-right')}</span>
      </a>`;
}

function noteChapter(folder) {
  const notes = folder.pdf_resources || [];
  return `
    <details class="tree-chapter" open>
      <summary class="tree-chapter-head">
        <span class="tree-caret" aria-hidden="true"></span>
        <span class="tree-chapter-name">${esc(folder.title)}</span>
        <span class="tree-meta">${notes.length} ${notes.length === 1 ? 'note' : 'notes'}</span>
      </summary>
      <div class="tree-files">
        ${notes.map(noteRow).join('') || '<p class="tree-empty">No note published in this chapter yet.</p>'}
      </div>
    </details>`;
}

function renderLectures() {
  const host = $('#panel-lectures');
  if (!host) return;
  const total = chapters.reduce((n, folder) => n + (folder.lessons || []).length, 0);
  if (!total) {
    host.innerHTML = emptyState({
      title: 'No classes in this subject yet',
      body: 'Classes appear here as soon as the faculty publishes them. Notes, if there are any, are on the Notes tab.',
      iconName: 'play'
    });
    return;
  }
  host.innerHTML = `<div class="content-tree">${chapters.map(lectureChapter).join('')}</div>`;
}

function renderNotes() {
  const host = $('#panel-notes');
  if (!host) return;
  const total = chapters.reduce((n, folder) => n + (folder.pdf_resources || []).length, 0);
  if (!total) {
    host.innerHTML = emptyState({
      title: 'No notes in this subject yet',
      body: 'Notes and PDFs appear here, filed in the chapter they belong to, as soon as the faculty publishes them.',
      iconName: 'note'
    });
    return;
  }
  host.innerHTML = `<div class="content-tree">${chapters.map(noteChapter).join('')}</div>`;
}

function renderCounts(summary) {
  const values = { lectures: summary.classes, notes: summary.notes };
  Object.entries(values).forEach(([name, value]) => {
    const node = document.querySelector(`.tab-count[data-count="${name}"]`);
    if (!node) return;
    node.textContent = value > 0 ? String(value) : '';
    node.hidden = !(value > 0);
  });
}

function renderAside(summary) {
  const host = $('#subject-aside');
  if (!host) return;
  const facts = [
    ['Chapters', String(chapters.length)],
    ['Classes', String(summary.classes)],
    ['Notes', String(summary.notes)],
    ['Batch', course.title]
  ];
  host.innerHTML = `
    <div class="facts-card">
      <strong style="display:block;margin-bottom:10px">${esc(subject)}</strong>
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
      <a class="btn btn-ghost btn-block" style="margin-top:var(--sp-4)" href="course.html${apiQuery({ slug: course.slug })}">
        ${icon('arrow-left')} Back to batch
      </a>
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Behaviour                                                          */
/* ------------------------------------------------------------------ */

/**
 * The filter, applied to whichever panel is showing.
 *
 * Rows are hidden rather than removed, so a chapter you had open stays open,
 * and searching for a chapter name keeps every class inside it. Switching tab
 * re-runs the same filter on the panel that just appeared, which is what makes
 * one search box honest across two tabs.
 */
function initFilter() {
  const input = $('#subject-search');
  const nothing = $('#subject-no-match');
  if (!input || !nothing) return;

  applyFilter = () => {
    const term = input.value.trim().toLowerCase();
    const panel = document.querySelector('.tab-panel:not([hidden])');
    if (!panel) return;
    let anyVisible = false;

    panel.querySelectorAll('.tree-chapter').forEach((chapter) => {
      const chapterHit =
        !term || chapter.querySelector('.tree-chapter-name').textContent.toLowerCase().includes(term);
      let hits = 0;

      chapter.querySelectorAll('.lecture-card, .tree-file').forEach((row) => {
        const hit = chapterHit || row.textContent.toLowerCase().includes(term);
        row.hidden = !hit;
        if (hit) hits += 1;
      });

      chapter.hidden = Boolean(term) && !chapterHit && hits === 0;
      if (!chapter.hidden) anyVisible = true;
    });

    nothing.hidden = !term || anyVisible;
  };

  input.addEventListener('input', applyFilter);
  input.addEventListener('search', applyFilter);

  // One button opens every chapter, the other closes them: a subject can run
  // to a dozen chapters and the tree is native <details>, so this is a two
  // line change rather than a second tree implementation.
  $$('[data-tree]').forEach((button) => {
    button.addEventListener('click', () => {
      const open = button.dataset.tree === 'expand';
      const panel = document.querySelector('.tab-panel:not([hidden])');
      if (!panel) return;
      panel.querySelectorAll('.tree-chapter').forEach((chapter) => {
        chapter.open = open;
      });
    });
  });
}

const TABS = ['lectures', 'notes'];

function tabFromUrl() {
  const wanted = (qsParam('tab') || '').toLowerCase();
  return TABS.includes(wanted) ? wanted : 'lectures';
}

function writeTabToUrl(name, { push }) {
  const url = new URL(location.href);
  if (name === 'lectures') url.searchParams.delete('tab');
  else url.searchParams.set('tab', name);
  const next = `${url.pathname}${url.search}${url.hash}`;
  if (next === `${location.pathname}${location.search}${location.hash}`) return;
  if (push) history.pushState({ tab: name }, '', next);
  else history.replaceState({ tab: name }, '', next);
}

function selectTab(name, { push = true, focus = false } = {}) {
  const chosen = TABS.includes(name) ? name : 'lectures';
  $$('.tabs .tab').forEach((tab) => {
    const selected = tab.dataset.tab === chosen;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
    const panel = document.getElementById(tab.getAttribute('aria-controls'));
    if (panel) panel.hidden = !selected;
  });
  writeTabToUrl(chosen, { push });
  applyFilter();
}

function initTabs() {
  const tabs = $$('.tabs .tab');
  const nameOf = (tab) => tab.dataset.tab || 'lectures';

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
