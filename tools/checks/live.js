/**
 * Live check: boot pages with the network switched on.
 *
 * `check.js` proves the fixture fallback; this proves the pages render *server*
 * data. Start the API and the static server first (see tools/checks/README.md),
 * then run `node live.js`.
 */
const { boot } = require('./harness');

const ORIGIN = process.env.CHECK_ORIGIN || 'http://127.0.0.1:8080';

// Relative URLs in the page resolve against the preview origin, and the request
// is forwarded to the real server rather than stubbed.
const liveBoot = (page, mods, query = '') =>
  boot(page, mods, {
    query,
    fetcher: (url, init) => fetch(new URL(url, ORIGIN).toString(), init)
  });

let pass = 0;
let fail = 0;
const check = (name, ok, detail = '') => {
  if (ok) pass += 1; else fail += 1;
  console.log(`${ok ? '  ✓' : '  ✗'} ${name}${detail ? '  — ' + detail : ''}`);
};

(async () => {
  console.log('\nAPI reachable');
  const health = await fetch(`${ORIGIN}/api/courses/?page_size=1`).catch(() => null);
  check('catalogue answers', Boolean(health && health.ok), health ? String(health.status) : 'no response');
  const coursePayload = await health.json();
  check('seed rows present', coursePayload.count >= 5, `count=${coursePayload.count}`);

  console.log('\ntests.html (live)');
  {
    const { doc, errors } = await liveBoot('tests.html', ['core', 'data', 'ui', 'tests']);
    const cards = [...doc.querySelectorAll('#test-grid .test-card')];
    check('three or more live test cards', cards.length >= 3, String(cards.length));
    const titles = cards.map((c) => c.querySelector('.test-title').textContent.trim());
    check('titles come from the API', titles.some((t) => t.includes('JEE Main Full Mock')), titles[0]);
    check('no fixture duplicate titles', new Set(titles).size === titles.length, titles.join(' | ').slice(0, 90));
    const exam = cards[0].querySelector('.test-eyebrow').textContent;
    check('exam label from the series subject', /Physics|Reasoning|Biology|English/.test(exam), exam.trim());
    check('question count from the server', /[1-9]\d* Questions/.test(cards[0].textContent), (cards[0].textContent.match(/\d+ Questions/) || [''])[0]);
    check('start links carry real ids', [...doc.querySelectorAll('.test-card a.btn')].every((a) => /test-player\.html\?test=\d+/.test(a.getAttribute('href'))));
    check('preview flag not raised', !doc.querySelector('#preview-flag') || doc.querySelector('#preview-flag').hidden);
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\nindex.html (live)');
  {
    const { doc, errors } = await liveBoot('index.html', ['core', 'data', 'ui', 'home']);
    const batches = [...doc.querySelectorAll('#trending-grid .batch-card')];
    check('three live batch cards', batches.length === 3, String(batches.length));
    check('batch titles from the API', batches.some((b) => /JEE Main 2027|NEET 2027|SSC CGL 2026|GATE CS 2027/.test(b.textContent)));
    const tests = [...doc.querySelectorAll('#home-tests .test-card')];
    check('three live test cards', tests.length === 3, String(tests.length));
    check('test cards labelled from the API', tests.every((t) => !/Untitled/.test(t.textContent)));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\ntest-player.html (live paper)');
  {
    const quizId = coursePayload.results ? null : null;
    const quizzes = await (await fetch(`${ORIGIN}/api/quizzes/?page_size=1`)).json();
    const id = quizzes.results[0].id;
    const { doc, errors } = await liveBoot('test-player.html', ['core', 'data', 'ui', 'test-player'], `?test=${id}`);
    const title = doc.querySelector('#intro-title').textContent.trim();
    check('intro title is the server quiz', /JEE Main Full Mock|SSC CGL|NEET|Bank PO/.test(title), title);
    check('question count matches the server', doc.querySelector('#intro-count').textContent.trim() === String(quizzes.results[0].question_count), doc.querySelector('#intro-count').textContent);
    const agree = doc.querySelector('#agree');
    agree.checked = true;
    agree.dispatchEvent(new doc.defaultView.Event('change', { bubbles: true }));
    doc.querySelector('#start-btn').dispatchEvent(new doc.defaultView.MouseEvent('click', { bubbles: true }));
    await new Promise((r) => setTimeout(r, 900));
    check('exam view opens with the server paper', !doc.querySelector('#exam-view').hidden);
    check('paper has questions', doc.querySelectorAll('.qoption').length === 4, String(doc.querySelectorAll('.qoption').length));
    check('section strip from question topics', [...doc.querySelectorAll('#section-tabs .exam-tab')].map((t) => t.textContent.trim().split(' ')[0]).join(',').includes('Physics'), [...doc.querySelectorAll('#section-tabs .exam-tab')].map((t) => t.textContent.trim()).join(' | '));
    check('marks come from the quiz', doc.querySelector('#q-marks').textContent === '+4', doc.querySelector('#q-marks').textContent);
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\ncourse.html (live batch)');
  {
    const { doc, errors } = await liveBoot('course.html', ['core', 'data', 'ui', 'course'], '?slug=demo-ssc-cgl-2026');
    const crumb = doc.querySelector('#crumb-title').textContent.trim();
    check('slug resolves to the right batch', crumb === 'SSC CGL 2026 Foundation', crumb);
    const headline = doc.querySelector('#course-headline').textContent;
    check('headline shows the server lesson count', /4 lessons/.test(headline), (headline.match(/\d+ lessons/) || [''])[0]);
    check('headline shows the server test count', /1 tests?/.test(headline), (headline.match(/\d+ tests?/) || [''])[0]);
    check('no invented enrolment or rating', !/enrolled/.test(headline) && !/★|⭐/.test(headline));
    const testsTab = doc.querySelector('#panel-tests').textContent;
    check('tests tab lists the real mock', /SSC CGL Tier I/.test(testsTab), testsTab.replace(/\s+/g, ' ').trim().slice(0, 60));
    check('tests tab has no invented counts', !/up to \d+ marks/.test(testsTab));
    check('faculty tab is honest', /being added/.test(doc.querySelector('#panel-faculty').textContent));
    check('no console errors', errors.length === 0, errors[0]);
  }

  console.log('\nquizzes nested under a course');
  {
    const list = await (await fetch(`${ORIGIN}/api/courses/`, { headers: { Accept: 'application/json' } })).json();
    const ssc = list.results.find((c) => c.slug === 'demo-ssc-cgl-2026');
    const nested = await (await fetch(`${ORIGIN}/api/quizzes/?course=${ssc.id}`)).json();
    check('course filter returns only its tests', nested.count === 1 && nested.results[0].course === ssc.id, `count=${nested.count}`);
  }

  console.log(`\n${pass}/${pass + fail} live checks passed`);
  process.exit(fail ? 1 : 0);
})();
