/**
 * Class player.
 *
 * Reads one lesson from `/lessons/<id>/`, the other lessons in the same
 * section, the section PDFs and the batch announcements. A lesson without a
 * `video_url` shows an explicit "no recording published" stage instead of a
 * fake timestamp — the API is the only source of truth about whether a
 * recording exists.
 *
 * Opening a class records it (`POST /progress/`), and "Mark complete" writes
 * the completed flag. Until this existed the server-side progress table was
 * never written to, so the dashboard's "Continue learning" and "Lessons done"
 * could not fill — the endpoint was implemented and nothing called it.
 */

import {
  $, $$, esc, getJson, request, rows, apiQuery, qsParam, initials, shortDate, isSignedIn
} from './core.js';
import { mountChrome, icon, toast, emptyState } from './ui.js';

mountChrome('');

const lessonId = qsParam('lesson') || qsParam('id');

const STATE = {
  lesson: null,
  siblings: [],
  files: [],
  notices: [],
  notes: [],
  progress: null,
  progressError: null
};

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

/**
 * Hosts whose URL is a *player page*, not a media file.
 *
 * `https://embed.vcdn.me/embed/<id>` is an HTML document; handing it to
 * `<video src>` shows a broken element with no explanation. Those go in an
 * iframe instead. Everything else keeps the native player, which is better
 * for captions, speed control and mobile fullscreen.
 */
const EMBED_HOSTS = ['embed.vcdn.me', 'player.vimeo.com', 'drive.google.com'];
const EMBED_PATHS = [/^\/embed\//, /\/embed\//, /\/file\/d\//];

function isEmbedUrl(raw) {
  try {
    const url = new URL(raw, location.origin);
    if (url.protocol !== 'https:') return false;
    if (EMBED_HOSTS.includes(url.hostname)) return true;
    return EMBED_HOSTS.some((host) => url.hostname === host) && EMBED_PATHS.some((re) => re.test(url.pathname));
  } catch {
    return false;
  }
}

/** The iframe an embed URL turns into, or null when the lesson has none. */
function embedFrame(lesson) {
  const host = $('#player-embed');
  if (!host) return null;
  if (!lesson.video_url || !isEmbedUrl(lesson.video_url)) {
    // Removing the node also stops playback (and any autoplay) when the
    // learner moves to a lesson without a recording.
    host.innerHTML = '';
    host.hidden = true;
    return null;
  }
  if (!host.querySelector('iframe')) {
    host.innerHTML = `
      <iframe
        src="${esc(lesson.video_url)}"
        title="${esc(lesson.title || 'Class recording')}"
        loading="lazy"
        allow="autoplay; encrypted-media; picture-in-picture; fullscreen; screen-wake-lock"
        allowfullscreen
        referrerpolicy="strict-origin-when-cross-origin"></iframe>`;
  }
  host.hidden = false;
  return host;
}

function setStage(lesson) {
  const stage = $('#player-stage');
  const face = $('#stage-face');
  const video = $('#player-video');
  const empty = $('#stage-empty');
  const frame = embedFrame(lesson);
  // Only a page with a recording gives up its chrome to the video.
  document.body.classList.toggle('has-recording', Boolean(frame || lesson.video_url));

  if (frame) {
    // An embed brings its own chrome; the page stage just holds the frame.
    stage.classList.remove('is-empty');
    video.hidden = true;
    video.removeAttribute('src');
    empty.hidden = true;
    stage.removeAttribute('role');
    face.hidden = true;
    showFullButton(true);
    return;
  }

  if (lesson.video_url) {
    stage.classList.remove('is-empty');
    video.src = lesson.video_url;
    video.hidden = false;
    empty.hidden = true;
    stage.removeAttribute('role');
    face.hidden = true;
    showFullButton(true);
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
  showFullButton(false);
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

/* ------------------------------------------------------------------ */
/* Progress                                                            */
/* ------------------------------------------------------------------ */

/**
 * Record that this lesson was opened, and paint the completion control from
 * the server's answer rather than from local memory.
 */
/* ------------------------------------------------------------------ */
/* Full screen                                                        */
/* ------------------------------------------------------------------ */

const stageEl = $('#player-stage');
const fullBtn = $('#stage-full');

const fullscreenSupported = () =>
  Boolean(document.fullscreenEnabled || document.webkitFullscreenEnabled);

const stageIsFull = () => document.fullscreenElement || document.webkitFullscreenElement;

function setFullButton(full) {
  if (!fullBtn) return;
  fullBtn.setAttribute('aria-label', full ? 'Exit full screen' : 'Full screen');
  fullBtn.innerHTML = icon(full ? 'minimize' : 'maximize');
}

/**
 * The stage button is the page's own route to full screen.
 *
 * An embed is a frame: its controls belong to the host, so on a phone the
 * learner has no way to enlarge it and no way to turn it landscape. Both are
 * browser-level operations on *our* element, which is why they live here
 * rather than inside the iframe.
 */
function showFullButton(visible) {
  if (!fullBtn) return;
  fullBtn.hidden = !visible || !fullscreenSupported();
}

/**
 * A phone held upright shows a 16:9 recording as a letterbox stripe. Locking
 * to landscape while the stage is full screen is what a native player does;
 * browsers that refuse (desktop, iOS) keep whatever orientation they have.
 */
function lockLandscape() {
  if (!window.matchMedia?.('(pointer: coarse)').matches) return;
  if (window.innerWidth > window.innerHeight) return;
  screen.orientation?.lock?.('landscape')?.catch?.(() => {});
}

async function enterStageFullscreen() {
  if (stageEl.requestFullscreen) await stageEl.requestFullscreen({ navigationUI: 'hide' });
  else if (stageEl.webkitRequestFullscreen) stageEl.webkitRequestFullscreen();
  else {
    // iPhone Safari will only full-screen a media element, never a wrapper.
    const video = $('#player-video');
    if (video?.webkitEnterFullscreen) video.webkitEnterFullscreen();
  }
}

async function toggleStageFullscreen() {
  try {
    if (stageIsFull()) {
      if (document.exitFullscreen) await document.exitFullscreen();
      else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
      return;
    }
    await enterStageFullscreen();
    if ($('#player-embed') && !$('#player-embed').hidden) lockLandscape();
  } catch {
    toast('This browser would not open the video full screen.', 'error');
  }
}

fullBtn?.addEventListener('click', toggleStageFullscreen);
document.addEventListener('fullscreenchange', () => {
  const full = Boolean(stageIsFull());
  setFullButton(full);
  if (!full) screen.orientation?.unlock?.();
});
document.addEventListener('webkitfullscreenchange', () => setFullButton(Boolean(stageIsFull())));

async function loadProgress(lesson) {
  const button = $('#mark-complete');
  if (!button) return;

  if (!isSignedIn()) {
    button.hidden = true;
    return;
  }

  button.hidden = false;
  try {
    // One row per (user, lesson): posting "opened" is safe to repeat.
    const record = await request('/progress/', {
      method: 'POST',
      body: { lesson: lesson.id, completed: false }
    });
    STATE.progress = record;
    paintProgress(record);
  } catch (err) {
    STATE.progressError = err;
    button.hidden = true;
    const status = $('#player-sub');
    if (status && err?.status !== 401) {
      status.textContent = 'Progress could not be saved — the server did not answer.';
    }
  }
}

function paintProgress(record) {
  const button = $('#mark-complete');
  const label = $('#mark-complete-label');
  if (!button || !label) return;
  const done = Boolean(record?.completed);
  button.classList.toggle('is-done', done);
  label.textContent = done ? 'Completed' : 'Mark complete';
  button.setAttribute('aria-pressed', String(done));
}

async function toggleComplete() {
  const lesson = STATE.lesson;
  if (!lesson) return;
  const button = $('#mark-complete');
  const done = Boolean(STATE.progress?.completed);
  button.disabled = true;
  try {
    const record = await request('/progress/', {
      method: 'POST',
      body: { lesson: lesson.id, completed: !done }
    });
    STATE.progress = record;
    paintProgress(record);
    toast(record.completed ? 'Marked this class complete.' : 'Marked as not finished.', 'success');
  } catch (err) {
    toast(err?.message || 'That did not save.', 'error');
  } finally {
    button.disabled = false;
  }
}

$('#mark-complete')?.addEventListener('click', toggleComplete);

/* ------------------------------------------------------------------ */
/* Notes on this lesson                                                */
/* ------------------------------------------------------------------ */

function noteRow(note) {
  return `
    <article class="note-preview" data-note="${note.id}">
      <div class="row-between" style="gap:10px;align-items:flex-start">
        <p style="margin:0">${esc(note.body)}</p>
        <button class="icon-btn" type="button" data-delete-note="${note.id}"
                aria-label="Delete this note" style="width:32px;height:32px;flex:none">
          ${icon('trash')}
        </button>
      </div>
      <span class="tiny subtle">${esc(shortDate(note.updated_at))}</span>
    </article>`;
}

function renderLessonNotes() {
  const host = $('#lesson-note-list');
  const form = $('#lesson-note-form');
  if (!host) return;

  if (!isSignedIn()) {
    if (form) form.hidden = true;
    host.innerHTML = emptyState({
      title: 'Sign in to keep notes',
      body: 'Notes are private to your account, so they are saved on the server and follow you between devices.',
      actionLabel: 'Sign in',
      actionHref: `login.html?next=${encodeURIComponent(`player.html?lesson=${lessonId}`)}`,
      iconName: 'note'
    });
    return;
  }

  if (form) form.hidden = false;
  host.innerHTML = STATE.notes.length
    ? STATE.notes.map(noteRow).join('')
    : '<p class="tiny muted" style="margin:0">No note on this class yet. Anything you write above is saved to your account.</p>';
}

async function loadLessonNotes(lesson) {
  if (!isSignedIn()) {
    STATE.notes = [];
    renderLessonNotes();
    return;
  }
  try {
    const payload = await getJson(`/notes/${apiQuery({ lesson: lesson.id, page_size: 20 })}`);
    STATE.notes = rows(payload);
  } catch {
    STATE.notes = [];
  }
  renderLessonNotes();
}

$('#lesson-note-form')?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const lesson = STATE.lesson;
  const field = $('#lesson-note-body');
  const status = $('#lesson-note-status');
  const button = $('#lesson-note-save');
  if (!lesson || !field) return;

  const body = field.value.trim();
  if (!body) {
    if (status) status.textContent = 'Write something first.';
    field.focus();
    return;
  }

  if (button) button.disabled = true;
  if (status) status.textContent = 'Saving…';
  try {
    const saved = await request('/notes/', {
      method: 'POST',
      body: {
        lesson: lesson.id,
        title: lesson.title ? `Note — ${lesson.title}` : 'Class note',
        body
      }
    });
    STATE.notes = [saved, ...STATE.notes];
    field.value = '';
    if (status) status.textContent = '';
    renderLessonNotes();
    toast('Note saved to your account.', 'success');
  } catch (err) {
    if (status) status.textContent = err?.message || 'The note did not save.';
  } finally {
    if (button) button.disabled = false;
  }
});

$('#lesson-note-list')?.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-delete-note]');
  if (!button) return;
  const id = button.getAttribute('data-delete-note');
  if (!window.confirm('Delete this note? This cannot be undone.')) return;

  button.disabled = true;
  try {
    await request(`/notes/${id}/`, { method: 'DELETE' });
    STATE.notes = STATE.notes.filter((note) => String(note.id) !== String(id));
    renderLessonNotes();
    toast('Note deleted.', 'success');
  } catch (err) {
    button.disabled = false;
    toast(err?.message || 'The note could not be deleted.', 'error');
  }
});

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
    const complete = $('#mark-complete');
    if (complete) complete.hidden = true;
    renderLessonNotes();
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

  await loadProgress(lesson);
  await loadLessonNotes(lesson);

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
