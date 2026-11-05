/**
 * Live check: boot the real pages against a running API.
 *
 * The front end has no fixture fallback, so this is the check that proves the
 * screens render database rows: every assertion compares the DOM with what
 * `/api/…` actually returned for the same request.
 *
 *   terminal 1 — API      : cd backend && python manage.py runserver 127.0.0.1:8000
 *   terminal 2 — site     : python3 tools/serve.py --port 8080
 *   terminal 3 — this file: cd tools/checks && node live.js
 *
 * Point it elsewhere with `CHECK_ORIGIN=https://staging.example node live.js`.
 */
const { boot, click, wait } = require('./harness');

const ORIGIN = process.env.CHECK_ORIGIN || 'http://127.0.0.1:8080';

const liveFetch = (url, init) => fetch(new URL(url, ORIGIN).toString(), init);

const liveBoot = (page, mods, query = '', seedStorage = null) =>
  boot(page, mods, { query, fetcher: liveFetch, seedStorage });

/**
 * A real account for the sections that act as a learner.
 *
 * The suite cannot use a seeded student: `seed_demo` deliberately creates no
 * signable account, and a lesson list is empty until somebody has joined a
 * batch (free batches need enrolment too). So the check makes its own learner
 * through the public API and enrols it in a free batch — the same two calls a
 * visitor makes. Both endpoints are throttled (10/min), and a suite that
 * registers on every run would trip that, so the token is cached on disk and
 * reused until it is nearly expired. A 429 is waited out once rather than
 * reported as a product failure.
 */
const TOKEN_CACHE = '/tmp/studyspace-check-token.json';

const CHECK_LEARNER = {
  username: 'live-check-learner',
  email: 'live-check@studyspace.example',
  password: 'LiveCheck!2026'
};

function tokenIsFresh(token) {
  try {
    const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString());
    return payload.exp * 1000 - Date.now() > 120000;
  } catch {
    return false;
  }
}

const postJson = (path, body) =>
  fetch(`${ORIGIN}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

async function mintToken() {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    // 201 on the first run, 400 once the learner already exists — either way
    // the next step is the same login.
    const registered = await postJson('/api/auth/register/', {
      ...CHECK_LEARNER,
      password_confirm: CHECK_LEARNER.password
    });
    if (registered.status === 429) {
      console.log('  … registration throttled, waiting for the window to reopen');
      await wait(61000);
      continue;
    }
    const res = await postJson('/api/token/', {
      username_or_email: CHECK_LEARNER.username,
      password: CHECK_LEARNER.password
    });
    if (res.ok) return res.json();
    if (res.status !== 429) return null;
    console.log('  … login throttled, waiting for the window to reopen');
    await wait(61000);
  }
  return null;
}

/**
 * Join a free batch, the way a student does.
 *
 * Without this every signed-in screen is empty: the enrolment gate applies to
 * free batches too, so the check would "prove" an empty catalogue. Idempotent —
 * an account that already belongs to a batch makes no request.
 */
async function ensureEnrolment(auth) {
  const mine = await (await fetch(`${ORIGIN}/api/courses/?mine=1&page_size=1`, { headers: auth })).json();
  if ((mine?.count || 0) > 0) return true;
  const free = await (await fetch(`${ORIGIN}/api/courses/?pricing_mode=free&page_size=5`, { headers: auth })).json();
  const course = (free?.results || [])[0];
  if (!course) return false;
  const res = await fetch(`${ORIGIN}/api/courses/${course.id}/enroll/`, {
    method: 'POST',
    headers: { ...auth, 'Content-Type': 'application/json' },
    body: '{}'
  });
  return res.ok;
}

async function signIn(depth = 0) {
  let token = null;
  try {
    const cached = JSON.parse(require('fs').readFileSync(TOKEN_CACHE, 'utf8'));
    if (tokenIsFresh(cached.access)) token = cached;
  } catch {
    /* no usable cache */
  }
  if (!token) {
    token = await mintToken();
    if (!token) return null;
    try {
      require('fs').writeFileSync(TOKEN_CACHE, JSON.stringify(token));
    } catch {
      /* a cache miss just means the next run logs in again */
    }
  }
  const auth = { Authorization: `Bearer ${token.access}` };
  const meRes = await fetch(`${ORIGIN}/api/auth/me/`, { headers: auth });
  if (!meRes.ok) {
    // A cached token from before the database was reseeded names a user that
    // no longer exists. Drop it and mint a fresh one instead of failing the
    // whole signed-in half of the suite.
    if (depth > 0) return null;
    try {
      require('fs').unlinkSync(TOKEN_CACHE);
    } catch {
      /* nothing to drop */
    }
    return signIn(depth + 1);
  }
  const me = await meRes.json();
  await ensureEnrolment(auth);
  return {
    storage: {
      'studyspace.access': token.access,
      'studyspace.refresh': token.refresh,
      'studyspace.user': JSON.stringify({ username: me.username, email: me.email })
    },
    auth: { Authorization: `Bearer ${token.access}` }
  };
}

let pass = 0;
let fail = 0;
const check = (name, ok, detail = '') => {
  if (ok) pass += 1;
  else fail += 1;
  console.log(`${ok ? '  ✓' : '  ✗'} ${name}${detail ? `  — ${detail}` : ''}`);
};

const api = async (path, auth) => {
  const res = await fetch(`${ORIGIN}${path}`, auth ? { headers: auth } : undefined);
  return res.ok ? res.json() : null;
};

const rowsOf = (payload) => (Array.isArray(payload) ? payload : payload?.results || []);
const text = (node) => (node?.textContent || '').replace(/\s+/g, ' ').trim();

/* Copy that used to be fixture data. None of it may come back. */
const FIXTURES = [
  'Aarav Gupta',
  'student@studyspace.example',
  '10,482 learners',
  'All-India rank',
  'Bookmarked',
  'Today’s Classes',
  'Organic Chemistry',
  'sample data'
];

(async () => {
  console.log('\nAPI');
  // Signed in from the start: the enrolment gate means a guest sees no
  // lessons at all, and half the suite renders the learner's own screens.
  const session = await signIn();
  const auth = session?.auth;
  const courses = await api('/api/courses/?page_size=3');
  const quizzes = await api('/api/quizzes/?page_size=60');
  const lessons = await api('/api/lessons/?page_size=60', auth);
  check('catalogue answers', Boolean(courses), String(courses?.count));
  check('seed rows present', (courses?.count || 0) >= 5, `count=${courses?.count}`);
  check('quizzes answer', Boolean(quizzes), `count=${quizzes?.count}`);
  check('lessons answer', Boolean(lessons), `count=${lessons?.count}`);
  check(
    'a joined batch has classes to check',
    (lessons?.count || 0) > 0,
    session ? `count=${lessons?.count}` : 'no account could sign in'
  );
  if (!courses || !quizzes) {
    console.log('\nThe API did not answer — start the server first.');
    process.exit(1);
  }

  console.log('\nindex.html');
  {
    // The timetable belongs to the batches this learner joined, so the page is
    // booted with the session — a guest genuinely has none.
    const { doc, errors } = await liveBoot('index.html', ['core', 'content', 'ui', 'home'], '', session.storage);
    const batchCards = [...doc.querySelectorAll('#trending-grid .batch-card')];
    const apiTitles = rowsOf(courses).map((c) => c.title);
    check('batch rail renders API rows', batchCards.length > 0, String(batchCards.length));
    check(
      'batch titles match the API',
      batchCards.every((card) => apiTitles.some((title) => text(card).includes(title))),
      apiTitles[0]
    );
    // P5: the rail is the server's timetable, not a list of today's uploads.
    const schedule = await api('/api/schedule/?days=7', auth);
    const scheduled = (schedule?.groups || []).flatMap((group) => group.classes);
    const rail = [...doc.querySelectorAll('#schedule-list .class-row')];
    check('timetable renders server rows', rail.length > 0, `${rail.length} rows`);
    check(
      'timetable titles are the scheduled classes',
      rail.every((row) => scheduled.some((entry) => text(row).includes(entry.title))),
      text(rail[0]).slice(0, 70)
    );
    // The clock is printed on the batch's zone, the same calendar the day
    // headings were cut on. This runner is UTC, so a page printing device time
    // would show 13:30 for a 19:00 IST class — the mismatch this check exists
    // to catch.
    const zone = schedule?.timezone || 'Asia/Kolkata';
    const clockOf = (iso) =>
      new Date(iso)
        .toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: zone })
        .replace(/\s/g, ' ')
        .toLowerCase();
    const firstScheduled = scheduled.find((entry) => text(rail[0])?.includes(entry.title));
    check(
      'a row shows the class time the server sent',
      rail.every((row) => /\d{1,2}:\d{2}/.test(text(row.querySelector('.class-time')))),
      text(rail[0]?.querySelector('.class-time'))
    );
    check(
      'the row prints the batch clock, not the device clock',
      Boolean(firstScheduled) &&
        text(rail[0].querySelector('.class-time')).toLowerCase() === clockOf(firstScheduled.starts_at).replace(/\u202f/g, ' '),
      `${text(rail[0]?.querySelector('.class-time'))} vs ${firstScheduled ? clockOf(firstScheduled.starts_at) : '?'} (${zone})`
    );
    check(
      'no timetable row claims to be live',
      doc.querySelectorAll('#schedule-list .badge-live').length === 0,
      `${doc.querySelectorAll('#schedule-list .badge-live').length} badged`
    );
    check('the API reports no live count', !schedule || !('live' in (schedule.counts || {})), JSON.stringify(schedule?.counts || {}));
    const testCards = [...doc.querySelectorAll('#home-tests .test-card')];
    check('test rail renders API papers', testCards.length > 0, String(testCards.length));
    const main = text(doc.querySelector('main'));
    const leaked = FIXTURES.filter((phrase) => main.includes(phrase));
    check('no fixture copy on the home page', leaked.length === 0, leaked.join(', '));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\ncourses.html');
  {
    const { doc, errors } = await liveBoot('courses.html', ['core', 'content', 'ui', 'courses']);
    const cards = [...doc.querySelectorAll('#course-grid .batch-card')];
    check('grid renders server rows', cards.length > 0, String(cards.length));
    check('grid is capped at one page', cards.length <= 9, String(cards.length));
    const search = doc.querySelector('#course-search');
    check('search box present', Boolean(search));
    const sort = doc.querySelector('#course-sort');
    check('sort select offers API orderings', /position|title|price/.test(sort?.innerHTML || ''));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\ncourse.html');
  {
    const slug = rowsOf(courses)[0].slug;
    const detail = await api(`/api/courses/${rowsOf(courses)[0].id}/`);
    const { doc, errors } = await liveBoot('course.html', ['core', 'content', 'ui', 'course'], `?slug=${slug}`);
    check('headline is the API title', text(doc.querySelector('#course-headline')).includes(detail.title), text(doc.querySelector('#course-headline')).slice(0, 60));

    // The subjects: one card per subject the API's chapters file under, and
    // the fallback is the batch's own subject — the page never invents one.
    const folders = detail.folders || [];
    const groups = new Map();
    folders.forEach((folder) => {
      const name = (folder.subject || '').trim() || detail.subject || 'General';
      if (!groups.has(name)) groups.set(name, []);
      groups.get(name).push(folder);
    });

    const cards = [...doc.querySelectorAll('#subject-grid .subject-card')];
    check('one card per server subject', cards.length === groups.size, `${cards.length}/${groups.size}`);
    check(
      'the cards are the subjects the chapters filed under',
      cards.every((card) => groups.has(card.dataset.subject)) &&
        [...groups.keys()].every((name) => cards.some((card) => card.dataset.subject === name)),
      cards.map((card) => card.dataset.subject).join('|')
    );
    const subjectUrl = (name) =>
      `subject.html?${new URLSearchParams({ course: slug, subject: name }).toString()}`;
    check(
      'a card links to its own subject page',
      cards.every((card) => card.getAttribute('href') === subjectUrl(card.dataset.subject)),
      cards[0]?.getAttribute('href')
    );

    const expectedCounts = [...groups.entries()].map(([name, chapters]) => {
      const classes = chapters.reduce((n, f) => n + (f.lessons || []).length, 0);
      const notes = chapters.reduce((n, f) => n + (f.pdf_resources || []).length, 0);
      const parts = [
        `${chapters.length} ${chapters.length === 1 ? 'chapter' : 'chapters'}`,
        `${classes} ${classes === 1 ? 'class' : 'classes'}`
      ];
      if (notes) parts.push(`${notes} ${notes === 1 ? 'note' : 'notes'}`);
      return [name, parts.join(' · ')];
    });
    check(
      'every card counts what the API says is inside',
      expectedCounts.every(([name, meta]) => {
        const card = cards.find((row) => row.dataset.subject === name);
        return card && text(card.querySelector('.subject-meta')) === meta;
      }),
      expectedCounts.map(([name, meta]) => `${name}: ${meta}`).join(' / ')
    );

    // The strip above the tabs shows at most six classes; when the window
    // holds more, it says how many it is holding back rather than letting six
    // rows look like the whole timetable.
    const batchSchedule = await api(`/api/schedule/?course=${slug}&days=14`);
    const aheadCount = (batchSchedule?.groups || [])
      .flatMap((group) => group.classes)
      .filter((entry) => entry.status !== 'ended').length;
    const stripRows = doc.querySelectorAll('#class-timetable .day-schedule .class-row').length;
    const stripNote = text(doc.querySelector('#class-timetable .batch-schedule-head .subtle'));
    const hiddenAhead = aheadCount - stripRows;
    check(
      'the strip says when it is holding classes back',
      stripRows === Math.min(aheadCount, 6) &&
        (hiddenAhead > 0 ? stripNote === `${hiddenAhead} more below` : stripNote === 'Next 14 days'),
      `${stripRows}/${aheadCount} rows / "${stripNote}"`
    );

    // No live anywhere: these are recordings.
    check('the batch page claims nothing is live', doc.querySelectorAll('.badge-live').length === 0, String(doc.querySelectorAll('.badge-live').length));
    check('nothing on the page offers to join a class', !/join (the )?class/i.test(text(doc.querySelector('#panel-subjects'))));
    check('aside shows the real price', /Free|₹/.test(text(doc.querySelector('#course-aside'))), text(doc.querySelector('#course-aside')).slice(0, 50));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\nlearn.html (the classroom)');
  {
    // A batch the account actually holds: the classroom is gated on access, so
    // checking it on a batch the learner has not joined would only prove the
    // gate. `ensureEnrolment` has already joined a free batch by now.
    const owned = session ? await api('/api/courses/?mine=1&page_size=1', session.auth) : null;
    const row = rowsOf(owned)[0];
    if (!row) {
      check('a joined batch is available for the classroom check', false, 'no batch on the account');
    } else {
      const detail = await api(`/api/courses/${row.id}/`, session?.auth);
      const folders = detail.folders || [];
      const groups = new Map();
      folders.forEach((folder) => {
        const name = (folder.subject || '').trim() || detail.subject || 'General';
        if (!groups.has(name)) groups.set(name, []);
        groups.get(name).push(folder);
      });
      const classes = folders.reduce((n, folder) => n + (folder.lessons || []).length, 0);
      const notes = folders.reduce((n, folder) => n + (folder.pdf_resources || []).length, 0);

      const { doc, window, errors } = await liveBoot(
        'learn.html',
        ['core', 'content', 'ui', 'learn'],
        `?course=${row.slug}`,
        session?.storage
      );
      await wait(600);

      check('the headline is the API title', text(doc.querySelector('#learn-title')) === detail.title, text(doc.querySelector('#learn-title')));
      check(
        'the line under it counts the server folders',
        text(doc.querySelector('#learn-sub')) ===
          `${folders.length} ${folders.length === 1 ? 'chapter' : 'chapters'} · ${classes} ${classes === 1 ? 'class' : 'classes'} · ${notes} ${notes === 1 ? 'note' : 'notes'}`,
        text(doc.querySelector('#learn-sub'))
      );
      check(
        'the batch page is still one click away',
        doc.querySelector('#overview-link').getAttribute('href') === `course.html?slug=${row.slug}`
      );

      const tabs = [...doc.querySelectorAll('#learn-tabs .tab')];
      check(
        'four tabs: Subjects, Tests, Announcements, Community',
        tabs.map((tab) => tab.dataset.tab).join('|') === 'subjects|tests|announcements|community',
        tabs.map((tab) => tab.dataset.tab).join('|')
      );
      check(
        'the header names the faculty the batch lists',
        (detail.faculty || []).length === 0 ||
          (detail.faculty || []).every((person) => text(doc.querySelector('#learn-faculty')).includes(person.name)),
        text(doc.querySelector('#learn-faculty')).slice(0, 60)
      );

      const cards = [...doc.querySelectorAll('#subject-grid .subject-card')];
      check('one card per server subject', cards.length === groups.size, `${cards.length}/${groups.size}`);
      const expected = [...groups.entries()].map(([name, chapters]) => {
        const held = chapters.reduce((n, folder) => n + (folder.lessons || []).length, 0);
        const kept = chapters.reduce((n, folder) => n + (folder.pdf_resources || []).length, 0);
        const parts = [
          `${chapters.length} ${chapters.length === 1 ? 'chapter' : 'chapters'}`,
          `${held} ${held === 1 ? 'class' : 'classes'}`
        ];
        if (kept) parts.push(`${kept} ${kept === 1 ? 'note' : 'notes'}`);
        return [name, parts.join(' · ')];
      });
      check(
        'every card counts what the API says is inside',
        expected.every(([name, meta]) => {
          const card = cards.find((item) => item.dataset.subject === name);
          return card && text(card.querySelector('.subject-meta')) === meta;
        }),
        expected.map(([name, meta]) => `${name}: ${meta}`).join(' / ')
      );
      check(
        'a card continues into that subject of this batch',
        cards.every(
          (card) =>
            card.getAttribute('href') ===
            `subject.html?${new URLSearchParams({ course: row.slug, subject: card.dataset.subject }).toString()}`
        ),
        cards[0]?.getAttribute('href')
      );

      // The papers and the feed are the batch's own rows, counted from the API.
      const papers = rowsOf(await api(`/api/quizzes/?course=${row.id}&page_size=50`));
      const posts = rowsOf(await api(`/api/community/?course=${row.id}&page_size=10`));
      doc.querySelector('#tab-tests').click();
      await wait(400);
      const paperCards = doc.querySelectorAll('#panel-tests .test-card').length;
      check(
        'the Tests tab holds exactly the batch papers',
        paperCards === papers.length &&
          (papers.length > 0 || /No papers in this batch yet/.test(text(doc.querySelector('#panel-tests')))),
        `${paperCards}/${papers.length}`
      );
      doc.querySelector('#tab-announcements').click();
      await wait(400);
      const pinned = posts.filter((post) => post.pinned);
      const noticeCards = doc.querySelectorAll('#panel-announcements .post-card').length;
      check(
        'the Announcements tab holds exactly the pinned notices',
        noticeCards === pinned.length,
        `${noticeCards}/${pinned.length}`
      );
      doc.querySelector('#tab-community').click();
      await wait(400);
      const feedCards = doc.querySelectorAll('#panel-community .post-card').length;
      check(
        'the Community tab holds exactly the batch feed',
        feedCards === posts.length &&
          (posts.length > 0 || /Nothing posted in this batch yet/.test(text(doc.querySelector('#panel-community')))),
        `${feedCards}/${posts.length}`
      );

      // Today's classes, above the tabs, from the same schedule endpoint.
      const schedule = await api(`/api/schedule/?course=${row.slug}&days=14`);
      const ahead = (schedule?.groups || [])
        .flatMap((group) => group.classes)
        .filter((entry) => entry.status !== 'ended');
      const stripRows = doc.querySelectorAll('#class-timetable .day-schedule .class-row').length;
      const stripNote = text(doc.querySelector('#class-timetable .batch-schedule-head .subtle'));
      const hiddenAhead = ahead.length - stripRows;
      check(
        'the strip shows at most six classes and says what it holds back',
        stripRows === Math.min(ahead.length, 6) &&
          (hiddenAhead > 0 ? stripNote === `${hiddenAhead} more below` : /Next 14 days|Last 14 days/.test(stripNote)),
        `${stripRows}/${ahead.length} rows / "${stripNote}"`
      );

      // `.badge-live` also paints a *Pinned* notice, so the check is about
      // claims, not the class: the batch header and the syllabus must never
      // say a class is on air.
      check(
        'nothing in the batch header or the syllabus claims to be live',
        doc.querySelectorAll('.learn-hero .badge-live, #panel-subjects .badge-live').length === 0 &&
          !/\blive\b/i.test(text(doc.querySelector('.learn-hero'))) &&
          !/\blive\b/i.test(text(doc.querySelector('#panel-subjects')))
      );
      check('no console errors', errors.length === 0, errors[0]);
    }
  }

  console.log('\nsubject.html');
  {
    const row = rowsOf(courses)[0];
    const detail = await api(`/api/courses/${row.id}/`);
    const folders = detail.folders || [];
    const name = (folders[0]?.subject || '').trim() || detail.subject || 'General';
    const mine = folders.filter((folder) => ((folder.subject || '').trim() || detail.subject || 'General') === name);

    const { doc, errors } = await liveBoot('subject.html', ['core', 'content', 'ui', 'subject'], `?course=${row.slug}&subject=${encodeURIComponent(name)}`);
    check('the headline is the subject the batch files under', text(doc.querySelector('#subject-headline')) === name, text(doc.querySelector('#subject-headline')));
    check(
      'the breadcrumb links back to the batch',
      doc.querySelector('#crumb-batch').getAttribute('href') === `course.html?slug=${row.slug}`
    );

    // Only this subject's chapters: the same payload, cut by subject.
    const chapters = [...doc.querySelectorAll('#panel-lectures .tree-chapter')];
    const hasClasses = mine.some((folder) => (folder.lessons || []).length > 0);
    check(
      'every chapter of this subject is here, and no other',
      chapters.length === (hasClasses ? mine.length : 0) &&
        chapters.every((chapter) => mine.some((folder) => text(chapter.querySelector('.tree-chapter-name')) === folder.title)),
      `${chapters.length}/${mine.length}: ${chapters.map((chapter) => text(chapter.querySelector('.tree-chapter-name'))).join(' | ')}`
    );

    const lessons = mine.flatMap((folder) => folder.lessons || []);
    const cards = [...doc.querySelectorAll('#panel-lectures .lecture-card')];
    check('every class in the subject is a card', cards.length === lessons.length, `${cards.length}/${lessons.length}`);
    check(
      'no class is repeated',
      new Set(cards.map((card) => card.dataset.lesson)).size === lessons.length
    );
    check(
      'a card opens the player for that class',
      cards.every((card) =>
        card.getAttribute('href')
          ? card.getAttribute('href') === `player.html?lesson=${card.dataset.lesson}`
          : true
      )
    );
    check(
      'a locked class is badged rather than linked',
      cards.filter((card) => card.tagName !== 'A').every((card) => /Locked/.test(text(card))) &&
        cards.filter((card) => card.classList.contains('is-locked')).length ===
          cards.filter((card) => card.tagName !== 'A').length
    );

    // Notes, from the same chapters.
    const notes = mine.flatMap((folder) => folder.pdf_resources || []);
    doc.querySelector('#tab-notes').click();
    await wait(30);
    const rows = [...doc.querySelectorAll('#panel-notes .tree-file')];
    check('every note in the subject is listed', rows.length === notes.length, `${rows.length}/${notes.length}`);
    check(
      'a note without a file is badged, not linked',
      rows.every((note) => (note.getAttribute('href') ? /pdf\.html\?pdf=\d+/.test(note.getAttribute('href')) : /Locked/.test(text(note))))
    );

    // The counts on the tabs are the payload's, not a guess.
    const lessonsExpected = lessons.length;
    const notesExpected = notes.length;
    const tabCount = (key) => {
      const node = doc.querySelector(`.tab-count[data-count="${key}"]`);
      return node && !node.hidden ? Number(text(node)) : 0;
    };
    check('the Lectures badge matches the payload', tabCount('lectures') === lessonsExpected, `${tabCount('lectures')}/${lessonsExpected}`);
    check('the Notes badge matches the payload', tabCount('notes') === notesExpected, `${tabCount('notes')}/${notesExpected}`);

    check('nothing on the subject page claims to be live', doc.querySelectorAll('.badge-live').length === 0);
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\ntests.html');
  {
    const { doc, errors } = await liveBoot('tests.html', ['core', 'content', 'ui', 'tests']);
    const cards = [...doc.querySelectorAll('#test-grid .test-card')];
    check('paper cards render', cards.length > 0, String(cards.length));
    check('card count matches the API', cards.length === rowsOf(quizzes).length, `${cards.length}/${rowsOf(quizzes).length}`);
    check('no rank claim', !text(doc.querySelector('main')).includes('All-India rank'));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\ntest-player.html (guest attempt, end to end)');
  {
    const quiz = rowsOf(quizzes)[0];
    const { doc, errors, window } = await liveBoot(
      'test-player.html',
      ['core', 'content', 'ui', 'test-player'],
      `?test=${quiz.id}`
    );

    check('intro title is the server paper', text(doc.querySelector('#intro-title')) === quiz.title, text(doc.querySelector('#intro-title')));
    check('question count is the server count', text(doc.querySelector('#intro-count')) === String(quiz.question_count), text(doc.querySelector('#intro-count')));
    check('marking comes from the paper', text(doc.querySelector('#intro-marking')).includes('+4'), text(doc.querySelector('#intro-marking')));
    check('no sign-in gate on the start button', !doc.querySelector('#start-btn').disabled || !doc.querySelector('#agree').checked);

    doc.querySelector('#agree').checked = true;
    doc.querySelector('#agree').dispatchEvent(new window.Event('change', { bubbles: true }));
    check('start enabled without an account', !doc.querySelector('#start-btn').disabled);
    click(window, doc.querySelector('#start-btn'));
    await wait(1200);

    check('exam view opened', !doc.querySelector('#exam-view').hidden);
    const options = [...doc.querySelectorAll('#exam-view .qoption')];
    check('four options from the server', options.length === 4, String(options.length));
    check('marks on the question', text(doc.querySelector('#q-marks')).startsWith('+4'), text(doc.querySelector('#q-marks')));
    const token = window.localStorage.getItem('studyspace.attempt-token');
    check('attempt token stored for a guest', Boolean(token));

    // Answer the first question, then submit — the whole point of removing the
    // sign-in gate is that this path works with no account at all.
    const option = doc.querySelectorAll('#exam-view .qoption input')[0];
    option.checked = true;
    option.dispatchEvent(new window.Event('change', { bubbles: true }));
    await wait(900);

    click(window, doc.querySelector('#submit-btn'));
    await wait(200);
    click(window, doc.querySelector('#confirm-submit'));
    await wait(1500);

    check('guest submit reaches the result view', !doc.querySelector('#result-view').hidden, doc.querySelector('#result-sub')?.textContent?.slice(0, 70));
    check('score came back from the server', /\d/.test(doc.querySelector('#result-hero').textContent || ''));
    check('guest answers are scored, not self-marked', !/scored on this device/i.test(doc.body.textContent));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\ncommunity.html');
  {
    const feed = await api('/api/community/');
    const { doc, errors } = await liveBoot('community.html', ['core', 'content', 'ui', 'community']);
    const host = doc.querySelector('#announcement-list');
    if (rowsOf(feed).length) {
      check('announcements render', host.querySelectorAll('.post-card').length === rowsOf(feed).length);
    } else {
      check('empty feed shows an honest empty state', Boolean(host.querySelector('.empty-state')));
    }
    check('no reply box without a write endpoint', !doc.querySelector('[data-compose]'));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\nprofile.html (guest)');
  {
    const { doc, errors } = await liveBoot('profile.html', ['core', 'content', 'ui', 'profile']);
    check('guest is told to sign in', text(doc.querySelector('#profile-note')).includes('Sign in'));
    check('no borrowed name', text(doc.querySelector('#profile-name')) === 'Guest', text(doc.querySelector('#profile-name')));
    check('stats stay blank, not invented', [...doc.querySelectorAll('.profile-stat strong')].every((n) => text(n) === '—'));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\ndashboard.html (guest)');
  {
    const { doc, errors } = await liveBoot('dashboard.html', ['core', 'content', 'ui', 'dashboard']);
    const figures = [...doc.querySelectorAll('.dash-figure strong')].map(text);
    check('figures are blank for a guest', figures.every((value) => value === '—'), figures.join(','));
    check('continue panel asks for sign-in', Boolean(doc.querySelector('#continue-list .empty-state')));
    check('notes panel asks for sign-in', Boolean(doc.querySelector('#notes-list .empty-state')));
    const upcoming = doc.querySelector('#upcoming-list');
    check('upcoming panel answers', Boolean(upcoming.querySelector('.upcoming-item') || upcoming.querySelector('.empty-state')));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\nplayer.html');
  {
    const lesson = rowsOf(lessons)[0];
    const { doc, errors } = await liveBoot(
      'player.html',
      ['core', 'content', 'ui', 'player'],
      `?lesson=${lesson.id}`,
      session.storage
    );
    check('lesson title from the API', text(doc.querySelector('#player-title')) === lesson.title, text(doc.querySelector('#player-title')));
    check('no invented timestamp', !text(doc.querySelector('#player-sub')).includes('/ 1:00:15'));
    // Three honest states: an embed page, a media file, or nothing.
    const expectsEmbed = Boolean(lesson.video_url) && /embed\.vcdn\.me|player\.vimeo\.com/.test(lesson.video_url);
    if (!lesson.video_url) {
      check('a lesson without a recording says so', !doc.querySelector('#stage-empty').hidden);
    } else if (expectsEmbed) {
      const iframe = doc.querySelector('#player-embed iframe');
      check('an embed URL is shown as an iframe', Boolean(iframe) && !doc.querySelector('#player-embed').hidden);
      check('the iframe src is the URL the API served', iframe?.getAttribute('src') === lesson.video_url, iframe?.getAttribute('src'));
    } else {
      check('a media URL uses the video element', !doc.querySelector('#player-video').hidden);
    }
    check('section list rendered', doc.querySelectorAll('#chapter-list .lesson-item').length > 0);
    check('no console errors', errors.length === 0, errors[0]);

    // The same page as a guest: the class is not theirs, and the page says so
    // instead of rendering a stage with nothing behind it.
    const guest = await liveBoot('player.html', ['core', 'content', 'ui', 'player'], `?lesson=${lesson.id}`);
    check(
      'a guest is told the class is not theirs',
      /Lesson not found|unavailable/i.test(text(guest.doc.querySelector('#player-title'))),
      text(guest.doc.querySelector('#player-title'))
    );
    check('the guest player has no stage to pretend with', !guest.doc.querySelector('#player-video:not([hidden])'));
    check('no console errors for a guest', guest.errors.length === 0, guest.errors[0]);
  }

  console.log('\nbatch page lists its faculty (live rows)');
  {
    const list = await api('/api/courses/?page_size=6');
    const course = rowsOf(list).find((row) => row.slug === 'demo-jee-main-2027') || rowsOf(list)[0];
    const detail = await api(`/api/courses/${course.id}/`);
    const { doc, errors } = await liveBoot('course.html', ['core', 'content', 'ui', 'course'], `?slug=${course.slug}`);

    if ((detail.faculty || []).length) {
      const cards = doc.querySelectorAll('#panel-teachers .faculty-card');
      check('every seeded teacher is on the page', cards.length === detail.faculty.length, `${cards.length}/${detail.faculty.length}`);
      check('the page names the same people', text(doc.querySelector('#panel-teachers')).includes(detail.faculty[0].name));
      check('the Teachers tab counts them', text(doc.querySelector('.tab-count[data-count="teachers"]')) === String(detail.faculty.length), text(doc.querySelector('.tab-count[data-count="teachers"]')));
    } else {
      check('a batch without faculty says so', Boolean(doc.querySelector('#panel-teachers .empty-state')));
    }
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\nbatch page: the “Get code” button on a paid batch');
  {
    const list = await api('/api/courses/?page_size=60');
    const paid = rowsOf(list).find((row) => row.pricing_mode === 'paid' && row.telegram_dm);
    const { doc, errors } = await liveBoot(
      'course.html',
      ['core', 'content', 'ui', 'course'],
      paid ? `?slug=${paid.slug}` : '?slug=missing',
      session.storage
    );
    await wait(400);
    if (!paid) {
      check('a paid batch with a Telegram handle exists to check', false, 'none in the catalogue');
    } else {
      const button = doc.querySelector('#purchase-slot [data-get-code]');
      check('the API hands the browser a DM link', /^https:\/\/t\.me\//.test(paid.telegram_dm), paid.telegram_dm.slice(0, 60));
      check('the page renders “Get code”', Boolean(button), button?.textContent?.trim());
      check('the button uses the API link', button?.getAttribute('href') === paid.telegram_dm);
      check('the draft names the batch', decodeURIComponent(button?.getAttribute('href') || '').replace(/\+/g, ' ').includes(paid.title));
    }
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\nlearning loop: open a class, write a note, see it on the dashboard');
  {
    if (!session) {
      check('a signed-in account is available for the learning-loop check', false, 'token refused');
    } else {
      const owned = await api('/api/lessons/?page_size=1', session.auth);
      const lesson = rowsOf(owned)[0];

      const { doc, window, errors } = await liveBoot(
        'player.html',
        ['core', 'content', 'ui', 'player'],
        `?lesson=${lesson.id}`,
        session.storage
      );
      await wait(700);

      const complete = doc.querySelector('#mark-complete');
      check('the player offers completion to a signed-in learner', Boolean(complete) && !complete.hidden);

      click(window, complete);
      await wait(700);

      const saved = await (
        await fetch(`${ORIGIN}/api/progress/?lesson=${lesson.id}`, { headers: session.auth })
      ).json();
      check(
        'the server now holds a completed progress row',
        rowsOf(saved).some((row) => row.completed),
        JSON.stringify(rowsOf(saved)[0] || {})
      );

      doc.querySelector('#lesson-note-body').value = 'Live check note.';
      doc.querySelector('#lesson-note-form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
      await wait(800);

      const notes = await (
        await fetch(`${ORIGIN}/api/notes/?lesson=${lesson.id}`, { headers: session.auth })
      ).json();
      check('the note reached the database', rowsOf(notes).some((row) => row.body === 'Live check note.'));
      check('the note is rendered under the lesson', /Live check note\./.test(text(doc.querySelector('#lesson-note-list'))));

      const { doc: dash, errors: dashErrors } = await liveBoot(
        'dashboard.html',
        ['core', 'content', 'ui', 'dashboard'],
        '',
        session.storage
      );
      await wait(600);
      check(
        'the dashboard now offers the lesson under "Continue learning"',
        Boolean(dash.querySelector('#continue-list .continue-card')),
        text(dash.querySelector('#continue-list')).slice(0, 60)
      );
      check('"Lessons done" is no longer zero', text(dash.querySelectorAll('.dash-figure strong')[1]) !== '0', text(dash.querySelectorAll('.dash-figure strong')[1]));

      check('no console errors while writing', errors.length === 0, errors[0]);
      check('no console errors on the dashboard', dashErrors.length === 0, dashErrors[0]);
    }
  }

  console.log('\nactivity inbox (live rows)');
  {
    const inbox = await api('/api/notifications/');
    const { doc, window } = await liveBoot('dashboard.html', ['core', 'content', 'ui', 'dashboard']);
    await wait(400);
    click(window, doc.querySelector('#notify-btn'));
    await wait(500);
    const items = doc.querySelectorAll('#notify-panel .notify-item');
    if (inbox.count) {
      check('the panel lists the API items', items.length === inbox.count, `${items.length}/${inbox.count}`);
      check('the first item is the API title', text(items[0]).includes(inbox.results[0].title));
    } else {
      check('an empty inbox says so', Boolean(doc.querySelector('#notify-panel .notify-empty')));
    }
  }

  /**
   * Parity: every path a screen asks for must exist on this API.
   *
   * The pages are booted with a recording fetcher, so nothing here is a
   * hand-written list of endpoints — it is whatever the modules actually
   * request. Each recorded path is then replayed; 404 is the one answer that
   * means "this screen is calling something the backend does not publish".
   * 401/403/405 all prove the route exists.
   */
  console.log('\ncontract (paths the screens request)');
  {
    // Ids move when the demo is reseeded, so the player is pointed at a lesson
    // that exists right now rather than at last week's id.
    const liveLessons = rowsOf(await api('/api/lessons/?page_size=60', auth));
    const lessonId = liveLessons[0]?.id;
    const PAGES = [
      ['index.html', ['core', 'content', 'ui', 'home'], '', false],
      ['courses.html', ['core', 'content', 'ui', 'courses'], '', false],
      ['course.html', ['core', 'content', 'ui', 'course'], '?slug=jee-main-2027', false],
      ['learn.html', ['core', 'content', 'ui', 'learn'], '?course=jee-main-2027', true],
      ['tests.html', ['core', 'content', 'ui', 'tests'], '', false],
      ['community.html', ['core', 'content', 'ui', 'community'], '', false],
      ['profile.html', ['core', 'content', 'ui', 'profile'], '', true],
      ['dashboard.html', ['core', 'content', 'ui', 'dashboard'], '', true],
      ['player.html', ['core', 'content', 'ui', 'player'], `?lesson=${lessonId}`, true],
      ['legal.html', ['core', 'content', 'ui', 'legal'], '', false]
    ];
    const everyPath = new Set();
    for (const [page, mods, query, asAccount] of PAGES) {
      const asked = [];
      const recorder = (url, init) => {
        try {
          const abs = new URL(url, ORIGIN);
          asked.push(abs.pathname + abs.search);
        } catch {
          /* a request the browser would reject anyway */
        }
        return liveFetch(url, init);
      };
      await boot(page, mods, { query, fetcher: recorder, seedStorage: asAccount ? session?.storage : null });
      await wait(500);
      const missing = [];
      for (const path of new Set(asked)) {
        everyPath.add(path);
        const res = await fetch(`${ORIGIN}${path}`, { method: 'GET', headers: session?.auth || {} });
        if (res.status === 404) missing.push(`${path} → 404`);
      }
      check(
        `${page} only calls published endpoints`,
        missing.length === 0 && asked.length > 0,
        missing.length ? missing.join(', ') : `${new Set(asked).size} paths`
      );
    }
    if (session) {
      check('the screens cover the API broadly', everyPath.size >= 20, `${everyPath.size} distinct paths`);
    } else {
      // Without the demo account the signed-in half of the app never boots, so
      // half the paths are never requested. Say so rather than pass quietly.
      console.log(
        '  … no session: signed-in paths unchecked. Create the demo student (see README) to cover them.'
      );
    }
  }

  console.log(`\n${pass}/${pass + fail} live checks passed`);
  process.exit(fail ? 1 : 0);
})();
