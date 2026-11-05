/**
 * Batch detail.
 *
 * One read of the catalogue (`?slug=`) resolves the batch, a second read of the
 * detail endpoint brings its folders, lessons, PDFs and access state, and a
 * third brings the tests attached to it. The curriculum, the lesson list and
 * the test list are therefore the database, not a template — a batch with no
 * folders renders "no lessons yet" instead of a plausible syllabus.
 */

import {
  $, $$, esc, getJson, rows, apiQuery, money, initials, qsParam, isSignedIn,
  request, shortDate, adaptCourse, adaptTest
} from './core.js';
import {
  mountChrome, batchCard, icon, thumbTone, emptyState, toast, wireRetry,
  scheduleRow, clockLabel, dayLabel
} from './ui.js';

mountChrome('courses');

const slug = qsParam('slug') || '';
let current = null;

/* ------------------------------------------------------------------ */
/* Load                                                               */
/* ------------------------------------------------------------------ */

async function loadCourse() {
  if (!slug && !qsParam('id')) {
    renderMissing('No batch selected', 'Open the catalogue and pick a batch.');
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
    const tests = await getJson(`/quizzes/${apiQuery({ course: match.id, page_size: 50 })}`).catch(() => null);
    render(detail, rows(tests || []));
  } catch (err) {
    renderMissing('Batch unavailable', err?.message || 'The batch could not be loaded.');
  }
}

function renderMissing(title, body) {
  const host = $('#course-headline');
  if (host) host.textContent = title;
  $('#purchase-slot').innerHTML = emptyState({
    title,
    body,
    actionLabel: 'Back to batches',
    actionHref: 'courses.html',
    iconName: 'book'
  });
  ['#panel-overview', '#panel-classes', '#panel-notes', '#panel-papers', '#panel-teachers', '#course-aside', '#similar-grid'].forEach(
    (selector) => {
      const node = $(selector);
      if (node) node.innerHTML = '';
    }
  );
}

/* ------------------------------------------------------------------ */
/* Render                                                             */
/* ------------------------------------------------------------------ */

function render(detail, testRows) {
  current = adaptCourse(detail);
  current.folders = detail.folders || [];
  current.description = detail.description || '';

  document.title = `${current.title} — StudySpace`;
  $('#crumb-title').textContent = current.title;

  renderHeadline();
  renderPurchase();
  renderOverview();
  renderClasses();
  renderPapers(testRows);
  renderTeachers();
  renderAside();
  renderCounts(testRows);
  initTabs();
  wireRedeem();
  wireEnroll();
  loadSimilar();
}

function renderHeadline() {
  const host = $('#course-headline');
  const facts = [
    ['play', `${current.lessons} ${current.lessons === 1 ? 'lesson' : 'lessons'}`],
    ['file-text', `${current.tests} ${current.tests === 1 ? 'test' : 'tests'}`],
    ['book', `${current.folders.length} ${current.folders.length === 1 ? 'chapter' : 'chapters'}`]
  ];

  host.innerHTML = `
    <span class="badges">
      ${current.free ? '<span class="badge badge-free">Free batch</span>' : '<span class="badge badge-paid">Paid batch</span>'}
      <span class="badge badge-dark">${esc(current.subject)}</span>
      ${current.hasAccess ? '<span class="badge badge-live">Unlocked</span>' : ''}
    </span>
    <span class="course-title">${esc(current.title)}</span>
    <p class="course-hero-lead">${esc(current.description)}</p>
    <div class="batch-facts-inline">
      ${facts.map(([iconName, label]) => `<span>${icon(iconName)} ${esc(label)}</span>`).join('')}
      ${current.telegram ? `<span>${icon('message')} <a class="link" href="${esc(current.telegram)}" rel="noopener">Batch channel</a></span>` : ''}
    </div>`;

  const cover = $('#course-cover');
  if (cover) {
    cover.className = `batch-cover-lg ${thumbTone(current.subject)}`;
    cover.innerHTML = `${
      current.image
        ? `<img class="batch-cover-img" src="${esc(current.image)}" alt="" decoding="async" data-hide-on-error>`
        : ''
    }<span class="cover-faces"><span class="cover-face">${esc(initials(current.subject || 'SS'))}</span></span>`;
  }
}

function renderPurchase() {
  const host = $('#purchase-slot');
  const isFree = current.free;
  // A free batch is not handed out: it is joined. Until the learner enrols,
  // the recordings stay locked, so the button says "Enrol" rather than
  // "Start learning" and the copy stops promising open access.
  const open = current.hasAccess;

  host.innerHTML = `
    <div class="batch-actions">
      ${
        open
          ? `<a class="btn btn-primary btn-lg" href="#panel-classes" data-open-tab="classes">Start learning</a>`
          : isFree
            ? `<button class="btn btn-primary btn-lg" type="button" data-enroll>Enrol — free</button>`
            : `<button class="btn btn-accent btn-lg" type="button" data-redeem>Redeem access code</button>`
      }
      ${
        !open && !isFree && current.telegramDm
          ? `<a class="btn btn-primary btn-lg" href="${esc(current.telegramDm)}" target="_blank" rel="noopener" data-get-code>${icon('message')} Get code</a>`
          : ''
      }
      <button class="btn btn-ghost btn-lg" data-share>${icon('share')} Share</button>
    </div>
    ${
      isFree && !open
        ? '<p class="tiny subtle" style="margin-top:12px">Free to join. One tap adds the batch to your account and unlocks its classes and notes.</p>'
        : isFree
          ? '<p class="tiny subtle" style="margin-top:12px">Enrolled. Classes and notes are open on this account.</p>'
          : current.hasAccess
          ? '<p class="tiny subtle" style="margin-top:12px">Unlocked on this account. No card payment is taken on this platform.</p>'
          : `<p class="tiny subtle" style="margin-top:12px">${money(current.price)} · ${
              current.telegramDm
                ? `message ${esc(current.telegramHandle || 'the teacher')} on Telegram for a code, then redeem it here. No card payment is taken.`
                : 'unlocks with an access code from your institute, no card payment'
            }</p>`
    }`;

  const mobile = $('#mobile-buy');
  if (mobile) {
    document.body.classList.add('has-mobile-buy');
    mobile.innerHTML = `
      <span class="mobile-buy-price">
        ${isFree ? 'Free batch' : current.hasAccess ? 'Unlocked' : money(current.price)}
      </span>
      ${
        open
          ? `<a class="btn btn-primary btn-sm" href="#panel-classes" data-open-tab="classes">Start learning</a>`
          : isFree
            ? `<button class="btn btn-primary btn-sm" type="button" data-enroll>Enrol free</button>`
            : `${
                current.telegramDm
                  ? `<a class="btn btn-primary btn-sm" href="${esc(current.telegramDm)}" target="_blank" rel="noopener" data-get-code>${icon('message')} Get code</a>`
                  : ''
              }<button class="btn btn-accent btn-sm" type="button" data-redeem>Redeem code</button>`
      }`;
  }
}

/**
 * The batch's own numbers, written on the tab that leads to them.
 *
 * A count is only shown when there is something to count: an empty tab reads
 * "Notes", not "Notes 0", because a zero badge is noise, not information.
 */
function renderCounts(testRows) {
  // The Classes tab holds classes *and* notes now that the tree nests both,
  // so its badge counts both: a tab that says "5" and opens on seven rows is
  // a small lie the screen has no reason to tell.
  const lessons = current.folders.reduce((n, folder) => n + (folder.lessons || []).length, 0);
  const notes = current.folders.reduce((n, folder) => n + (folder.pdf_resources || []).length, 0);
  const counts = {
    classes: lessons + notes,
    papers: (testRows || []).length,
    teachers: (current.faculty || []).length
  };
  Object.entries(counts).forEach(([name, value]) => {
    const node = document.querySelector(`.tab-count[data-count="${name}"]`);
    if (!node) return;
    node.textContent = value > 0 ? String(value) : '';
    node.hidden = !(value > 0);
  });
}

function renderOverview() {
  const host = $('#panel-overview');
  const lessonCount = current.folders.reduce((n, f) => n + (f.lessons || []).length, 0);
  host.innerHTML = `
    <p>${esc(current.description || 'This batch has no description yet.')}</p>
    <div class="grid grid-2" style="gap:var(--sp-4);margin-top:var(--sp-4)">
      <div class="card card-pad">
        <strong style="display:block;margin-bottom:6px">What is inside</strong>
        <ul class="feature-list" style="margin:0">
          <li>${icon('play')}<span>${lessonCount} ${lessonCount === 1 ? 'lesson' : 'lessons'} across ${current.folders.length} ${current.folders.length === 1 ? 'chapter' : 'chapters'}</span></li>
          <li>${icon('file-text')}<span>${current.tests} ${current.tests === 1 ? 'paper' : 'papers'} in this batch</span></li>
          <li>${icon('note')}<span>Notes and PDFs, filed in the chapter they belong to</span></li>
        </ul>
      </div>
      <div class="card card-pad">
        <strong style="display:block;margin-bottom:6px">How access works</strong>
        <p class="small muted" style="margin:0">
          ${
            current.free
              ? 'Free to join — press Enrol and the batch is added to your account. Recordings and notes open to enrolled learners.'
              : current.hasAccess
                ? 'This batch is unlocked on your account. Lessons and protected notes are available.'
                : current.telegramDm
                  ? `Paid batch. Message ${esc(current.telegramHandle || 'the teacher')} on Telegram for an access code — the chat opens with this batch already named — then redeem the code here.`
                  : 'This is a paid batch. Enter an access code issued by your institute to unlock the lessons and protected notes.'
          }
        </p>
      </div>
    </div>
    <div class="card card-pad" style="margin-top:var(--sp-4)">
      <strong style="display:block;margin-bottom:10px">Questions people ask</strong>
      ${faqItems()
        .map(
          ([q, a]) => `
        <div class="acc-item">
          <div class="acc-head-static"><span class="acc-title">${esc(q)}</span></div>
          <p class="acc-text">${esc(a)}</p>
        </div>`
        )
        .join('')}
    </div>`;
}

/* ------------------------------------------------------------------ */
/* The batch tree: subject → chapter → files                          */
/* ------------------------------------------------------------------ */

/** "3 classes · 1 note" — the summary a folder line carries. */
function itemCount(classes, notes) {
  const parts = [];
  if (classes) parts.push(`${classes} ${classes === 1 ? 'class' : 'classes'}`);
  if (notes) parts.push(`${notes} ${notes === 1 ? 'note' : 'notes'}`);
  return parts.join(' · ') || 'Empty';
}

/**
 * Chapters grouped by the subject they are filed under.
 *
 * `CourseFolder.subject` is what the provider typed; when it is blank the
 * chapter files under the batch's own subject rather than a heading the
 * faculty never chose. A chapter that arrives with a subject the batch does
 * not carry still gets a group of its own — the screen follows the data.
 */
function groupBySubject(folders) {
  const groups = new Map();
  folders.forEach((folder) => {
    const subject = (folder.subject || '').trim() || current.subject || 'General';
    if (!groups.has(subject)) groups.set(subject, []);
    groups.get(subject).push(folder);
  });
  return [...groups.entries()].map(([subject, chapters]) => ({
    subject,
    chapters,
    classes: chapters.reduce((n, c) => n + (c.lessons || []).length, 0),
    notes: chapters.reduce((n, c) => n + (c.pdf_resources || []).length, 0)
  }));
}

/** One row in a chapter: a class, or a note. Both read the same way. */
function fileRow({ kind, id, title, meta, href, locked, description }) {
  const iconName = kind === 'note' ? 'note' : 'play';
  const label = `<span class="tree-file-icon" aria-hidden="true">${icon(iconName)}</span>
        <span class="tree-file-name">${esc(title)}${
          description ? `<small>${esc(description)}</small>` : ''
        }</span>
        <span class="tree-file-meta">${esc(meta)}</span>`;

  if (locked) {
    return `<div class="tree-file is-locked" data-kind="${kind}" data-file="${id}">
        ${label}
        <span class="tree-file-action"><span class="badge badge-outline">Locked</span></span>
      </div>`;
  }
  return `<a class="tree-file" data-kind="${kind}" data-file="${id}" href="${esc(href)}">
        ${label}
        <span class="tree-file-action">Open ${icon('arrow-right')}</span>
      </a>`;
}

function chapterBlock(folder) {
  const lessons = folder.lessons || [];
  const notes = folder.pdf_resources || [];
  const rows = [
    ...lessons.map((lesson) =>
      fileRow({
        kind: 'class',
        id: lesson.id,
        title: lesson.title,
        description: lesson.starts_at
          ? `${dayLabel(lesson.starts_at, current.timezone || '')} · ${clockLabel(lesson.starts_at, current.timezone || '')}`
          : lesson.description,
        meta: `${lesson.duration_minutes || 0} min`,
        href: `player.html?lesson=${lesson.id}`,
        locked: lesson.is_locked
      })
    ),
    ...notes.map((note) =>
      fileRow({
        kind: 'note',
        id: note.id,
        title: note.title,
        description: note.description,
        meta: 'PDF',
        href: `pdf.html?pdf=${note.id}`,
        locked: note.is_locked || !note.file_url
      })
    )
  ];

  return `
    <details class="tree-chapter" open>
      <summary class="tree-chapter-head">
        <span class="tree-caret" aria-hidden="true"></span>
        <span class="tree-chapter-name">${esc(folder.title)}</span>
        <span class="tree-meta">${itemCount(lessons.length, notes.length)}</span>
      </summary>
      ${
        folder.description
          ? `<p class="tree-chapter-note">${esc(folder.description)}</p>`
          : ''
      }
      <div class="tree-files">
        ${rows.join('') || '<p class="tree-empty">Nothing published in this chapter yet.</p>'}
      </div>
    </details>`;
}

function renderClasses() {
  const host = $('#panel-classes');
  if (!current.folders.length) {
    host.innerHTML = emptyState({
      title: 'No chapters published yet',
      body: 'Chapters, classes and notes appear here as soon as the faculty publishes them.',
      iconName: 'play'
    });
    return;
  }

  const groups = groupBySubject(current.folders);
  const totalClasses = groups.reduce((n, g) => n + g.classes, 0);
  const totalNotes = groups.reduce((n, g) => n + g.notes, 0);

  host.innerHTML = `
    <div class="card card-pad batch-schedule" id="class-timetable" aria-live="polite"></div>
    <div class="content-tree" id="content-tree">
      <div class="tree-toolbar">
        <label class="visually-hidden" for="content-search">Search this batch</label>
        <input id="content-search" type="search" autocomplete="off" placeholder="Search chapters, classes and notes">
        <div class="tree-actions">
          <button type="button" class="chip" data-tree="expand">Expand all</button>
          <button type="button" class="chip" data-tree="collapse">Collapse all</button>
        </div>
        <p class="tree-total">${groups.length} ${groups.length === 1 ? 'subject' : 'subjects'} · ${totalClasses} ${totalClasses === 1 ? 'class' : 'classes'} · ${totalNotes} ${totalNotes === 1 ? 'note' : 'notes'}</p>
      </div>
      <p class="tree-no-match" id="tree-no-match" hidden>Nothing in this batch matches that search.</p>
      ${groups
        .map(
          (group) => `
        <details class="tree-subject" open>
          <summary class="tree-subject-head">
            <span class="tree-caret" aria-hidden="true"></span>
            <span class="tree-subject-name">${esc(group.subject)}</span>
            <span class="tree-meta">${group.chapters.length} ${group.chapters.length === 1 ? 'chapter' : 'chapters'} · ${itemCount(group.classes, group.notes)}</span>
          </summary>
          <div class="tree-chapters">${group.chapters.map(chapterBlock).join('')}</div>
        </details>`
        )
        .join('')}
    </div>`;

  wireTreeSearch(host);
  loadBatchSchedule();
}

/**
 * Filter the tree as you type.
 *
 * The rows stay in the document and are hidden, so the open/closed state of a
 * chapter survives a search: a learner who searched "integration", cleared it,
 * and came back to the same chapter they had open is the behaviour a file
 * manager has taught them to expect.
 */
function wireTreeSearch(host) {
  const input = host.querySelector('#content-search');
  const nothing = host.querySelector('#tree-no-match');
  if (!input || !nothing) return;

  const apply = () => {
    const term = input.value.trim().toLowerCase();
    const matches = (text) => !term || text.toLowerCase().includes(term);
    let anyVisible = false;

    host.querySelectorAll('.tree-subject').forEach((subject) => {
      const subjectHit = matches(subject.querySelector('.tree-subject-name').textContent);
      let subjectVisible = false;

      subject.querySelectorAll('.tree-chapter').forEach((chapter) => {
        // A chapter matches on its own name, on any file inside it, or
        // because the subject above it already matched.
        const chapterHit =
          subjectHit || matches(chapter.querySelector('.tree-chapter-name').textContent);
        let hits = 0;

        chapter.querySelectorAll('.tree-file').forEach((row) => {
          const hit = chapterHit || matches(row.textContent);
          row.hidden = !hit;
          if (hit) hits += 1;
        });

        chapter.hidden = Boolean(term) && !chapterHit && hits === 0;
        if (!chapter.hidden) subjectVisible = true;
      });

      subject.hidden = Boolean(term) && !subjectHit && !subjectVisible;
      if (!subject.hidden) anyVisible = true;
    });

    nothing.hidden = !term || anyVisible;
  };

  input.addEventListener('input', apply);
  input.addEventListener('search', apply);

  // A batch can carry a dozen chapters. Opening them one at a time is the
  // file-manager annoyance this whole screen exists to avoid.
  host.querySelectorAll('[data-tree]').forEach((button) => {
    button.addEventListener('click', () => {
      const open = button.dataset.tree === 'expand';
      host.querySelectorAll('#content-tree details').forEach((details) => {
        details.open = open;
      });
    });
  });
}

/**
 * The batch's own timetable, above its curriculum.
 *
 * `/schedule/?course=` is public: a batch page may show when its classes air
 * before anyone enrols — exactly what a PW batch page does with its Schedule
 * strip. A recording the visitor cannot open still appears in the list as
 * locked, because "there is a class at 7" is true for everyone.
 *
 * A failure here does not take the page down: the curriculum is below it and
 * is the reason the page exists.
 */
async function loadBatchSchedule() {
  const host = $('#class-timetable');
  if (!host || !current) return;

  let payload;
  try {
    payload = await getJson(`/schedule/${apiQuery({ course: current.slug, days: 14 })}`);
  } catch {
    host.innerHTML = '<p class="tiny muted" style="margin:0">The timetable could not be loaded. The curriculum below is unaffected.</p>';
    return;
  }

  const entries = (payload.groups || []).flatMap((group) => group.classes);
  // `ahead` stays unsliced so the head can count what the strip left out;
  // slicing it first made every strip look complete.
  const ahead = entries.filter((entry) => entry.status !== 'ended');
  const shown = ahead.length ? ahead.slice(0, 6) : entries.slice(-3);

  if (!shown.length) {
    host.innerHTML = `
      <div class="batch-schedule-head">
        <strong>Class schedule</strong>
        <span class="tiny subtle">Next 14 days</span>
      </div>
      <p class="tiny muted" style="margin:0">No class has an air time yet. The lessons below can be watched on demand.</p>`;
    return;
  }

  // A strip cannot be the whole timetable. When it stops short, say so
  // instead of letting six rows look like all of them.
  const rest = ahead.length - shown.length;
  const scope = rest > 0 ? `${rest} more below` : ahead.length ? 'Next 14 days' : 'Last 14 days';

  host.innerHTML = `
    <div class="batch-schedule-head">
      <strong>${ahead.length ? 'Next classes' : 'Recent classes'}</strong>
      <span class="tiny subtle">${scope}</span>
    </div>
    <div class="day-schedule">
      ${shown.map((entry) => scheduleRow(entry, { showCourse: false, timeZone: payload.timezone || '' })).join('')}
    </div>`;
}

/** The batch's papers, card for card, from `/quizzes/?course=`. */
function renderPapers(testRows) {
  const host = $('#panel-papers');
  if (!testRows.length) {
    host.innerHTML = emptyState({
      title: 'No papers in this batch yet',
      body: 'A published paper appears here with its duration and marking scheme.',
      actionLabel: 'All papers',
      actionHref: 'tests.html',
      iconName: 'file-text'
    });
    return;
  }
  host.innerHTML = `<div class="test-grid">${testRows.map(adaptTest).map((t) => testCardFor(t)).join('')}</div>`;
}

/** A local copy so this module does not import the card twice. */
function testCardFor(test) {
  const locked = test.locked;
  return `
    <article class="test-card">
      <div class="test-card-top">
        <span class="test-eyebrow">${esc(test.subject)} · ${esc(test.kind)}</span>
        <span class="badge ${locked ? 'badge-paid' : 'badge-free'}">${locked ? 'Enrol' : 'Open'}</span>
      </div>
      <h3 class="test-title">${esc(test.title)}</h3>
      <p class="test-meta">${test.questions} Questions · ${test.marks} Marks</p>
      <p class="test-meta">${test.duration} minutes</p>
      <div class="test-card-foot">
        <span class="tiny subtle">${test.opensAt ? shortDate(test.opensAt) : 'Always open'}</span>
        ${
          locked
            ? '<span class="badge badge-outline">Enrol to unlock</span>'
            : `<a class="btn btn-primary btn-sm" href="test-player.html?test=${test.id}">Start Test</a>`
        }
      </div>
    </article>`;
}

/**
 * The teachers on this batch, straight from `GET /courses/<id>/` → `faculty`.
 *
 * This list used to be hard-coded to an empty state: the tab existed and no
 * table answered it. It now renders what the provider typed in, and says so
 * plainly when a batch genuinely lists nobody.
 */
function renderTeachers() {
  const host = $('#panel-teachers');
  const people = current.faculty || [];

  if (!people.length) {
    host.innerHTML = emptyState({
      title: 'No faculty listed',
      body: 'This batch does not name its teachers yet. Its classes and notes are already in the Classes and Notes tabs.',
      iconName: 'users'
    });
    return;
  }

  host.innerHTML = `
    <div class="faculty-grid">
      ${people
        .map(
          (person) => `
        <article class="faculty-card">
          <span class="faculty-avatar" aria-hidden="true">${
            person.avatar_url
              ? `<img src="${esc(person.avatar_url)}" alt="" loading="lazy">`
              : esc(initials(person.name))
          }</span>
          <div class="faculty-body">
            <strong>${esc(person.name)}</strong>
            ${person.subject ? `<span class="badge badge-outline">${esc(person.subject)}</span>` : ''}
            ${person.bio ? `<p class="small muted" style="margin:6px 0 0">${esc(person.bio)}</p>` : ''}
          </div>
        </article>`
        )
        .join('')}
    </div>`;
}

/** The four questions the access model raises, answered from this batch. */
function faqItems() {
  return [
    ['Is this batch free?', current.free ? 'Yes. Press Enrol and the batch is added to your account — recordings and notes open straight away.' : 'No — it unlocks with an access code from your institute. There is no card payment on this platform.'],
    ['Do I need an account?', 'Browsing does not need one, but joining a batch and keeping your progress and notes does.'],
    ['How do I get the code?', current.telegramDm ? `Press Get code to message ${current.telegramHandle || 'the teacher'} on Telegram; the batch name and number are already in the message. Then paste the code they send you under “Redeem access code”.` : 'Ask your institute for a code, then paste it under “Redeem access code”.'],
    ['Can I attempt the papers?', 'Any published paper that is open can be started from the Papers tab. Paid papers need the batch unlocked first.']
  ];
}

function renderAside() {
  const host = $('#course-aside');
  const facts = [
    ['Subject', current.subject],
    ['Price', current.free ? 'Free' : money(current.price)],
    ['Chapters', String(current.folders.length)],
    ['Tests', String(current.tests)],
    ['Access', current.hasAccess ? 'Unlocked' : 'Locked']
  ];
  host.innerHTML = `
    <div class="facts-card">
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
      ${
        current.free || current.hasAccess
          ? `<a class="btn btn-primary btn-block" style="margin-top:var(--sp-4)" href="#panel-classes" data-open-tab="classes">Class schedule</a>`
          : `${
              current.telegramDm
                ? `<a class="btn btn-primary btn-block" style="margin-top:var(--sp-4)" href="${esc(current.telegramDm)}" target="_blank" rel="noopener" data-get-code>${icon('message')} Get code</a>`
                : ''
            }<button class="btn btn-accent btn-block" style="margin-top:${current.telegramDm ? '10px' : 'var(--sp-4)'}" type="button" data-redeem>Redeem code</button>`
      }
    </div>`;
}

async function loadSimilar() {
  const host = $('#similar-grid');
  if (!host) return;
  try {
    const payload = await getJson('/courses/?page_size=6');
    const list = rows(payload)
      .map(adaptCourse)
      .filter((course) => course.slug !== current.slug)
      .slice(0, 3);
    host.innerHTML = list.length
      ? list.map(batchCard).join('')
      : '<p class="small muted">This is the only published batch right now.</p>';
  } catch {
    host.innerHTML = '<p class="small muted">Other batches could not be loaded.</p>';
  }
}

/* ------------------------------------------------------------------ */
/* Behaviour                                                          */
/* ------------------------------------------------------------------ */

/**
 * The tab strip: four panels, one visible, and the choice written into the URL.
 *
 * `?tab=classes` is a link a teacher can send and a student can bookmark. The
 * strip follows the ARIA tabs pattern — one tab in the tab order (roving
 * tabindex), arrow keys move between tabs, Home and End jump to the ends.
 *
 * Notes used to be a fifth tab. They are files inside a chapter now, which is
 * where a learner looks for them, so a tab listing them again would be a
 * second answer to the same question. `?tab=notes` falls back to Overview.
 */
const TABS = ['overview', 'classes', 'papers', 'teachers'];

function tabFromUrl() {
  const wanted = (qsParam('tab') || '').toLowerCase();
  return TABS.includes(wanted) ? wanted : 'overview';
}

function writeTabToUrl(name, { push }) {
  const url = new URL(location.href);
  if (name === 'overview') url.searchParams.delete('tab');
  else url.searchParams.set('tab', name);
  const next = `${url.pathname}${url.search}${url.hash}`;
  if (next === `${location.pathname}${location.search}${location.hash}`) return;
  if (push) history.pushState({ tab: name }, '', next);
  else history.replaceState({ tab: name }, '', next);
}

function selectTab(name, { push = true, focus = false } = {}) {
  const chosen = TABS.includes(name) ? name : 'overview';
  $$('.tabs .tab').forEach((tab) => {
    const selected = tab.dataset.tab ? tab.dataset.tab === chosen : chosen === 'overview';
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
    const panel = document.getElementById(tab.getAttribute('aria-controls'));
    if (panel) panel.hidden = !selected;
  });
  writeTabToUrl(chosen, { push });
}

function initTabs() {
  const tabs = $$('.tabs .tab');
  const nameOf = (tab) => tab.dataset.tab || 'overview';

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

  // Back and forward move between the tabs the visitor actually opened.
  window.addEventListener('popstate', () => selectTab(tabFromUrl(), { push: false }));

  // A deep link opens on its own tab; an unknown one falls back to Overview.
  selectTab(tabFromUrl(), { push: false });
}

function wireEnroll() {
  // Its own listener: joining a free batch must not depend on the redeem
  // dialog existing on the page.
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-enroll]');
    if (!button) return;

    if (!isSignedIn()) {
      location.href = `login.html?next=${encodeURIComponent(`course.html?slug=${current.slug}`)}`;
      return;
    }

    const label = button.textContent;
    button.disabled = true;
    button.textContent = 'Joining…';
    request(`/courses/${current.id}/enroll/`, { method: 'POST' })
      .then(() => {
        toast('Batch joined. Opening its classes…', 'success');
        setTimeout(() => location.reload(), 600);
      })
      .catch((err) => {
        button.disabled = false;
        button.textContent = label;
        toast(err?.message || 'That batch could not be joined.', 'danger');
      });
  });
}

function wireRedeem() {
  const modal = $('#redeem-modal');
  if (!modal) return;

  const open = () => {
    modal.classList.add('is-open');
    document.body.classList.add('is-locked');
    // The "message the teacher" row is built here, not in the markup: on a
    // batch with no Telegram username there is nothing to link to, and an
    // empty row would be a dead end.
    const ask = $('#redeem-ask');
    if (ask) {
      ask.hidden = !current.telegramDm;
      if (current.telegramDm) {
        ask.innerHTML = `
          <span class="alert alert-info" style="margin:0">
            ${icon('message')}
            <span>No code yet? <a class="link strong" href="${esc(current.telegramDm)}" target="_blank" rel="noopener">Message ${esc(current.telegramHandle || 'your teacher')} on Telegram</a> — the chat opens with this batch already named.</span>
          </span>`;
      }
    }
    setTimeout(() => $('#code-input')?.focus(), 60);
  };
  const close = () => {
    modal.classList.remove('is-open');
    document.body.classList.remove('is-locked');
  };

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-get-code]')) {
      // Opening Telegram is all this button does; it must never be mistaken
      // for a redeem, so it is handled before the redeem branch.
      return;
    }
    if (event.target.closest('[data-redeem]')) {
      if (!isSignedIn()) {
        location.href = `login.html?next=${encodeURIComponent(`course.html?slug=${current.slug}`)}`;
        return;
      }
      open();
    }
    if (event.target.closest('[data-close-modal]') || event.target === modal) close();
    if (event.target.closest('[data-share]')) {
      const url = location.href;
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(url).then(
          () => toast('Batch link copied.', 'success'),
          () => toast('Copy the address bar to share this batch.', 'info')
        );
      } else {
        toast('Copy the address bar to share this batch.', 'info');
      }
    }
    const opener = event.target.closest('[data-open-tab]');
    if (opener) {
      // An in-page button that means "show me that tab" — it must move the tab
      // strip too, or the button and the highlighted tab disagree.
      event.preventDefault();
      selectTab(opener.dataset.openTab, { push: true });
      document.getElementById('batch-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('is-open')) close();
  });

  $('#redeem-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const error = $('#redeem-error');
    const button = form.querySelector('button[type="submit"]');
    const code = String(new FormData(form).get('code') || '').trim();
    error.hidden = true;
    button.disabled = true;
    button.textContent = 'Checking…';
    try {
      await request('/access-codes/redeem/', { method: 'POST', body: { code, course_id: current.id } });
      toast('Batch unlocked. Loading your lessons…', 'success');
      setTimeout(() => location.reload(), 700);
    } catch (err) {
      error.hidden = false;
      error.textContent = err?.message || 'That code could not be redeemed.';
      button.disabled = false;
      button.textContent = 'Unlock batch';
    }
  });
}

wireRetry();
loadCourse();
