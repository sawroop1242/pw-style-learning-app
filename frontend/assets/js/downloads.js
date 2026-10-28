/**
 * Downloads — every lesson, note and paper the learner can open, in one place.
 *
 * There is no "saved for offline" endpoint, so this page does not pretend to
 * have one: it lists the media the API returns for the batches you can read,
 * and the offline promise is limited to what the service worker caches.
 */

import { $$, esc, getJson, rows, apiQuery, shortDate } from './core.js';
import { mountChrome, icon, emptyState, errorState, wireRetry } from './ui.js';

mountChrome('downloads');

function lessonRow(lesson) {
  const noVideo = !lesson.video_url;
  return `
    <div class="dl-row">
      <span class="dl-thumb">${icon('play')}</span>
      <span class="dl-main">
        <strong>${esc(lesson.title)}</strong>
        <small>${lesson.duration_minutes || 0} min${noVideo ? ' · no recording yet' : ''}${lesson.is_locked ? ' · locked' : ''}</small>
      </span>
      ${
        noVideo || lesson.is_locked
          ? '<span class="badge badge-outline">' + (lesson.is_locked ? 'Locked' : 'No video') + '</span>'
          : `<a class="dl-action" href="player.html?lesson=${lesson.id}" aria-label="Open ${esc(lesson.title)}">${icon('play')}</a>`
      }
    </div>`;
}

function pdfRow(pdf) {
  return `
    <div class="dl-row">
      <span class="dl-thumb">${icon('note')}</span>
      <span class="dl-main">
        <strong>${esc(pdf.title)}</strong>
        <small>${esc(pdf.description || 'PDF notes')}${pdf.is_locked ? ' · locked' : ''}</small>
      </span>
      ${
        pdf.file_url
          ? `<a class="dl-action" href="${esc(pdf.file_url)}" target="_blank" rel="noopener" aria-label="Open ${esc(pdf.title)}">${icon('download')}</a>`
          : '<span class="badge badge-outline">Locked</span>'
      }
    </div>`;
}

function testRow(test) {
  const locked = test.has_access === false;
  return `
    <div class="dl-row">
      <span class="dl-thumb">${icon('file-text')}</span>
      <span class="dl-main">
        <strong>${esc(test.title)}</strong>
        <small>${test.question_count} questions · ${test.duration_minutes || 0} min${test.opens_at ? ` · opens ${shortDate(test.opens_at)}` : ''}</small>
      </span>
      ${
        locked
          ? '<span class="badge badge-outline">Locked</span>'
          : `<a class="dl-action" href="test-player.html?test=${test.id}" aria-label="Start ${esc(test.title)}">${icon('play')}</a>`
      }
    </div>`;
}

function paint(host, list, render, empty) {
  if (!list.length) {
    host.innerHTML = emptyState(empty);
    return;
  }
  host.innerHTML = list.map(render).join('');
}

async function load() {
  try {
    const [lessons, pdfs, quizzes] = await Promise.all([
      getJson(`/lessons/${apiQuery({ page_size: 60, ordering: 'position' })}`),
      getJson(`/pdfs/${apiQuery({ page_size: 60 })}`),
      getJson(`/quizzes/${apiQuery({ page_size: 60 })}`)
    ]);

    // Only recordings are useful here; a lesson without a video URL cannot be
    // played, and a wall of "No video" rows is noise rather than information.
    paint(
      document.getElementById('list-lectures'),
      rows(lessons).filter((lesson) => lesson.video_url),
      lessonRow,
      {
        title: 'No recordings published yet',
        body: 'Faculty have not attached a video to any lesson in your batches. Notes and papers are still available in the other tabs.',
        actionLabel: 'Browse batches',
        actionHref: 'courses.html',
        iconName: 'play'
      }
    );
    paint(document.getElementById('list-notes'), rows(pdfs), pdfRow, {
      title: 'No notes uploaded',
      body: 'PDFs appear here once the faculty adds them to a section.',
      actionLabel: 'Browse batches',
      actionHref: 'courses.html',
      iconName: 'note'
    });
    paint(document.getElementById('list-tests'), rows(quizzes), testRow, {
      title: 'No papers published',
      body: 'Published tests appear here with their question count and duration.',
      actionLabel: 'Browse tests',
      actionHref: 'tests.html',
      iconName: 'file-text'
    });
  } catch (err) {
    document.getElementById('list-lectures').innerHTML = errorState({
      title: 'Downloads could not load',
      body: err.message || 'The server did not answer.',
      retryLabel: 'Try again'
    });
    document.getElementById('list-notes').innerHTML = '';
    document.getElementById('list-tests').innerHTML = '';
  }
}

const tabs = $$('.tabs .tab');
function selectTab(index) {
  tabs.forEach((tab, i) => {
    const selected = i === index;
    tab.setAttribute('aria-selected', String(selected));
    const panel = document.getElementById(tab.getAttribute('aria-controls'));
    if (panel) panel.hidden = !selected;
  });
}
tabs.forEach((tab, i) => {
  tab.addEventListener('click', () => selectTab(i));
  tab.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const next = (i + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    selectTab(next);
  });
});

wireRetry();
load();
