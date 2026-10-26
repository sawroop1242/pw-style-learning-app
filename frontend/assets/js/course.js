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
  mountChrome, batchCard, icon, thumbTone, emptyState, toast, wireRetry
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
  ['#panel-overview', '#panel-curriculum', '#panel-tests', '#panel-faculty', '#panel-faq', '#course-aside', '#similar-grid'].forEach(
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
  renderCurriculum();
  renderTests(testRows);
  renderFaculty();
  renderFaq();
  renderAside();
  wireTabs();
  wireRedeem();
  loadSimilar();
}

function renderHeadline() {
  const host = $('#course-headline');
  const facts = [
    ['play', `${current.lessons} ${current.lessons === 1 ? 'lesson' : 'lessons'}`],
    ['file-text', `${current.tests} ${current.tests === 1 ? 'test' : 'tests'}`],
    ['book', `${current.folders.length} ${current.folders.length === 1 ? 'section' : 'sections'}`]
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
    cover.innerHTML = `<span class="cover-faces"><span class="cover-face">${esc(initials(current.subject || 'SS'))}</span></span>`;
  }
}

function renderPurchase() {
  const host = $('#purchase-slot');
  const isFree = current.free;
  const open = isFree || current.hasAccess;

  host.innerHTML = `
    <div class="batch-actions">
      ${
        open
          ? `<a class="btn btn-primary btn-lg" href="#panel-curriculum" data-open-curriculum>Start learning</a>`
          : `<button class="btn btn-accent btn-lg" type="button" data-redeem>Redeem access code</button>`
      }
      <button class="btn btn-ghost btn-lg" data-share>${icon('share')} Share</button>
    </div>
    ${
      isFree
        ? '<p class="tiny subtle" style="margin-top:12px">Open to every account, including guests — no code needed.</p>'
        : current.hasAccess
          ? '<p class="tiny subtle" style="margin-top:12px">Unlocked on this account. No card payment is taken on this platform.</p>'
          : `<p class="tiny subtle" style="margin-top:12px">${money(current.price)} · unlocks with an access code, no card payment</p>`
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
          ? `<a class="btn btn-primary btn-sm" href="#panel-curriculum">Start learning</a>`
          : `<button class="btn btn-accent btn-sm" type="button" data-redeem>Redeem code</button>`
      }`;
  }
}

function lessonRow(lesson) {
  return `
    <div class="lesson-item ${lesson.is_locked ? 'is-locked' : ''}">
      <span class="lesson-num">${icon(lesson.is_locked ? 'lock' : 'play')}</span>
      <span class="lesson-main">
        <strong>${esc(lesson.title)}</strong>
        <small>${lesson.duration_minutes || 0} min${lesson.is_locked ? ' · locked' : ''}</small>
      </span>
      ${
        lesson.is_locked
          ? '<span class="lesson-state" aria-hidden="true">' + icon('lock') + '</span>'
          : `<a class="link" href="player.html?lesson=${lesson.id}">Open ${icon('arrow-right')}</a>`
      }
    </div>`;
}

function pdfRow(pdf) {
  const locked = pdf.is_locked || !pdf.file_url;
  return `
    <div class="dl-row">
      <span class="dl-thumb">${icon('note')}</span>
      <span class="dl-main">
        <strong>${esc(pdf.title)}</strong>
        <small>${esc(pdf.description || 'PDF notes')}${locked ? ' · locked' : ''}</small>
      </span>
      ${
        locked
          ? '<span class="badge badge-outline">Locked</span>'
          : `<a class="dl-action" href="${esc(pdf.file_url)}" target="_blank" rel="noopener" aria-label="Open ${esc(pdf.title)}">${icon('download')}</a>`
      }
    </div>`;
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
          <li>${icon('play')}<span>${lessonCount} ${lessonCount === 1 ? 'lesson' : 'lessons'} across ${current.folders.length} ${current.folders.length === 1 ? 'section' : 'sections'}</span></li>
          <li>${icon('file-text')}<span>${current.tests} ${current.tests === 1 ? 'test' : 'tests'} attached to this batch</span></li>
          <li>${icon('note')}<span>PDF notes where the faculty uploaded them</span></li>
        </ul>
      </div>
      <div class="card card-pad">
        <strong style="display:block;margin-bottom:6px">How access works</strong>
        <p class="small muted" style="margin:0">
          ${
            current.free
              ? 'Free batches are open to everyone, including guests. Everything here can be opened straight away.'
              : current.hasAccess
                ? 'This batch is unlocked on your account. Lessons and protected notes are available.'
                : 'This is a paid batch. Enter an access code issued by your institute to unlock the lessons and protected notes.'
          }
        </p>
      </div>
    </div>`;
}

function renderCurriculum() {
  const host = $('#panel-curriculum');
  if (!current.folders.length) {
    host.innerHTML = emptyState({
      title: 'No lessons published yet',
      body: 'Sections and lessons appear here as soon as the faculty publishes them.',
      iconName: 'play'
    });
    return;
  }
  host.innerHTML = current.folders
    .map(
      (folder) => `
      <div class="card card-pad" style="margin-bottom:var(--sp-4)">
        <div class="row-between" style="margin-bottom:10px">
          <strong>${esc(folder.title)}</strong>
          <span class="tiny subtle">${(folder.lessons || []).length} ${(folder.lessons || []).length === 1 ? 'lesson' : 'lessons'}</span>
        </div>
        ${folder.description ? `<p class="small muted" style="margin:0 0 10px">${esc(folder.description)}</p>` : ''}
        <div class="lesson-list">
          ${(folder.lessons || []).map(lessonRow).join('') || '<p class="tiny subtle" style="margin:0">No lessons in this section yet.</p>'}
        </div>
        ${
          (folder.pdf_resources || []).length
            ? `<div style="margin-top:12px"><p class="tiny strong" style="margin:0 0 6px">Notes</p>${folder.pdf_resources
                .map(pdfRow)
                .join('')}</div>`
            : ''
        }
      </div>`
    )
    .join('');
}

function renderTests(testRows) {
  const host = $('#panel-tests');
  if (!testRows.length) {
    host.innerHTML = emptyState({
      title: 'No tests in this batch yet',
      body: 'A published paper appears here with its duration and marking scheme.',
      actionLabel: 'All tests',
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

function renderFaculty() {
  $('#panel-faculty').innerHTML = emptyState({
    title: 'Teacher profiles are being added',
    body: 'This batch does not list its faculty yet. Lessons and notes are already available in the Class Schedule tab.',
    iconName: 'users'
  });
}

function renderFaq() {
  const items = [
    ['Is this batch free?', current.free ? 'Yes. Every lesson and note in this batch is open to any account, including guests.' : 'No — it unlocks with an access code from your institute. There is no card payment on this platform.'],
    ['Do I need an account?', 'You can browse the batch and open free lessons without one. Signing in keeps your progress and notes attached to you.'],
    ['Can I attempt the tests?', 'Any published test that is open can be started from the Subjects tab. Paid tests need the batch unlocked first.']
  ];
  $('#panel-faq').innerHTML = items
    .map(
      ([q, a]) => `
      <div class="acc-item">
        <div class="acc-head-static"><span class="acc-title">${esc(q)}</span></div>
        <p class="acc-text">${esc(a)}</p>
      </div>`
    )
    .join('');
}

function renderAside() {
  const host = $('#course-aside');
  const facts = [
    ['Subject', current.subject],
    ['Price', current.free ? 'Free' : money(current.price)],
    ['Sections', String(current.folders.length)],
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
          ? `<a class="btn btn-primary btn-block" style="margin-top:var(--sp-4)" href="#panel-curriculum">Class schedule</a>`
          : `<button class="btn btn-accent btn-block" style="margin-top:var(--sp-4)" type="button" data-redeem>Redeem code</button>`
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

function wireTabs() {
  const tabs = $$('.tabs .tab');
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectTab(index));
    tab.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].focus();
      selectTab(next);
    });
  });
}

function selectTab(index) {
  $$('.tabs .tab').forEach((tab, i) => {
    const selected = i === index;
    tab.setAttribute('aria-selected', String(selected));
    const panel = document.getElementById(tab.getAttribute('aria-controls'));
    if (panel) panel.hidden = !selected;
  });
}

function wireRedeem() {
  const modal = $('#redeem-modal');
  if (!modal) return;

  const open = () => {
    modal.classList.add('is-open');
    document.body.classList.add('is-locked');
    setTimeout(() => $('#code-input')?.focus(), 60);
  };
  const close = () => {
    modal.classList.remove('is-open');
    document.body.classList.remove('is-locked');
  };

  document.addEventListener('click', (event) => {
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
    if (event.target.closest('[data-open-curriculum]')) {
      const tabs = $$('.tabs .tab');
      selectTab(tabs.findIndex((tab) => tab.getAttribute('aria-controls') === 'panel-curriculum'));
      document.getElementById('panel-curriculum')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
