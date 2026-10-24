/**
 * Khazana — the free subject library.
 * Subject counts come from the bundled catalogue (patched by the API's course
 * list when it answers); the free-batch grid uses the same adapter as Home.
 */

import { $, esc, live, initials, storage, qsParam, adaptCourse } from './core.js';
import { mountChrome, batchCard, icon, skeletonBatchGrid } from './ui.js';
import { SUBJECTS, COURSES } from './data.js';

mountChrome('khazana');

const avatar = document.querySelector('[data-welcome-avatar]');
if (avatar) avatar.textContent = initials(storage.user?.username || 'Student');

function renderSubjects(selected) {
  const host = $('#subject-grid');
  host.innerHTML = SUBJECTS.map(
    (subject) => `
    <a class="subject-tile" href="khazana.html?subject=${encodeURIComponent(subject.name)}"
       ${subject.name === selected ? 'aria-current="true"' : ''}>
      <span class="subject-icon tone-${subject.tone}">${icon(subject.icon)}</span>
      <span class="subject-body">
        <strong>${esc(subject.name)}</strong>
        <small>${subject.chapters} ${subject.chapters === 1 ? 'chapter' : 'chapters'} · ${subject.lectures} ${subject.lectures === 1 ? 'lecture' : 'lectures'}</small>
      </span>
    </a>`
  ).join('');

  const totalChapters = SUBJECTS.reduce((n, s) => n + s.chapters, 0);
  const totalLectures = SUBJECTS.reduce((n, s) => n + s.lectures, 0);
  $('#khazana-count').textContent = `${SUBJECTS.length} subjects · ${totalChapters} chapters · ${totalLectures} lectures`;
}

async function renderFree() {
  const grid = $('#free-grid');
  grid.innerHTML = skeletonBatchGrid(3);
  const { data } = await live('/courses/?page_size=60', COURSES);
  const rows = (Array.isArray(data) ? data : data.results || []).map(adaptCourse);
  const free = rows.filter((c) => c.pricing_mode === 'free').slice(0, 6);
  grid.innerHTML = free.length
    ? free.map(batchCard).join('')
    : `<div class="empty-state">${icon('book')}<h3>No free batches yet</h3><p>Paid batches unlock with an access code from your institute. Free batches appear here as they are published.</p><a class="btn btn-ghost btn-sm" href="courses.html">Browse all batches</a></div>`;
}

renderSubjects(qsParam('subject') || '');
renderFree();
