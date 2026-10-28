/**
 * Render check: every page boots its module and renders, against a stubbed API.
 *
 * Two cases per page:
 *   • data   — the stub answers, so the page must show server rows
 *   • outage — no network at all, so the page must say so instead of inventing
 *
 * Both cases must mount the shell (sidebar + tabbar), keep one h1, and log no
 * console errors. `live.js` repeats the data case against the real server.
 */
const { boot } = require('./harness');
const { makeStub } = require('./stub');

const PAGES = [
  ['index.html', ['core', 'content', 'ui', 'home']],
  ['courses.html', ['core', 'content', 'ui', 'courses']],
  ['course.html', ['core', 'content', 'ui', 'course'], '?slug=jee-main-2027'],
  ['tests.html', ['core', 'content', 'ui', 'tests']],
  ['downloads.html', ['core', 'content', 'ui', 'downloads']],
  ['community.html', ['core', 'content', 'ui', 'community']],
  ['profile.html', ['core', 'content', 'ui', 'profile']],
  ['dashboard.html', ['core', 'content', 'ui', 'dashboard']],
  ['player.html', ['core', 'content', 'ui', 'player'], '?lesson=12'],
  ['legal.html', ['core', 'content', 'ui', 'legal']]
];

/* A page whose content is editorial rather than rows. */
const STATIC = ['legal.html'];

/* Dashboard and profile only show account data to a signed-in visitor. */
const SIGNED_IN = {
  'studyspace.access': 'stub-access-token',
  'studyspace.refresh': 'stub-refresh-token',
  'studyspace.user': JSON.stringify({ username: 'stub_student', email: 'student@example.test' })
};

const OUTAGE_COPY = /could not|couldn’t|unavailable|not answer|no |Sign in|Nothing|Pick a|Loading|empty|No recording|not published|may have been/i;

async function inspect(page, mods, query, opts, label) {
  const { doc, errors } = await boot(page, mods, {
    query,
    fetcher: opts.fetcher,
    seedStorage: opts.seedStorage
  });
  const h1 = doc.querySelectorAll('h1').length;
  const sidebar = doc.querySelectorAll('.sidebar .side-link').length;
  const tabs = doc.querySelectorAll('.tabbar a').length;
  const main = (doc.querySelector('main')?.textContent || '').replace(/\s+/g, ' ').trim();
  const problems = [];

  if (!h1) problems.push('no h1');
  if (!sidebar) problems.push('no sidebar');
  if (!tabs) problems.push('no tabbar');
  if (errors.length) problems.push(errors[0].slice(0, 200));
  if (opts.expectData) {
    const rows = doc.querySelectorAll(
      '.batch-card, .test-card, .today-card, .lesson-item, .dl-row, .post-card, .upcoming-item, .note-preview, .menu-row'
    ).length;
    if (!rows) problems.push('no rows rendered');
  } else if (!OUTAGE_COPY.test(main) && main.length > 0) {
    problems.push('outage is not explained to the user');
  }

  console.log(
    `${problems.length ? '✗' : '✓'} ${page.padEnd(16)} ${label.padEnd(7)} h1=${h1} side=${sidebar} tabs=${tabs} text=${main.length} ${
      problems.join(' | ')
    }`
  );
  return problems.length === 0;
}

(async () => {
  let failed = 0;

  console.log('\nWith the API answering');
  for (const [page, mods, query = ''] of PAGES) {
    const ok = await inspect(
      page,
      mods,
      query,
      { fetcher: makeStub({ signedIn: true }), seedStorage: SIGNED_IN, expectData: !STATIC.includes(page) },
      'data'
    );
    if (!ok) failed += 1;
  }

  console.log('\nWith the API unreachable');
  for (const [page, mods, query = ''] of PAGES) {
    const ok = await inspect(page, mods, query, { fetcher: null, expectData: false }, 'outage');
    if (!ok) failed += 1;
  }

  console.log('\nWith an empty catalogue');
  for (const page of ['index.html', 'courses.html', 'tests.html', 'downloads.html', 'community.html']) {
    const mods = PAGES.find((row) => row[0] === page)[1];
    const { doc, errors } = await boot(page, mods, { fetcher: makeStub({ empty: true }), seedStorage: SIGNED_IN });
    const empty = Boolean(doc.querySelector('#course-empty .empty-state, #test-empty .empty-state, #trending-grid .empty-state, #announcement-list .empty-state, #list-lectures .empty-state'));
    const problems = [];
    if (!empty) problems.push('no empty state');
    if (errors.length) problems.push(errors[0].slice(0, 160));
    if (problems.length) failed += 1;
    console.log(`${problems.length ? '✗' : '✓'} ${page.padEnd(16)} empty   ${problems.join(' | ')}`);
  }

  console.log(failed === 0 ? '\nALL PAGES OK' : `\n${failed} CHECK(S) FAILED`);
  process.exit(failed === 0 ? 0 : 1);
})();
