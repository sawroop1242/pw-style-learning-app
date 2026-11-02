/**
 * PDF reader.
 *
 * The provider's own viewer is framed, because that is what it is for: the
 * API's `viewer_url` is the file link (a PDF opens in the browser's viewer,
 * pdfhost's /v/ page in pdfhost's reader) with Google Drive's /view rewritten
 * to /preview. When the frame never loads — a host that sends
 * `X-Frame-Options: DENY` — the reader says so and offers the file in a new
 * tab instead of showing an empty rectangle.
 */

import { $, esc, getJson, qsParam } from './core.js';
import { mountChrome, icon, errorState, wireRetry } from './ui.js';

mountChrome('courses');

const id = qsParam('pdf');

function showProblem(title, body, href, label) {
  $('#reader-title').textContent = title;
  $('#reader-sub').textContent = '';
  $('#reader-frame').hidden = true;
  const fallback = $('#reader-fallback');
  fallback.hidden = false;
  $('#reader-fallback-title').textContent = title;
  $('#reader-fallback-body').textContent = body;
  const open = $('#reader-open');
  open.href = href || 'courses.html';
  open.textContent = label || 'My batches';
  if (!href) {
    open.removeAttribute('target');
    open.removeAttribute('rel');
  }
}

async function load() {
  if (!id) {
    showProblem('No note selected', 'Open a note from the batch it belongs to.', '', 'My batches');
    return;
  }

  let pdf;
  try {
    pdf = await getJson(`/pdfs/${encodeURIComponent(id)}/`);
  } catch (err) {
    $('#reader-wrap').innerHTML = errorState({
      title: 'This note could not load',
      body: err?.message || 'The server did not answer.',
      retryLabel: 'Try again'
    });
    wireRetry();
    return;
  }

  document.title = `${pdf.title} — StudySpace`;
  $('#reader-title').textContent = pdf.title;
  $('#reader-sub').textContent = pdf.description || '';

  if (pdf.is_locked || !pdf.viewer_url) {
    showProblem(
      'This note is locked',
      'Notes open for learners enrolled in the batch. Join the batch, then come back.',
      pdf.course ? `course.html?slug=${encodeURIComponent(pdf.course_slug || '')}` : 'courses.html',
      'Browse batches'
    );
    return;
  }

  const external = $('#reader-external');
  external.hidden = false;
  external.href = pdf.viewer_url;

  const frame = $('#reader-frame');
  frame.src = pdf.viewer_url;
  frame.hidden = false;
  $('#reader-fallback').hidden = true;

  // A frame that never fires `load` is usually a host refusing to be framed.
  // Ten seconds is long enough for a big PDF on a slow connection to start.
  let loaded = false;
  frame.addEventListener('load', () => {
    loaded = true;
  });
  setTimeout(() => {
    if (loaded || frame.hidden) return;
    showProblem(
      'Still loading…',
      'The provider is slow to answer, or it refuses to be shown inside the app. Opening it in a new tab always works.',
      pdf.viewer_url,
      'Open the PDF in a new tab'
    );
  }, 10000);
}

load();
