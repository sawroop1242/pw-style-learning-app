/**
 * Offline render check: every page boots with its module, renders real content,
 * mounts the shell and logs no errors.
 *
 * The network is unreachable here on purpose — this proves the bundled fixtures
 * still carry the site when the API is down (`live.js` covers the other case).
 */
const { boot } = require('./harness');

const PAGES = [
  ['index.html', ['core', 'data', 'ui', 'home']],
  ['player.html', ['core', 'data', 'ui', 'player']],
  ['downloads.html', ['core', 'data', 'ui', 'downloads']],
  ['community.html', ['core', 'data', 'ui', 'community']],
  ['profile.html', ['core', 'data', 'ui', 'profile']],
  ['courses.html', ['core', 'data', 'ui', 'courses']],
  ['course.html', ['core', 'data', 'ui', 'course']],
  ['tests.html', ['core', 'data', 'ui', 'tests']],
  ['dashboard.html', ['core', 'data', 'ui', 'dashboard']],
  ['legal.html', ['core', 'data', 'ui', 'legal']]
];

(async () => {
  let failed = 0;
  for (const [page, mods] of PAGES) {
    const { doc, errors } = await boot(page, mods);
    const h1 = doc.querySelectorAll('h1').length;
    const sidebar = doc.querySelectorAll('.sidebar .side-link').length;
    const tabs = doc.querySelectorAll('.tabbar a').length;
    const text = (doc.querySelector('main')?.textContent || '').replace(/\s+/g, ' ').trim();
    const problems = [];
    if (!h1) problems.push('no h1');
    if (!sidebar) problems.push('no sidebar');
    if (!tabs) problems.push('no tabbar');
    if (text.length < 120) problems.push(`main too empty (${text.length})`);
    if (errors.length) problems.push(errors[0].slice(0, 160));
    if (problems.length) failed += 1;
    console.log(
      `${problems.length ? '✗' : '✓'} ${page.padEnd(16)} h1=${h1} side=${sidebar} tabs=${tabs} text=${text.length} ${problems.join(' | ')}`
    );
  }
  console.log(failed === 0 ? '\nALL PAGES OK' : `\n${failed} PAGE(S) FAILED`);
  process.exit(failed === 0 ? 0 : 1);
})();
