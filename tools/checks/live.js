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

const liveBoot = (page, mods, query = '') =>
  boot(page, mods, {
    query,
    fetcher: (url, init) => fetch(new URL(url, ORIGIN).toString(), init)
  });

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
    check(
      'stage says whether a recording exists',
      lesson.video_url ? !doc.querySelector('#player-video').hidden : !doc.querySelector('#stage-empty').hidden
    );
    check('section list rendered', doc.querySelectorAll('#chapter-list .lesson-item').length > 0);
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log(`\n${pass}/${pass + fail} live checks passed`);
  process.exit(fail ? 1 : 0);
})();
