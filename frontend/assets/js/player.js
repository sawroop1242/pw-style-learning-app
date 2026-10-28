/**
 * Class player.
 *
 * Reads one lesson from `/lessons/<id>/`, the other lessons in the same
 * section, the notes (PDFs) of that section and the batch announcements. A
 * lesson without a `video_url` shows an explicit "no recording published"
 * stage instead of a fake timestamp — the API is the only source of truth
 * about whether a recording exists.
 */

import { $, $$, esc, getJson, rows, apiQuery, qsParam, initials, shortDate } from './core.js';
import { mountChrome, icon, toast, emptyState } from './ui.js';

mountChrome('');

const lessonId = qsParam('lesson') || qsParam('id');

const STATE = { lesson: null, siblings: [], files: [], notices: [] };

function renderTabs() {
  const tabs = $$('.tabs .tab');
  const select = (index) => {
    tabs.forEach((tab, i) => {
      const selected = i === index;
      tab.setAttribute('aria-selected', String(selected));
      const panel = document.getElementById(tab.getAttribute('aria-controls'));
      if (panel) panel.hidden = !selected;
    });
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(index));
    tab.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].focus();
      select(next);
    });
  });
}

function setStage(lesson) {
  const stage = $('#player-stage');
  const face = $('#stage-face');
  const video = $('#player-video');
  const empty = $('#stage-empty');

  if (lesson.video_url) {
    stage.classList.remove('is-empty');
    video.src = lesson.video_url;
    video.hidden = false;
    empty.hidden = true;
    stage.removeAttribute('role');
    face.hidden = true;
    video.addEventListener('error', () => {
      video.hidden = true;
      face.hidden = false;
      empty.hidden = false;
      empty.querySelector('strong').textContent = 'The recording could not be opened';
      empty.querySelector('p').textContent = 'The video URL is set but the file did not load in this browser.';
    });
    return;
  }

  video.hidden = true;
  stage.classList.add('is-empty');
  empty.hidden = false;
  empty.querySelector('strong').textContent = lesson.is_locked
    ? 'This lesson is locked'
    : 'No recording published';
  empty.querySelector('p').textContent = lesson.is_locked
    ? 'Unlock the batch to watch the recording for this lesson.'
    : 'This class has no video URL yet. The description and the section notes are still available.';
  face.textContent = initials(lesson.course_title || 'SS');
  face.hidden = false;
}

function renderHead(lesson) {
  document.title = `${lesson.title} — StudySpace`;
  $('#player-title').textContent = lesson.title;
  $('#player-sub').textContent = [lesson.folder_title, lesson.course_title].filter(Boolean).join(' · ');
  const brief = $('#player-brief');
  brief.textContent = lesson.description || '';
  brief.hidden = !lesson.description;

  const stage = $('#player-stage');
  // The tone classes carry a background of their own, so they are not applied
  // here: the stage keeps the player gradient and only marks itself empty.
  stage.dataset.course = lesson.course_title || '';
}

function renderChapters(lesson) {
  const host = $('#chapter-list');
  const siblings = STATE.siblings;
  if (!siblings.length) {
    host.innerHTML = emptyState({
      title: 'No other lessons in this section',
      body: 'This is the only published lesson here right now.',
      iconName: 'play'
    });
    return;
  }

  host.innerHTML = siblings
    .map((row) => {
      const current = String(row.id) === String(lesson.id);
      const locked = row.is_locked || !row.video_url;
      return `
        <a class="lesson-item ${current ? 'is-current' : ''} ${locked && !current ? 'is-locked' : ''}"
           href="player.html?lesson=${row.id}" ${current ? 'aria-current="page"' : ''}>
          <span class="lesson-num">${current ? icon('play') : locked ? icon('lock') : icon('play')}</span>
          <span class="lesson-main">
            <strong>${esc(row.title)}</strong>
            <small>${row.duration_minutes || 0} min${current ? ' · now playing' : ''}${locked && !current ? ' · no recording' : ''}</small>
          </span>
          <span class="lesson-state" aria-hidden="true">${icon(current ? 'check' : 'arrow-right')}</span>
        </a>`;
    })
    .join('');

  // Prev / next within the section, following the API order.
  const index = siblings.findIndex((row) => String(row.id) === String(lesson.id));
  const prev = siblings[index - 1];
  const next = siblings[index + 1];
  const prevLink = $('#prev-link');
  const nextLink = $('#next-link');
  if (prev) {
    prevLink.hidden = false;
    prevLink.href = `player.html?lesson=${prev.id}`;
  }
  if (next) {
    nextLink.hidden = false;
    nextLink.href = `player.html?lesson=${next.id}`;
  }
}

function renderNotes(lesson) {
  const host = $('#note-list');
  const files = STATE.files.filter((file) => !lesson.folder || String(file.folder) === String(lesson.folder));
  if (!files.length) {
    host.innerHTML = emptyState({
      title: 'No notes for this section',
      body: 'The faculty has not uploaded notes to this section yet.',
      actionLabel: 'All downloads',
      actionHref: 'downloads.html',
      iconName: 'note'
    });
    return;
  }
  host.innerHTML = files
    .map(
      (file) => `
      <div class="dl-row">
        <span class="dl-thumb">${icon('note')}</span>
        <span class="dl-main">
          <strong>${esc(file.title)}</strong>
          <small>${esc(file.description || 'PDF notes')}</small>
        </span>
        ${
          file.file_url
            ? `<a class="dl-action" href="${esc(file.file_url)}" target="_blank" rel="noopener" aria-label="Open ${esc(file.title)}">${icon('download')}</a>`
            : '<span class="badge badge-outline">Locked</span>'
        }
      </div>`
    )
    .join('');
}

function renderNotices() {
  const host = $('#notice-list');
  if (!STATE.notices.length) {
    host.innerHTML = emptyState({
      title: 'No announcements yet',
      body: 'Announcements from the faculty for this batch appear here.',
      iconName: 'message'
    });
    return;
  }
  host.innerHTML = STATE.notices
    .map(
      (post) => `
      <article class="notice-row">
        <div class="row-between">
          <strong>${esc(post.title)}</strong>
          ${post.pinned ? '<span class="badge badge-live">Pinned</span>' : ''}
        </div>
        <p class="small muted" style="margin:6px 0 8px">${esc(post.body || '')}</p>
        <span class="tiny subtle">${esc(post.author_name || 'Faculty')} · ${esc(shortDate(post.created_at))}</span>
      </article>`
    )
    .join('');
}

async function load() {
  if (!lessonId) {
    // Nothing is selected, so the video stage would be an empty rectangle.
    const stage = $('#player-stage');
    if (stage) stage.hidden = true;
    const meta = $('.player-meta .icon-btn');
    if (meta) meta.hidden = true;
    $('#player-title').textContent = 'No lesson selected';
    $('#player-sub').textContent = '';
    $('#chapter-list').innerHTML = emptyState({
      title: 'Pick a lesson',
      body: 'Open a batch, choose a section and pick a lesson from there.',
      actionLabel: 'Browse batches',
      actionHref: 'courses.html',
      iconName: 'play'
    });
    $('#stage-empty').hidden = false;
    return;
  }

  let lesson;
  try {
    lesson = await getJson(`/lessons/${lessonId}/`);
  } catch (err) {
    $('#player-title').textContent = err.status === 404 ? 'Lesson not found' : 'This lesson could not be loaded';
    $('#player-sub').textContent = '';
    $('#stage-empty').hidden = false;
    $('#chapter-list').innerHTML = emptyState({
      title: err.status === 404 ? 'Lesson not found' : 'Lesson unavailable',
      body: err.status === 404
        ? 'It may have been unpublished, or it belongs to a batch you cannot open.'
        : err.message || 'The server did not answer.',
      actionLabel: 'Browse batches',
      actionHref: 'courses.html',
      iconName: 'alert'
    });
    return;
  }

  STATE.lesson = lesson;
  renderHead(lesson);
  setStage(lesson);

  // The section's other lessons: same batch, then keep the section's own rows.
  try {
    const payload = await getJson(`/lessons/${apiQuery({ course: lesson.course, page_size: 60 })}`);
    const all = rows(payload);
    STATE.siblings = lesson.folder ? all.filter((row) => String(row.folder) === String(lesson.folder)) : all;
  } catch {
    STATE.siblings = [];
  }
  renderChapters(lesson);

  try {
    STATE.files = rows(await getJson(`/pdfs/${apiQuery({ course: lesson.course, page_size: 60 })}`));
  } catch {
    STATE.files = [];
  }
  renderNotes(lesson);

  try {
    STATE.notices = rows(await getJson(`/community/${apiQuery({ course: lesson.course, page_size: 10 })}`));
  } catch {
    STATE.notices = [];
  }
  renderNotices();
}

$('#player-video')?.addEventListener('play', () => {
  // Nothing to fake: the element either has a source or it does not.
  const video = $('#player-video');
  if (!video.src) toast('No recording is attached to this lesson.', 'info');
});

renderTabs();
load();
