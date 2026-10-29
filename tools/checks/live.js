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
 * A real token so a section can act as an account.
 *
 * The login endpoint is deliberately throttled (10/min per identifier), and a
 * check suite that logs in on every run trips it. The token is cached on disk
 * and reused until it is nearly expired — which is also what a real session
 * does. A 429 is waited out once rather than reported as a product failure.
 */
const TOKEN_CACHE = '/tmp/studyspace-check-token.json';

function tokenIsFresh(token) {
  try {
    const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString());
    return payload.exp * 1000 - Date.now() > 120000;
  } catch {
    return false;
  }
}

async function mintToken() {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const res = await fetch(`${ORIGIN}/api/token/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username_or_email: 'aarav', password: 'StudySpace!2026' })
    });
    if (res.ok) return res.json();
    if (res.status !== 429) return null;
    console.log('  … login throttled, waiting for the window to reopen');
    await wait(61000);
  }
  return null;
}

async function signIn() {
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
  const me = await (
    await fetch(`${ORIGIN}/api/auth/me/`, {
      headers: { Authorization: `Bearer ${token.access}` }
    })
  ).json();
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

const api = async (path) => {
  const res = await fetch(`${ORIGIN}${path}`);
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
  const courses = await api('/api/courses/?page_size=3');
  const quizzes = await api('/api/quizzes/?page_size=60');
  const lessons = await api('/api/lessons/?page_size=60');
  check('catalogue answers', Boolean(courses), String(courses?.count));
  check('seed rows present', (courses?.count || 0) >= 5, `count=${courses?.count}`);
  check('quizzes answer', Boolean(quizzes), `count=${quizzes?.count}`);
  check('lessons answer', Boolean(lessons), `count=${lessons?.count}`);
  if (!courses || !quizzes) {
    console.log('\nThe API did not answer — start the server first.');
    process.exit(1);
  }

  console.log('\nindex.html');
  {
    const { doc, errors } = await liveBoot('index.html', ['core', 'content', 'ui', 'home']);
    const batchCards = [...doc.querySelectorAll('#trending-grid .batch-card')];
    const apiTitles = rowsOf(courses).map((c) => c.title);
    check('batch rail renders API rows', batchCards.length > 0, String(batchCards.length));
    check(
      'batch titles match the API',
      batchCards.every((card) => apiTitles.some((title) => text(card).includes(title))),
      apiTitles[0]
    );
    const lessonRail = [...doc.querySelectorAll('#today-grid .today-card')];
    const lessonTitles = rowsOf(lessons).map((lesson) => lesson.title);
    check('lesson rail renders API rows', lessonRail.length > 0, String(lessonRail.length));
    check(
      'lesson titles match the API',
      lessonRail.every((card) => lessonTitles.some((title) => text(card).includes(title))),
      text(lessonRail[0]).slice(0, 60)
    );
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
    const folders = [...doc.querySelectorAll('#panel-curriculum .card')];
    check('curriculum renders server folders', folders.length === (detail.folders || []).length, `${folders.length}/${(detail.folders || []).length}`);
    const lessonsRendered = doc.querySelectorAll('#panel-curriculum .lesson-item').length;
    const lessonsExpected = (detail.folders || []).reduce((n, f) => n + (f.lessons || []).length, 0);
    check('every server lesson is listed', lessonsRendered === lessonsExpected, `${lessonsRendered}/${lessonsExpected}`);
    check('aside shows the real price', /Free|₹/.test(text(doc.querySelector('#course-aside'))), text(doc.querySelector('#course-aside')).slice(0, 50));
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

  console.log('\ndownloads.html');
  {
    const { doc, errors } = await liveBoot('downloads.html', ['core', 'content', 'ui', 'downloads']);
    const lists = ['#list-lectures', '#list-notes', '#list-tests'].map((selector) => doc.querySelector(selector));
    check('three panels rendered', lists.every((node) => node && node.innerHTML.trim().length > 0));
    check(
      'panels show rows or an explicit empty state',
      lists.every((node) => node.querySelector('.dl-row') || node.querySelector('.empty-state'))
    );
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
    const { doc, errors } = await liveBoot('player.html', ['core', 'content', 'ui', 'player'], `?lesson=${lesson.id}`);
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
  }

  console.log('\nbatch page lists its faculty (live rows)');
  {
    const list = await api('/api/courses/?page_size=6');
    const course = rowsOf(list).find((row) => row.slug === 'demo-jee-main-2027') || rowsOf(list)[0];
    const detail = await api(`/api/courses/${course.id}/`);
    const { doc, errors } = await liveBoot('course.html', ['core', 'content', 'ui', 'course'], `?slug=${course.slug}`);

    if ((detail.faculty || []).length) {
      const cards = doc.querySelectorAll('#panel-faculty .faculty-card');
      check('every seeded teacher is on the page', cards.length === detail.faculty.length, `${cards.length}/${detail.faculty.length}`);
      check('the page names the same people', text(doc.querySelector('#panel-faculty')).includes(detail.faculty[0].name));
    } else {
      check('a batch without faculty says so', Boolean(doc.querySelector('#panel-faculty .empty-state')));
    }
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\nlearning loop: open a class, write a note, see it on the dashboard');
  {
    const session = await signIn();
    if (!session) {
      check('a signed-in account is available for the learning-loop check', false, 'token refused');
    } else {
      const lessons = await api('/api/lessons/?page_size=1');
      const lesson = rowsOf(lessons)[0];

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
    const session = await signIn();
    // Ids move when the demo is reseeded, so the player is pointed at a lesson
    // that exists right now rather than at last week's id.
    const liveLessons = rowsOf(await api('/api/lessons/?page_size=60'));
    const lessonId = liveLessons[0]?.id;
    const PAGES = [
      ['index.html', ['core', 'content', 'ui', 'home'], '', false],
      ['courses.html', ['core', 'content', 'ui', 'courses'], '', false],
      ['course.html', ['core', 'content', 'ui', 'course'], '?slug=jee-main-2027', false],
      ['tests.html', ['core', 'content', 'ui', 'tests'], '', false],
      ['downloads.html', ['core', 'content', 'ui', 'downloads'], '', false],
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
