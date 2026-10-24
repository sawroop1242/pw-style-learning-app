/**
 * Class player — a static, honest playback shell.
 *
 * There is no video endpoint in the API yet, so the stage is a still frame with
 * a real transport control that only moves the timestamp between the chapters
 * we know about. Nothing pretends to stream.
 */

import { $, $$, esc, toast } from './core.js';
import { mountChrome, icon } from './ui.js';
import { PLAYER } from './data.js';

mountChrome('');

const STATE_ICON = { done: 'check', current: 'play', open: 'play', locked: 'lock' };

function renderChapters() {
  $('#chapter-list').innerHTML = PLAYER.chapters
    .map(
      (chapter, i) => `
      <div class="lesson-item ${chapter.state === 'current' ? 'is-current' : ''} ${chapter.state === 'done' ? 'is-done' : ''} ${chapter.state === 'locked' ? 'is-locked' : ''}">
        <span class="lesson-num">${chapter.state === 'done' ? icon('check') : i + 1}</span>
        <span class="lesson-main">
          <strong>${esc(chapter.title)}</strong>
          <small>${esc(chapter.duration)}</small>
        </span>
        <span class="lesson-state" aria-hidden="true">${icon(STATE_ICON[chapter.state] || 'play')}</span>
      </div>`
    )
    .join('');
}

function renderNotes() {
  $('#note-list').innerHTML = PLAYER.notes
    .map(
      (note) => `
      <div class="note-row">
        <span class="row-icon">${icon('note')}</span>
        <span class="row-main"><strong>${esc(note.title)}</strong><small>${esc(note.meta)}</small></span>
        <button class="icon-btn" type="button" aria-label="Download ${esc(note.title)}" data-download="${esc(note.title)}">${icon('download')}</button>
      </div>`
    )
    .join('');
}

function renderDoubts() {
  $('#doubt-list').innerHTML = PLAYER.doubts
    .map(
      (doubt) => `
      <div class="doubt-row">
        <span class="row-icon">${icon('message')}</span>
        <span class="row-main"><strong>${esc(doubt.title)}</strong><small>${esc(doubt.by)} · ${esc(doubt.meta)}</small></span>
      </div>`
    )
    .join('');
}

/* Tabs */
const tabs = $$('.tabs .tab');
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTab(index));
});
function selectTab(index) {
  tabs.forEach((tab, i) => {
    const selected = i === index;
    tab.setAttribute('aria-selected', String(selected));
    const panel = document.getElementById(tab.getAttribute('aria-controls'));
    if (panel) panel.hidden = !selected;
  });
}
$$('.tabs [role="tab"]').forEach((tab, i) => {
  tab.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const next = (i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    selectTab(next);
  });
});

/* Transport — moves between chapters, nothing more */
let cursor = PLAYER.chapters.findIndex((c) => c.state === 'current');
const track = document.querySelector('[data-track]');
const position = document.querySelector('[data-position]');

function move(delta) {
  const next = Math.min(PLAYER.chapters.length - 1, Math.max(0, cursor + delta));
  if (next === cursor) {
    toast(delta > 0 ? 'That is the last chapter in this class.' : 'This is the first chapter.', 'info');
    return;
  }
  cursor = next;
  const chapter = PLAYER.chapters[cursor];
  position.textContent = ['12:34', '58:04', '1:00:15', '1:00:15'][cursor] || '00:00';
  track.style.width = `${((cursor + 1) / PLAYER.chapters.length) * 100}%`;
  if (chapter.state === 'locked') {
    toast('This chapter unlocks when your institute releases it.', 'info', 5000);
  }
}

document.querySelector('[data-next]')?.addEventListener('click', () => move(1));
document.querySelector('[data-prev]')?.addEventListener('click', () => move(-1));
document.querySelector('[data-play]')?.addEventListener('click', (e) => {
  e.currentTarget.innerHTML = icon('play');
  toast('Streaming is not wired up in this build — the class list and notes are.', 'info', 5000);
});
document.querySelector('[data-bookmark]')?.addEventListener('click', (e) => {
  const on = e.currentTarget.classList.toggle('is-on');
  toast(on ? 'Saved to your bookmarks.' : 'Removed from your bookmarks.', 'success');
});
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-download]');
  if (!btn) return;
  toast(`“${btn.dataset.download}” is available inside the batch downloads page.`, 'info', 4500);
});

renderChapters();
renderNotes();
renderDoubts();
