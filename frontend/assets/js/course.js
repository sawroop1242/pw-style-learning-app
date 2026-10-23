/** Batch detail: headline, purchase panel, tabs, curriculum and similar rows. */

import {
  $, $$, esc, live, money, discountPercent, shortDate, longDate,
  initials, qsParam, isSignedIn, request
} from './core.js';
import { mountChrome, batchCard, icon, thumbTone, emptyState, toast } from './ui.js';
import { COURSES } from './data.js';

mountChrome('courses');

/* ------------------------------------------------------------------ */
/* Curriculum fixtures                                                */
/* ------------------------------------------------------------------ */

const CURRICULUM = {
  Physics: [
    { title: 'Units, dimensions and errors', lessons: 6, minutes: 214, free: true },
    { title: 'Kinematics and relative motion', lessons: 9, minutes: 342, free: true },
    { title: 'Laws of motion and friction', lessons: 8, minutes: 301 },
    { title: 'Work, energy and power', lessons: 7, minutes: 268 },
    { title: 'Rotational motion', lessons: 11, minutes: 412 },
    { title: 'Thermodynamics and kinetic theory', lessons: 10, minutes: 366 }
  ],
  Chemistry: [
    { title: 'Some basic concepts of chemistry', lessons: 5, minutes: 188, free: true },
    { title: 'Atomic structure', lessons: 8, minutes: 296, free: true },
    { title: 'Chemical bonding and molecular structure', lessons: 10, minutes: 372 },
    { title: 'Thermodynamics', lessons: 7, minutes: 254 },
    { title: 'Equilibrium and redox', lessons: 9, minutes: 331 },
    { title: 'Organic chemistry — basic principles', lessons: 12, minutes: 448 }
  ],
  Biology: [
    { title: 'The living world and classification', lessons: 5, minutes: 176, free: true },
    { title: 'Cell — structure and function', lessons: 9, minutes: 318, free: true },
    { title: 'Cell cycle and cell division', lessons: 6, minutes: 224 },
    { title: 'Plant physiology', lessons: 11, minutes: 402 },
    { title: 'Human physiology', lessons: 14, minutes: 512 },
    { title: 'Genetics and evolution', lessons: 12, minutes: 436 }
  ],
  Mathematics: [
    { title: 'Sets, relations and functions', lessons: 6, minutes: 208, free: true },
    { title: 'Complex numbers and quadratic equations', lessons: 8, minutes: 288, free: true },
    { title: 'Matrices and determinants', lessons: 7, minutes: 246 },
    { title: 'Permutations and combinations', lessons: 6, minutes: 214 },
    { title: 'Limits, continuity and differentiability', lessons: 10, minutes: 358 },
    { title: 'Integral calculus', lessons: 9, minutes: 326 }
  ],
  Reasoning: [
    { title: 'Number series and analogy', lessons: 5, minutes: 168, free: true },
    { title: 'Coding–decoding and blood relations', lessons: 6, minutes: 204, free: true },
    { title: 'Syllogism and seating arrangement', lessons: 8, minutes: 276 },
    { title: 'Non-verbal reasoning', lessons: 6, minutes: 198 },
    { title: 'Data interpretation', lessons: 7, minutes: 232 }
  ]
};

const DEFAULT_CURRICULUM = [
  { title: 'Foundations and orientation', lessons: 4, minutes: 142, free: true },
  { title: 'Core concepts — part 1', lessons: 9, minutes: 312, free: true },
  { title: 'Core concepts — part 2', lessons: 8, minutes: 288 },
  { title: 'Applied problems', lessons: 7, minutes: 244 },
  { title: 'Revision and previous year questions', lessons: 6, minutes: 216 }
];

/* ------------------------------------------------------------------ */
/* Resolve the batch                                                  */
/* ------------------------------------------------------------------ */

const slug = qsParam('slug') || qsParam('id');

function matchFixture(raw) {
  return (
    COURSES.find((c) => c.slug === (raw.slug || slug)) ||
    COURSES.find((c) => String(c.id) === String(raw.id ?? slug)) ||
    COURSES[0]
  );
}

function normalise(raw) {
  const fixture = matchFixture(raw || {});
  const subject = raw?.subject || fixture.subject;
  return {
    ...fixture,
    ...raw,
    subject,
    exam: fixture.exam || subject,
    faculty: fixture.faculty || [],
    rating: fixture.rating || 4.7,
    ratingCount: fixture.ratingCount || 0,
    learners: fixture.learners || 0,
    lessons: raw?.lesson_count ?? fixture.lessons ?? 0,
    tests: fixture.tests ?? 0,
    language: fixture.language || 'Hinglish',
    mrp: fixture.mrp || (raw?.price ? Math.round(Number(raw.price) * 2.4) : 0),
    durationMonths: fixture.durationMonths || 12,
    startsOn: fixture.startsOn || null,
    badge: fixture.badge || null,
    description: raw?.description || fixture.description,
    title: raw?.title || fixture.title,
    slug: raw?.slug || fixture.slug,
    id: raw?.id ?? fixture.id
  };
}

async function loadCourse() {
  let course;
  try {
    const { data } = await live(`/courses/?slug=${encodeURIComponent(slug || '')}`, null, { timeout: 2200 });
    const rows = data ? (Array.isArray(data) ? data : data.results || []) : [];
    course = normalise(rows[0] || {});
  } catch {
    course = normalise({});
  }
  if (!course?.title) course = normalise({});
  render(course);
  return course;
}

/* ------------------------------------------------------------------ */
/* Render                                                             */
/* ------------------------------------------------------------------ */

let current = null;

function render(course) {
  current = course;
  document.title = `${course.title} — StudySpace`;
  const crumb = $('#crumb-title');
  if (crumb) crumb.textContent = course.title;

  renderHeadline(course);
  renderPurchase(course);
  renderOverview(course);
  renderCurriculum(course);
  renderTests(course);
  renderFaculty(course);
  renderAside(course);
  renderSimilar(course);
  wireTabs();
  wireRedeem(course);
}

function renderHeadline(course) {
  const host = $('#course-headline');
  const off = discountPercent(course.price, course.mrp);
  host.innerHTML = `
    <div class="badges">
      ${course.pricing_mode === 'free'
        ? '<span class="badge badge-free">Free batch</span>'
        : '<span class="badge badge-live">Live + recorded</span>'}
      <span class="badge badge-dark">${esc(course.exam)}</span>
      ${off ? `<span class="badge badge-hot">${off}% off</span>` : ''}
    </div>
    <span class="course-title">${esc(course.title)}</span>
    <p class="course-hero-lead">${esc(course.description || '')}</p>
    <div class="course-hero-meta">
      <div><svg><use href="#i-star"/></svg> ${course.rating.toFixed(1)} · ${course.ratingCount ? `${course.ratingCount.toLocaleString('en-IN')} ratings` : 'New batch'}</div>
      <div><svg><use href="#i-users"/></svg> ${course.learners.toLocaleString('en-IN')} enrolled</div>
      <div><svg><use href="#i-play"/></svg> ${course.lessons} lessons</div>
      <div><svg><use href="#i-file-text"/></svg> ${course.tests} tests</div>
      <div><svg><use href="#i-globe"/></svg> ${esc(course.language)}</div>
    </div>`;
}

function renderPurchase(course) {
  const host = $('#purchase-slot');
  const off = discountPercent(course.price, course.mrp);
  const isFree = course.pricing_mode === 'free' || Number(course.price) === 0;
  host.innerHTML = `
    <div class="purchase-card">
      <div class="purchase-preview ${thumbTone(course.subject)}">
        <span class="glyph">${esc(course.exam)}</span>
      </div>
      <div class="purchase-body">
        <div class="purchase-price">
          <span class="now">${money(course.price)}</span>
          ${course.mrp > course.price ? `<span class="was">${money(course.mrp)}</span>` : ''}
          ${off ? `<span class="off">${off}% off</span>` : ''}
        </div>
        ${
          course.startsOn
            ? `<p class="tiny muted">Batch starts <strong class="strong">${longDate(course.startsOn)}</strong></p>`
            : ''
        }
        <a class="btn ${isFree ? 'btn-primary' : 'btn-accent'} btn-lg btn-block" href="dashboard.html" data-primary-cta>
          ${isFree ? 'Start learning free' : 'Unlock this batch'}
        </a>
        <button class="btn btn-ghost btn-block btn-sm" data-redeem ${isFree ? 'hidden' : ''}>
          ${icon('lock')} I have an access code
        </button>

        <ul class="purchase-features">
          <li>${icon('check-circle')} ${course.lessons}+ recorded lessons</li>
          <li>${icon('check-circle')} ${course.tests} tests with All-India rank</li>
          <li>${icon('check-circle')} Chapter notes and DPPs</li>
          <li>${icon('check-circle')} Doubt support on every question</li>
          <li>${icon('check-circle')} Downloadable for offline study</li>
          <li>${icon('check-circle')} Valid until the exam date</li>
        </ul>

        <div class="purchase-note">${icon('shield-check')} No card payment · access codes only</div>
      </div>
    </div>`;
}

function renderAside(course) {
  const host = $('#course-aside');
  host.innerHTML = `
    <div class="card card-pad" style="display:grid;gap:14px">
      <h2 style="font-size:var(--text-md)">Batch at a glance</h2>
      <div class="stack" style="gap:10px">
        <div class="row-between tiny"><span class="muted">Language</span><strong>${esc(course.language)}</strong></div>
        <div class="row-between tiny"><span class="muted">Duration</span><strong>${course.durationMonths} months</strong></div>
        <div class="row-between tiny"><span class="muted">Starts</span><strong>${course.startsOn ? shortDate(course.startsOn) : 'Anytime'}</strong></div>
        <div class="row-between tiny"><span class="muted">Lessons</span><strong>${course.lessons}</strong></div>
        <div class="row-between tiny"><span class="muted">Tests</span><strong>${course.tests}</strong></div>
        <div class="row-between tiny"><span class="muted">Validity</span><strong>Till exam</strong></div>
      </div>
      <hr>
      <div class="row" style="gap:8px">
        <button class="btn btn-ghost btn-sm" style="flex:1" data-share>${icon('share')} Share</button>
        <button class="btn btn-ghost btn-sm" style="flex:1" data-bookmark>${icon('bookmark')} Save</button>
      </div>
    </div>

    <div class="card card-pad" style="margin-top:16px;display:grid;gap:12px;background:var(--violet-50);border-color:#ddd6fe">
      <div class="row" style="gap:10px">
        <span class="avatar avatar-teal">${icon('message')}</span>
        <div>
          <strong style="display:block;font-size:13px">Not sure if this batch fits?</strong>
          <small class="tiny muted">Talk to a counsellor before you commit.</small>
        </div>
      </div>
      <button class="btn btn-primary btn-sm" data-counsellor>Request a callback</button>
    </div>`;
}

function renderOverview(course) {
  const host = $('#panel-overview');
  host.innerHTML = `
    <div class="card card-pad" style="display:grid;gap:18px">
      <div class="prose">
        <h3 style="margin-top:0">About this batch</h3>
        <p>${esc(course.description || '')}</p>
        <p>Classes run live five days a week and every session is recorded within two hours, so a missed class never becomes a gap. Each chapter closes with a timed test scored on the server, and a revision note you can keep.</p>
        <h3>What you get</h3>
        <ul>
          <li>${icon('check')}<span><strong>Live classes</strong> with in-class polls and instant doubt windows.</span></li>
          <li>${icon('check')}<span><strong>Recorded lectures</strong> available within two hours, downloadable on Wi-Fi.</span></li>
          <li>${icon('check')}<span><strong>Daily practice problems</strong> with worked solutions released after the deadline.</span></li>
          <li>${icon('check')}<span><strong>Full-length mocks</strong> in the real exam interface, with All-India rank.</span></li>
          <li>${icon('check')}<span><strong>Chapter notes</strong> in the same place as your own notes and bookmarks.</span></li>
        </ul>
        <h3>Who this is for</h3>
        <p>Students preparing for ${esc(course.exam)} who want a fixed weekly rhythm rather than a pile of unlinked videos. If you are starting from scratch, begin with the free chapter tests before unlocking the full batch.</p>
      </div>

      <div class="alert alert-warn">
        <svg><use href="#i-info"/></svg>
        <span><strong>Sample content.</strong> This is a demonstration build — batch names, faculty and statistics are illustrative, not a real offering.</span>
      </div>
    </div>`;
}

function renderCurriculum(course) {
  const chapters = CURRICULUM[course.subject] || DEFAULT_CURRICULUM;
  const host = $('#panel-curriculum');
  const totalLessons = chapters.reduce((n, c) => n + c.lessons, 0);
  const totalMinutes = chapters.reduce((n, c) => n + c.minutes, 0);

  host.innerHTML = `
    <div class="row-between" style="margin-bottom:14px;flex-wrap:wrap;gap:10px">
      <p class="small muted">${chapters.length} chapters · ${totalLessons} lessons · ${(totalMinutes / 60).toFixed(1)} hours</p>
      <span class="badge badge-outline">${icon('play')} 2 free chapters</span>
    </div>
    <div class="accordion">
      ${chapters
        .map(
          (ch, i) => `
        <div class="acc-item">
          <button class="acc-head" aria-expanded="${i === 0}" aria-controls="ch-${i}">
            <span class="acc-num">${String(i + 1).padStart(2, '0')}</span>
            <span class="acc-title">${esc(ch.title)}</span>
            <span class="acc-count">${ch.lessons} lessons</span>
            <svg class="acc-chevron"><use href="#i-chevron-down"/></svg>
          </button>
          <div class="acc-panel" id="ch-${i}" ${i === 0 ? '' : 'hidden'}>
            ${Array.from({ length: Math.min(ch.lessons, 4) })
              .map(
                (_, n) => `
              <div class="lesson-row ${ch.free && n === 0 ? 'is-free' : ''}">
                ${icon(ch.free && n === 0 ? 'play' : 'lock', ch.free && n === 0 ? '' : 'lr-lock')}
                <span class="lr-title">${esc(ch.title)} — part ${n + 1}</span>
                <span class="lr-dur">${Math.round(ch.minutes / Math.min(ch.lessons, 4))} min</span>
              </div>`
              )
              .join('')}
            ${
              ch.lessons > 4
                ? `<div class="lesson-row" style="color:var(--violet-700);font-weight:600">${icon('plus')} ${ch.lessons - 4} more lessons</div>`
                : ''
            }
          </div>
        </div>`
        )
        .join('')}
    </div>`;
}

function renderTests(course) {
  const host = $('#panel-tests');
  const rows = [
    { name: 'Chapter test — after every unit', count: Math.max(1, Math.round(course.tests * 0.6)), marks: 40 },
    { name: 'Sectional tests — every two weeks', count: Math.max(1, Math.round(course.tests * 0.28)), marks: 100 },
    { name: 'Full-length mock — monthly', count: Math.max(1, Math.round(course.tests * 0.12)), marks: 300 }
  ];
  host.innerHTML = `
    <div class="stack">
      ${rows
        .map(
          (r) => `
        <div class="card card-pad row-between" style="gap:14px;flex-wrap:wrap">
          <div style="display:flex;gap:12px;align-items:center">
            <span class="test-icon">${icon('target')}</span>
            <div>
              <strong style="display:block;font-size:14px">${esc(r.name)}</strong>
              <small class="tiny muted">${r.count} tests · up to ${r.marks} marks · All-India rank</small>
            </div>
          </div>
          <a class="btn btn-ghost btn-sm" href="tests.html">Preview</a>
        </div>`
        )
        .join('')}
      <div class="alert alert-info" style="margin-top:6px">
        <svg><use href="#i-info"/></svg>
        <span>Results are calculated on the server. Rank is published only after the test window closes, so early finishers cannot leak the paper.</span>
      </div>
    </div>`;
}

function renderFaculty(course) {
  const host = $('#panel-faculty');
  const rows = course.faculty?.length ? course.faculty : [{ name: 'StudySpace Faculty', role: course.subject, initials: 'SF', tone: 'violet' }];
  host.innerHTML = `
    <div class="faculty-list">
      ${rows
        .map(
          (f) => `
        <div class="faculty-row">
          <span class="avatar avatar-lg avatar-${f.tone === 'violet' ? '' : f.tone}">${esc(f.initials || initials(f.name))}</span>
          <div style="flex:1">
            <h4>${esc(f.name)}</h4>
            <p>${esc(f.role)} · 8+ years teaching ${esc(course.exam)}</p>
          </div>
          <span class="badge badge-neutral">${icon('star')} 4.8</span>
        </div>`
        )
        .join('')}
    </div>`;
}

function renderSimilar(course) {
  const host = $('#similar-grid');
  if (!host) return;
  const rows = COURSES.filter((c) => c.slug !== course.slug).slice(0, 3);
  host.innerHTML = rows.map(batchCard).join('');
}

/* ------------------------------------------------------------------ */
/* Interactions                                                       */
/* ------------------------------------------------------------------ */

function wireTabs() {
  const tabs = $$('.tab');
  const panels = {
    'tab-overview': $('#panel-overview'),
    'tab-curriculum': $('#panel-curriculum'),
    'tab-tests': $('#panel-tests'),
    'tab-faculty': $('#panel-faculty')
  };

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => activate(tab.id));
    tab.addEventListener('keydown', (e) => {
      const idx = tabs.indexOf(tab);
      if (e.key === 'ArrowRight') tabs[(idx + 1) % tabs.length].focus();
      if (e.key === 'ArrowLeft') tabs[(idx - 1 + tabs.length) % tabs.length].focus();
    });
  });

  const fromHash = location.hash.replace('#', '');
  if (panels[`tab-${fromHash}`]) activate(`tab-${fromHash}`);

  function activate(id) {
    tabs.forEach((t) => t.setAttribute('aria-selected', String(t.id === id)));
    Object.entries(panels).forEach(([key, panel]) => {
      panel.hidden = key !== id;
    });
  }

  // Accordion
  document.querySelectorAll('.acc-head').forEach((head) => {
    head.addEventListener('click', () => {
      const open = head.getAttribute('aria-expanded') === 'true';
      head.setAttribute('aria-expanded', String(!open));
      const panel = head.nextElementSibling;
      if (panel) panel.hidden = open;
    });
  });
}

function wireRedeem(course) {
  const modal = $('#redeem-modal');
  const errorNode = $('#redeem-error');

  const setError = (message) => {
    if (!errorNode) return;
    errorNode.innerHTML = message;
    errorNode.hidden = !message;
  };

  const open = () => {
    setError('');
    modal.classList.add('is-open');
    document.body.classList.add('is-locked');
    $('#code-input')?.focus();
  };
  const close = () => {
    modal.classList.remove('is-open');
    document.body.classList.remove('is-locked');
  };

  document.addEventListener('click', async (e) => {
    if (e.target.closest('[data-redeem]')) {
      open();
      if (!isSignedIn()) {
        setError(`Sign in to redeem a code. <a href="login.html?next=${encodeURIComponent(`course.html?slug=${course.slug}`)}" class="link">Sign in</a>`);
      }
    }
    if (e.target.closest('[data-close-modal]')) close();
    if (e.target === modal) close();

    if (e.target.closest('[data-share]')) {
      const url = location.href;
      try {
        if (navigator.share) await navigator.share({ title: course.title, url });
        else {
          await navigator.clipboard.writeText(url);
          toast('Link copied to clipboard.', 'success');
        }
      } catch {
        /* dismissed */
      }
    }

    if (e.target.closest('[data-bookmark]')) {
      toast(isSignedIn() ? 'Saved to your bookmarks.' : 'Sign in to save this batch.', isSignedIn() ? 'success' : 'info');
    }

    if (e.target.closest('[data-counsellor]')) {
      toast('Callback requested. Our team will call between 10am and 7pm.', 'success');
    }

    if (e.target.closest('[data-primary-cta]')) {
      if (!isSignedIn()) {
        e.preventDefault();
        location.href = 'login.html';
      }
    }
  });

  $('#redeem-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    setError('');

    const code = $('#code-input').value.trim().toUpperCase();
    if (!code) {
      setError('Enter the access code printed on your receipt.');
      return;
    }
    if (!isSignedIn()) {
      setError(`Sign in to redeem a code. <a href="login.html?next=${encodeURIComponent(`course.html?slug=${course.slug}`)}" class="link">Sign in</a>`);
      return;
    }

    const button = e.target.querySelector('button[type="submit"]');
    const label = button.textContent;
    button.disabled = true;
    button.textContent = 'Checking code…';

    try {
      await request('/access-codes/redeem/', {
        method: 'POST',
        body: { code, course_id: course.id }
      });
      toast('Batch unlocked. Opening your dashboard…', 'success');
      setTimeout(() => (location.href = 'dashboard.html'), 900);
    } catch (err) {
      if (err.status === 0) {
        setError('Could not reach the server. Check your connection and try again.');
      } else if (err.status === 404 || err.status === 400) {
        setError(err.message || 'That code is not valid for this batch. Check the characters and try again.');
      } else if (err.status === 401) {
        setError(`Your session expired. <a href="login.html?next=${encodeURIComponent(`course.html?slug=${course.slug}`)}" class="link">Sign in again</a>`);
      } else {
        setError(err.message || 'That code did not work. Try again in a moment.');
      }
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  });
}

loadCourse().then((course) => {
  const cta = document.querySelector('[data-primary-cta]');
  if (cta) cta.href = 'dashboard.html';
});
