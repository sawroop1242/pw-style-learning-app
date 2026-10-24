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

/**
 * Merge an API row with the matching fixture.
 *
 * Fields the API owns (title, price, counts, description) always come from the
 * server. Fields it does not store yet (learners, rating, start date, language,
 * validity) come from the fixture for sample rows, and stay empty for live rows
 * rather than inventing social proof for a real batch.
 */
function normalise(raw) {
  const fixture = matchFixture(raw || {});
  const subject = raw?.subject || fixture.subject;
  const live = Boolean(raw?.id);
  return {
    ...fixture,
    ...raw,
    subject,
    exam: fixture.exam || subject,
    faculty: live ? [] : fixture.faculty || [],
    rating: live ? Number(raw.rating ?? 0) : fixture.rating || 4.7,
    ratingCount: live ? Number(raw.rating_count ?? 0) : fixture.ratingCount || 0,
    learners: live ? Number(raw.learners ?? 0) : fixture.learners || 0,
    lessons: raw?.lesson_count ?? fixture.lessons ?? 0,
    tests: raw?.quiz_count ?? (live ? 0 : fixture.tests ?? 0),
    language: live ? raw.language || null : fixture.language || 'Hinglish',
    mrp: live ? Number(raw.mrp ?? 0) : fixture.mrp || (raw?.price ? Math.round(Number(raw.price) * 2.4) : 0),
    durationMonths: live ? raw.duration_months ?? null : fixture.durationMonths || 12,
    startsOn: live ? raw.starts_on ?? null : fixture.startsOn || null,
    badge: fixture.badge || null,
    withBooks: Boolean(raw?.with_books),
    description: raw?.description || fixture.description,
    title: raw?.title || fixture.title,
    slug: raw?.slug || fixture.slug,
    id: raw?.id ?? fixture.id
  };
}

async function loadCourse() {
  let course;
  try {
    // Two hops: the list endpoint resolves the slug to an id, then the detail
    // endpoint returns the folders, lessons and lock state the page renders.
    const { data: list } = await live(`/courses/?slug=${encodeURIComponent(slug || '')}`, null, { timeout: 2200 });
    const rows = list ? (Array.isArray(list) ? list : list.results || []) : [];
    const match = rows[0];
    let detail = match;
    if (match?.id) {
      detail = await request(`/courses/${match.id}/`, { timeout: 2200 }).catch(() => match);
    }
    course = normalise(detail || {});
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
  renderFaq(course);
  renderAside(course);
  renderSimilar(course);
  wireTabs();
  wireRedeem(course);
}

function renderHeadline(course) {
  const host = $('#course-headline');
  const off = discountPercent(course.price, course.mrp);
  const faculty = course.faculty || [];

  host.innerHTML = `
    <span class="badges">
      ${course.pricing_mode === 'free'
        ? '<span class="badge badge-free">Free batch</span>'
        : '<span class="badge badge-live">Live + recorded</span>'}
      <span class="badge badge-dark">${esc(course.exam)}</span>
      ${off ? `<span class="badge badge-hot">${off}% off</span>` : ''}
    </span>
    <span class="course-title">${esc(course.title)}${course.withBooks ? '<span class="with-books">with Hindi Books</span>' : ''}</span>
    <p class="course-hero-lead">${esc(course.description || '')}</p>
    <div class="batch-facts-inline">
      <span>${icon('calendar')} Starts ${course.startsOn ? shortDate(course.startsOn) : 'soon'}</span>
      <span>${icon('play')} ${course.lessons} ${course.lessons === 1 ? 'lesson' : 'lessons'}</span>
      <span>${icon('file-text')} ${course.tests} ${course.tests === 1 ? 'test' : 'tests'}</span>
      ${course.learners ? `<span>${icon('users')} ${course.learners.toLocaleString('en-IN')} enrolled</span>` : ''}
      ${course.rating ? `<span>${icon('star')} ${course.rating.toFixed(1)}${course.ratingCount ? ` · ${course.ratingCount.toLocaleString('en-IN')} ratings` : ''}</span>` : ''}
    </div>`;

  const cover = $('#course-cover');
  if (cover) {
    cover.className = `batch-cover-lg ${thumbTone(course.subject)}`;
    cover.innerHTML = `
      ${course.withBooks ? '<span class="cover-pill">with Hindi Books</span>' : ''}
      <span class="cover-faces">
        ${faculty.length
          ? faculty.slice(0, 6).map((f) => `<span class="cover-face">${esc(f.initials || initials(f.name))}</span>`).join('')
          : `<span class="cover-face">${esc(initials(course.subject || 'SS'))}</span>`}
      </span>`;
  }
}

function renderPurchase(course) {
  const host = $('#purchase-slot');
  const off = discountPercent(course.price, course.mrp);
  const isFree = course.pricing_mode === 'free' || Number(course.price) === 0;
  host.innerHTML = `
    <div class="batch-actions">
      <a class="btn ${isFree ? 'btn-primary' : 'btn-accent'} btn-lg" href="dashboard.html" data-primary-cta>
        ${isFree ? 'Start learning free' : 'Enroll Now'}
      </a>
      <button class="btn btn-ghost btn-lg" data-share>${icon('share')} Share</button>
    </div>
    ${
      isFree
        ? ''
        : `<p class="tiny subtle" style="margin-top:12px">
             ${money(course.price)}
             ${course.mrp > course.price ? `<s>${money(course.mrp)}</s>` : ''}
             ${off ? `· ${off}% off` : ''} · unlocks with an access code, no card payment
           </p>`
    }`;

  // Sticky purchase bar for phones, mirroring the app screens.
  const mobile = $('#mobile-buy');
  if (mobile) {
    document.body.classList.add('has-mobile-buy');
    mobile.innerHTML = `
      <span class="mobile-buy-price">
        ${isFree ? 'Free batch' : money(course.price)}
        ${!isFree && off ? `<small>${off}% off</small>` : ''}
      </span>
      <a class="btn ${isFree ? 'btn-primary' : 'btn-accent'} btn-sm" href="dashboard.html">
        ${isFree ? 'Start free' : 'Enroll Now'}
      </a>`;
  }
}

function renderAside(course) {
  const host = $('#course-aside');
  host.innerHTML = `
    <div class="facts-card">
      <dl style="display:grid;gap:var(--sp-4);margin:0">
        <div class="facts-row">
          <dt>Batch Starts</dt>
          <dd>${course.startsOn ? longDate(course.startsOn) : 'Anytime'}</dd>
        </div>
        <div class="facts-row">
          <dt>Validity</dt>
          <dd>Till exam ${esc(course.exam)}</dd>
        </div>
        <div class="facts-row">
          <dt>Language</dt>
          <dd>${esc(course.language)}</dd>
        </div>
        <div class="facts-row">
          <dt>Applicable For</dt>
          <dd>${esc(course.exam)} ${esc(course.subject)} — all levels</dd>
        </div>
        <div class="facts-row">
          <dt>Included</dt>
          <dd>${course.lessons} lessons · ${course.tests} tests</dd>
        </div>
      </dl>
      <hr>
      <div class="row" style="gap:8px">
        <button class="btn btn-ghost btn-sm" style="flex:1" data-share>${icon('share')} Share</button>
        <button class="btn btn-ghost btn-sm" style="flex:1" data-bookmark>${icon('bookmark')} Save</button>
      </div>
      <div class="purchase-note">${icon('shield-check')} No card payment · access codes only</div>
    </div>

    <div class="card card-pad" style="margin-top:16px;display:grid;gap:12px;background:rgba(91,91,246,0.1);border-color:var(--violet-600)">
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

      <div class="check-list">
        <div class="check-item">${icon('play')} Live &amp; recorded classes</div>
        <div class="check-item">${icon('note')} Study material (PDF)</div>
        <div class="check-item">${icon('file-text')} Mock tests with rank</div>
        <div class="check-item">${icon('message')} Doubt support</div>
        <div class="check-item">${icon('download')} Downloadable lessons</div>
        <div class="check-item">${icon('book')} ${course.withBooks ? 'Hindi books included' : 'Chapter notes included'}</div>
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

/**
 * The Tests tab lists the quizzes the API actually publishes for this batch.
 * Nothing is invented: a batch with no tests says so.
 */
async function renderTests(course) {
  const host = $('#panel-tests');
  if (!host) return;

  const note = `
      <div class="alert alert-info" style="margin-top:6px">
        <svg><use href="#i-info"/></svg>
        <span>Answers are scored on the server. Rank is published only after the test window closes.</span>
      </div>`;

  let rows = [];
  if (course.id) {
    try {
      const { data } = await live(`/quizzes/?course=${encodeURIComponent(course.id)}&page_size=20`, null, { timeout: 2200 });
      rows = (data ? (Array.isArray(data) ? data : data.results || []) : []).map((quiz) => ({
        id: quiz.id,
        name: quiz.title,
        questions: quiz.question_count ?? 0,
        minutes: quiz.duration_minutes ?? 0,
        marks: quiz.marks_per_question
          ? Math.round(Number(quiz.marks_per_question) * (quiz.question_count ?? 0))
          : null,
        locked: quiz.has_access === false
      }));
    } catch {
      rows = [];
    }
  }

  if (!rows.length) {
    host.innerHTML = `
      <div class="stack">
        ${emptyState({
          title: 'No tests published for this batch yet',
          body: 'Chapter tests and full-length mocks appear here as soon as they are released.',
          actionLabel: 'Browse all test series',
          actionHref: 'tests.html',
          iconName: 'file-text'
        })}
        ${note}
      </div>`;
    return;
  }

  host.innerHTML = `
    <div class="stack">
      ${rows
        .map(
          (test) => `
        <div class="card card-pad row-between" style="gap:14px;flex-wrap:wrap">
          <div style="display:flex;gap:12px;align-items:center">
            <span class="test-icon">${icon('target')}</span>
            <div>
              <strong style="display:block;font-size:14px">${esc(test.name)}</strong>
              <small class="tiny muted">
                ${test.questions} questions${test.marks ? ` · ${test.marks} marks` : ''}${test.minutes ? ` · ${test.minutes} minutes` : ''}
              </small>
            </div>
          </div>
          ${
            test.locked
              ? '<span class="badge badge-outline">Enrol to unlock</span>'
              : `<a class="btn btn-ghost btn-sm" href="test-player.html?test=${test.id}">Start test</a>`
          }
        </div>`
        )
        .join('')}
      ${note}
    </div>`;
}

function renderFaculty(course) {
  const host = $('#panel-faculty');
  const rows = course.faculty || [];

  // The API does not store faculty yet, so a live batch says so instead of
  // showing a name, a tenure or a rating nobody supplied.
  if (!rows.length) {
    host.innerHTML = emptyState({
      title: 'Faculty profiles are being added',
      body: `This batch is taught by the ${course.subject} team. Names and profiles appear here once they are published.`,
      actionLabel: 'Ask a doubt in the community',
      actionHref: 'community.html',
      iconName: 'user'
    });
    return;
  }

  host.innerHTML = `
    <div class="faculty-list">
      ${rows
        .map(
          (f) => `
        <div class="faculty-row">
          <span class="avatar avatar-lg">${esc(f.initials || initials(f.name))}</span>
          <div style="flex:1">
            <h4>${esc(f.name)}</h4>
            <p>${esc(f.role || course.subject)}</p>
          </div>
        </div>`
        )
        .join('')}
    </div>`;
}

function renderFaq(course) {
  const host = $('#panel-faq');
  if (!host) return;
  const items = [
    ['How do I unlock a paid batch?', 'Paid batches unlock with a 12-character access code issued by your institute. There is no checkout and no card payment on StudySpace.'],
    ['Are the classes live or recorded?', 'Both. Classes run live to a timetable and the recording appears in the same chapter within a couple of hours, so a missed class never becomes a gap.'],
    ['Is there negative marking in the tests?', 'Each test carries its own marking scheme, shown on the instructions screen before you start. Scores are calculated on the server and cannot be changed by the browser.'],
    ['What is the validity of this batch?', `${course.title} stays available on your account until the ${course.exam} exam date shown in the batch facts.`],
    ['Can I study offline?', 'Yes. Opened lessons, notes and downloads stay readable without a connection. Tests need a connection to submit because they are scored on the server.']
  ];
  host.innerHTML = `
    <div class="accordion" role="list">
      ${items
        .map(
          ([q, a], i) => `
        <div class="acc-item" role="listitem">
          <button class="acc-head" type="button" aria-expanded="${i === 0}" aria-controls="faq-panel-${i}">
            <span class="acc-title">${esc(q)}</span>
            <svg class="acc-chevron"><use href="#i-chevron-down"/></svg>
          </button>
          <div class="acc-panel" id="faq-panel-${i}" ${i === 0 ? '' : 'hidden'}>
            <p class="acc-text">${esc(a)}</p>
          </div>
        </div>`
        )
        .join('')}
    </div>`;
  host.addEventListener('click', (e) => {
    const head = e.target.closest('.acc-head');
    if (!head) return;
    const open = head.getAttribute('aria-expanded') === 'true';
    host.querySelectorAll('.acc-head').forEach((other) => {
      other.setAttribute('aria-expanded', 'false');
      const panel = document.getElementById(other.getAttribute('aria-controls'));
      if (panel) panel.hidden = true;
    });
    if (!open) {
      head.setAttribute('aria-expanded', 'true');
      const panel = document.getElementById(head.getAttribute('aria-controls'));
      if (panel) panel.hidden = false;
    }
  });
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
  const tabs = $$('.tabs .tab');
  if (!tabs.length) return;
  // Panels are whatever the tabs declare via aria-controls, so adding a tab
  // to the markup never leaves an orphan panel behind.
  const panels = tabs.map((tab) => document.getElementById(tab.getAttribute('aria-controls')));

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => activate(tab.id));
    tab.addEventListener('keydown', (e) => {
      const idx = tabs.indexOf(tab);
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        const next = (idx + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        tabs[next].focus();
        activate(tabs[next].id);
      }
    });
  });

  const fromHash = location.hash.replace('#', '');
  const hashTab = tabs.find((tab) => tab.id === `tab-${fromHash}`);
  if (hashTab) activate(hashTab.id);

  function activate(id) {
    tabs.forEach((tab, i) => {
      const selected = tab.id === id;
      tab.setAttribute('aria-selected', String(selected));
      if (panels[i]) panels[i].hidden = !selected;
    });
  }
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
