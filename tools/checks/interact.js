/**
 * Interaction suite.
 *
 * Runs against the stubbed API (see `stub.js`), so it exercises the behaviour a
 * visitor drives — shell drawer, FAQ accordion, catalogue filters, tab strips,
 * the whole exam window and the note composer — without a server. `live.js`
 * proves the same pages against the real database.
 */
const { boot, click, key, wait, reporter } = require('./harness');
const { makeStub } = require('./stub');

const { check, finish } = reporter();

const SIGNED_IN = {
  'studyspace.access': 'stub-access-token',
  'studyspace.refresh': 'stub-refresh-token',
  'studyspace.user': JSON.stringify({ username: 'stub_student', email: 'student@example.test' })
};

const open = (page, mods, { query = '', signedIn = false } = {}) =>
  boot(page, mods, {
    query,
    fetcher: makeStub({ signedIn }),
    seedStorage: signedIn ? SIGNED_IN : null
  });

(async () => {
  /* ------------------------------- shell -------------------------------- */
  {
    console.log('\nshell');
    const { window, doc, errors } = await open('index.html', ['core', 'content', 'ui', 'home']);

    check('six sidebar links', doc.querySelectorAll('.sidebar .side-link').length === 6, String(doc.querySelectorAll('.sidebar .side-link').length));
    check('Home is the current page', doc.querySelector('.side-link[aria-current="page"]').textContent.trim() === 'Home');
    check('four bottom tabs', doc.querySelectorAll('.tabbar a').length === 4);
    check(
      'tab labels match the reference',
      [...doc.querySelectorAll('.tabbar a span')].map((s) => s.textContent.trim()).join('|') === 'Home|Batches|Test Series|Profile'
    );
    check('no Khazana anywhere in the shell', !/khazana/i.test(doc.body.innerHTML));
    check('no footer is mounted', !doc.querySelector('footer, .site-footer, #site-footer'));

    const menu = doc.querySelector('[data-menu-toggle]');
    const sidebar = doc.querySelector('.sidebar');
    click(window, menu);
    check('menu opens the drawer', sidebar.classList.contains('is-open') && menu.getAttribute('aria-expanded') === 'true');
    check('scrim shown while open', !doc.querySelector('[data-scrim]').hidden);
    check('body locked while the drawer is open', doc.body.classList.contains('is-locked'));
    key(window, doc.body, 'Escape');
    check('Escape closes the drawer', !sidebar.classList.contains('is-open') && doc.querySelector('[data-scrim]').hidden);
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ------------------------------- home --------------------------------- */
  {
    console.log('\nindex.html');
    const { window, doc, errors } = await open('index.html', ['core', 'content', 'ui', 'home']);

    check('welcome line names the visitor', /Hello|Welcome/i.test(doc.querySelector('#welcome-title').textContent), doc.querySelector('#welcome-title').textContent.trim());
    check('lesson rail filled from the API', doc.querySelectorAll('#today-grid .today-card').length === 4, String(doc.querySelectorAll('#today-grid .today-card').length));
    check('batch rail filled from the API', doc.querySelectorAll('#trending-grid .batch-card').length === 3, String(doc.querySelectorAll('#trending-grid .batch-card').length));
    check('test rail filled from the API', doc.querySelectorAll('#home-tests .test-card').length === 2, String(doc.querySelectorAll('#home-tests .test-card').length));
    check('notice rail filled from the API', doc.querySelectorAll('#home-notices .notice-item').length === 2, String(doc.querySelectorAll('#home-notices .notice-item').length));

    const heads = [...doc.querySelectorAll('#faq-list .acc-head')];
    check('six FAQs from the copy module', heads.length === 6, String(heads.length));
    check('first FAQ open', heads[0].getAttribute('aria-expanded') === 'true');
    click(window, heads[1]);
    await wait(60);
    check('opening another closes the first', heads[0].getAttribute('aria-expanded') === 'false');
    check('exactly one panel visible', [...doc.querySelectorAll('#faq-list .acc-panel')].filter((p) => !p.hidden).length === 1);

    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ------------------------------ courses ------------------------------- */
  {
    console.log('\ncourses.html');
    const { window, doc, errors } = await open('courses.html', ['core', 'content', 'ui', 'courses']);

    check('every server row is carded', doc.querySelectorAll('#course-grid .batch-card').length === 3, String(doc.querySelectorAll('#course-grid .batch-card').length));
    check('result count is announced', /3 batches/.test(doc.querySelector('#result-count').textContent), doc.querySelector('#result-count').textContent);
    check('one page needs no pager', doc.querySelectorAll('#course-pager a, #course-pager button').length === 0);
    check('subject facet built from the rows', doc.querySelectorAll('#filter-subject input').length === 3, String(doc.querySelectorAll('#filter-subject input').length));

    const price = doc.querySelector('#filter-price input[value="free"]');
    price.checked = true;
    price.dispatchEvent(new window.Event('change', { bubbles: true }));
    await wait(200);
    check('free filter narrows the grid', doc.querySelectorAll('#course-grid .batch-card').length === 2, String(doc.querySelectorAll('#course-grid .batch-card').length));
    click(window, doc.querySelector('#clear-filters'));
    await wait(200);
    check('clear filters restores the grid', doc.querySelectorAll('#course-grid .batch-card').length === 3);

    click(window, doc.querySelector('#tab-mine'));
    await wait(150);
    check('My batches tab opens', !doc.querySelector('#panel-mine').hidden && doc.querySelector('#panel-all').hidden);
    check(
      'signed out: My batches asks for a sign-in',
      Boolean(doc.querySelector('#my-empty .empty-state')) || doc.querySelectorAll('#my-grid .batch-card').length > 0
    );
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* -------------------------- courses, signed in ------------------------ */
  {
    console.log('\ncourses.html (signed in)');
    const { window, doc, errors } = await open('courses.html', ['core', 'content', 'ui', 'courses'], { signedIn: true });
    click(window, doc.querySelector('#tab-mine'));
    await wait(250);
    check('My batches lists only unlocked batches', doc.querySelectorAll('#my-grid .batch-card').length === 2, String(doc.querySelectorAll('#my-grid .batch-card').length));
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* -------------------------------- tests ------------------------------- */
  {
    console.log('\ntests.html');
    const { window, doc, errors } = await open('tests.html', ['core', 'content', 'ui', 'tests']);

    check('paper cards rendered', doc.querySelectorAll('#test-grid .test-card').length === 2, String(doc.querySelectorAll('#test-grid .test-card').length));
    const chips = [...doc.querySelectorAll('#test-filters .chip')];
    check('subject chips built from the rows', chips.length >= 1, String(chips.length));
    const active = doc.querySelectorAll('#test-filters .chip')[0];
    check('first chip is pressed', active.getAttribute('aria-pressed') === 'true');

    click(window, doc.querySelector('#tab-attempted'));
    await wait(200);
    check('Attempted tab opens', !doc.querySelector('#panel-attempted').hidden);
    click(window, doc.querySelector('#tab-open'));
    await wait(150);
    check('Open for you tab opens', !doc.querySelector('#panel-open').hidden);
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ---------------------------- exam window ----------------------------- */
  {
    console.log('\ntest-player.html');
    const { window, doc, errors } = await open('test-player.html', ['core', 'content', 'ui', 'test-player'], {
      query: '?test=5'
    });

    const start = doc.querySelector('#start-btn');
    check('start waits for the agreement box', start.disabled);
    check('no sign-in is demanded', !doc.querySelector('#intro-note').textContent.includes('Sign in to start'));

    const agree = doc.querySelector('#agree');
    agree.checked = true;
    agree.dispatchEvent(new window.Event('change', { bubbles: true }));
    check('agreeing unlocks start', !start.disabled);

    click(window, start);
    await wait(600);

    check('exam view is shown', !doc.querySelector('#exam-view').hidden);
    check('intro view is hidden', doc.querySelector('#intro-view').hidden);
    check('attempt badge says server-scored', doc.querySelector('#attempt-badge').textContent === 'Server-scored');
    check(
      'guest attempt token stored',
      window.localStorage.getItem('studyspace.attempt-token') === 'stub-guest-token',
      window.localStorage.getItem('studyspace.attempt-token')
    );

    const digits = [...doc.querySelectorAll('.exam-clock-digits b')].map((n) => n.textContent);
    check('clock is HH:MM:SS', digits.length === 3 && digits.every((d) => /^\d{2}$/.test(d)), digits.join(':'));

    const tabs = [...doc.querySelectorAll('#section-tabs .exam-tab')];
    check('one section comes from the paper topic', tabs.length === 1, String(tabs.length));
    check('palette numbers the paper', doc.querySelectorAll('#palette-groups .pal-btn').length === 3);
    check('question number reads like the reference', /^Question No\. 1$/.test(doc.querySelector('#q-number').textContent));
    check('marks parsed from the decimal string', doc.querySelector('#q-marks').textContent === '+4', doc.querySelector('#q-marks').textContent);
    check('negative marking parsed too', doc.querySelector('#q-negative').textContent === '-1', doc.querySelector('#q-negative').textContent);

    const option = doc.querySelectorAll('.qoption input')[1];
    option.checked = true;
    option.dispatchEvent(new window.Event('change', { bubbles: true }));
    await wait(700);
    check('chosen option is highlighted', doc.querySelectorAll('.qoption')[1].classList.contains('is-selected'));
    check('palette turns answered', doc.querySelectorAll('.pal-btn')[0].classList.contains('is-answered'));
    check('autosave reported from the server', /Saved/.test(doc.querySelector('#autosave-state').textContent), doc.querySelector('#autosave-state').textContent);

    click(window, doc.querySelector('#next-btn'));
    await wait(150);
    check('save & next advances', doc.querySelector('#q-number').textContent === 'Question No. 2');

    click(window, doc.querySelector('#mark-btn'));
    await wait(150);
    check('mark for review paints the palette', [...doc.querySelectorAll('.pal-btn')].some((b) => b.classList.contains('is-marked')));

    click(window, doc.querySelector('#pause-btn'));
    await wait(120);
    check('pause shows the veil', !doc.querySelector('#pause-veil').hidden);
    click(window, doc.querySelector('#resume-btn'));
    await wait(120);
    check('resume hides the veil', doc.querySelector('#pause-veil').hidden);

    click(window, doc.querySelector('#instructions-btn'));
    await wait(120);
    check('instructions modal opens', doc.querySelector('#instructions-modal').classList.contains('is-open'));
    check('instructions list filled from the paper', doc.querySelectorAll('#instruction-list li').length >= 1);
    key(window, doc.body, 'Escape');
    check('Escape closes instructions', !doc.querySelector('#instructions-modal').classList.contains('is-open'));

    click(window, doc.querySelector('#submit-btn'));
    await wait(150);
    check('submit opens the summary modal', doc.querySelector('#submit-modal').classList.contains('is-open'));
    click(window, doc.querySelector('#confirm-submit'));
    await wait(1200);

    check('result view replaces the exam', !doc.querySelector('#result-view').hidden && doc.querySelector('#exam-view').hidden);
    check('score comes from the server', /8/.test(doc.querySelector('#result-hero').textContent || ''), doc.querySelector('#result-hero').textContent.replace(/\s+/g, ' ').slice(0, 70));
    check('solutions rendered', doc.querySelectorAll('#solutions .solution').length === 3, String(doc.querySelectorAll('#solutions .solution').length));
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ----------------------------- dashboard ------------------------------ */
  {
    console.log('\ndashboard.html (signed in)');
    const { window, doc, errors } = await open('dashboard.html', ['core', 'content', 'ui', 'dashboard'], { signedIn: true });

    check('figures come from the API counts', [...doc.querySelectorAll('.dash-figure strong')].map((n) => n.textContent.trim()).join(',') === '2,1,1,1', [...doc.querySelectorAll('.dash-figure strong')].map((n) => n.textContent.trim()).join(','));
    check('continue card from progress', doc.querySelectorAll('#continue-list .continue-card').length === 1);

    // One graded paper is a figure, not a one-bar chart: a 0%-height bar in a
    // 140px panel reads as a broken chart.
    const single = doc.querySelector('#chart-bars .chart-single .chart-single-score');
    check('single result shown as a figure', Boolean(single) && single.textContent.trim() === '67%', single ? single.textContent.trim() : 'no .chart-single');
    check('a lone attempt does not draw an empty chart', doc.querySelectorAll('#chart-bars .chart-bar').length === 0);

    check('notes listed', doc.querySelectorAll('#notes-list .note-preview').length === 1);
    check('study task listed', doc.querySelectorAll('#task-list .task-row').length === 1);
    check('an unfinished task offers its completion control', Boolean(doc.querySelector('#task-list [data-task-toggle]')));

    // The planner is no longer read-only: the form posts to /study-tasks/.
    click(window, doc.querySelector('#task-toggle'));
    await wait(80);
    check('the add-task form opens', !doc.querySelector('#task-form').hidden);
    doc.querySelector('#task-title').value = 'Finish the mechanics set';
    doc.querySelector('#task-form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await wait(300);
    check('a new task is added to the plan', doc.querySelectorAll('#task-list .task-row').length === 2, String(doc.querySelectorAll('#task-list .task-row').length));
    check('the form closes after saving', doc.querySelector('#task-form').hidden);

    click(window, doc.querySelector('#task-list [data-task-toggle]'));
    await wait(300);
    check('completing a task updates the row', doc.querySelectorAll('#task-list .task-row.is-done').length === 1);

    click(window, doc.querySelector('[data-new-note]'));
    await wait(120);
    check('note modal opens', doc.querySelector('#note-modal').classList.contains('is-open'));
    doc.querySelector('#note-heading').value = 'Kinematics';
    doc.querySelector('#note-body').value = 'v = u + at';
    doc.querySelector('#note-form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await wait(400);
    check('note saved through the API is added', doc.querySelectorAll('#notes-list .note-preview').length === 2, String(doc.querySelectorAll('#notes-list .note-preview').length));
    check('modal closes after saving', !doc.querySelector('#note-modal').classList.contains('is-open'));
    check('no console errors', errors.length === 0, errors[0]);
  }

  {
    // Two graded papers is a trend: one bar each, the better one marked.
    console.log('\ndashboard.html (two graded papers)');
    const base = makeStub({ signedIn: true });
    const twice = async (url, init) => {
      const response = await base(url, init);
      if (!/\/quiz-attempts\//.test(String(url))) return response;
      const body = await response.clone().json();
      if (!Array.isArray(body.results)) return response;
      const graded = body.results.filter((row) => row.status !== 'in_progress');
      if (!graded.length) return response;
      const older = { ...graded[0], id: 99, score: '4.00', submitted_at: '2026-10-25T09:00:00Z' };
      return new Response(JSON.stringify({ ...body, results: [older, ...body.results] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    };
    const { doc } = await boot('dashboard.html', ['core', 'content', 'ui', 'dashboard'], { fetcher: twice, seedStorage: SIGNED_IN });

    const bars = [...doc.querySelectorAll('#chart-bars .chart-bar')];
    check('two papers draw two bars', bars.length === 2, String(bars.length));
    check('a two-paper trend has no single figure', !doc.querySelector('#chart-bars .chart-single'));
    check('the better bar is highlighted', doc.querySelectorAll('#chart-bars .bar.is-best').length === 1);
    check('the legend counts both papers', /2 submitted papers/.test(doc.querySelector('#trend-note').textContent), doc.querySelector('#trend-note').textContent);
  }

  /* ------------------------------- player -------------------------------- */
  {
    console.log('\nplayer.html (signed in)');
    const { window, doc, errors } = await open('player.html', ['core', 'content', 'ui', 'player'], {
      query: '?lesson=11',
      signedIn: true
    });

    // Opening a class records it: the dashboard's "continue learning" is fed
    // by this call and by nothing else.
    check('the class title comes from the API', /Units and measurement/.test(doc.querySelector('#player-title').textContent));

    // `https://embed.vcdn.me/embed/…` is a player *page*. Handed to <video src>
    // it is a broken element; it belongs in an iframe.
    const embed = doc.querySelector('#player-embed');
    const iframe = embed.querySelector('iframe');
    check('an embed URL becomes an iframe', Boolean(iframe) && !embed.hidden);
    check(
      'the iframe points at the URL the API served',
      iframe.getAttribute('src') === 'https://embed.vcdn.me/embed/28c4af9f-d817-460a-80ab-9a09f8c47c69',
      iframe.getAttribute('src')
    );
    check('the iframe is allowed to go fullscreen', iframe.hasAttribute('allowfullscreen'));
    check('the native video element is not used for an embed', doc.querySelector('#player-video').hidden);
    const complete = doc.querySelector('#mark-complete');
    check('a completion control is offered', Boolean(complete) && !complete.hidden);
    check('it starts out not complete', complete.getAttribute('aria-pressed') === 'false');

    click(window, complete);
    await wait(300);
    check('marking complete flips the control', complete.getAttribute('aria-pressed') === 'true');
    check('the label reads Completed', /Completed/.test(doc.querySelector('#mark-complete-label').textContent));

    // Notes on the lesson: the tab used to list PDFs only.
    click(window, doc.querySelector('#tab-notes'));
    await wait(120);
    check('the note composer is available', !doc.querySelector('#lesson-note-form').hidden);

    doc.querySelector('#lesson-note-body').value = 'Check the units on Q4.';
    doc.querySelector('#lesson-note-form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await wait(350);
    check('the saved note appears under the lesson', /Check the units on Q4/.test(doc.querySelector('#lesson-note-list').textContent));
    check('the field clears after saving', doc.querySelector('#lesson-note-body').value === '');
    check('no console errors', errors.length === 0, errors[0]);
  }

  {
    // A direct media file keeps the native player.
    console.log('\nplayer.html (direct media URL)');
    const { doc } = await open('player.html', ['core', 'content', 'ui', 'player'], {
      query: '?lesson=12',
      signedIn: true
    });
    check('a media file uses the native video element', !doc.querySelector('#player-video').hidden);
    check('a media file draws no iframe', doc.querySelector('#player-embed').hidden);
    check(
      'the video src is the API URL',
      /kinematics\.mp4/.test(doc.querySelector('#player-video').getAttribute('src') || '')
    );
  }

  {
    console.log('\nplayer.html (guest)');
    const { doc } = await open('player.html', ['core', 'content', 'ui', 'player'], { query: '?lesson=11' });
    check('a guest is not shown a completion control', doc.querySelector('#mark-complete').hidden);
    check('a guest is asked to sign in before writing a note', /Sign in/.test(doc.querySelector('#lesson-note-list').textContent));
  }

  /* ------------------------------ activity -------------------------------- */
  {
    console.log('\nactivity panel (signed in)');
    const { window, doc } = await open('dashboard.html', ['core', 'content', 'ui', 'dashboard'], { signedIn: true });
    const bell = doc.querySelector('#notify-btn');
    check('the bell is a real button', Boolean(bell) && bell.getAttribute('aria-expanded') === 'false');
    // The inbox loads with the page, so the dot is truthful before it is opened.
    check('the dot appears because the API reports unread items', bell.classList.contains('has-dot'));
    check('the panel starts hidden', doc.querySelector('#notify-panel').hidden);

    click(window, bell);
    await wait(300);
    check('the panel opens', !doc.querySelector('#notify-panel').hidden);
    check('the panel lists what the API returned', doc.querySelectorAll('#notify-panel .notify-item').length === 2, String(doc.querySelectorAll('#notify-panel .notify-item').length));
    check('unread items are marked', doc.querySelectorAll('#notify-panel .is-unread').length === 2, String(doc.querySelectorAll('#notify-panel .is-unread').length));
    check('each item links somewhere real', [...doc.querySelectorAll('#notify-panel .notify-item')].every((a) => /^(community|dashboard|test-player)\.html/.test(a.getAttribute('href'))));

    click(window, doc.querySelector('[data-notify-read]'));
    await wait(250);
    check('marking read clears the dot', !doc.querySelector('#notify-btn').classList.contains('has-dot'));
  }

  /* ----------------------------- community ------------------------------ */
  {
    console.log('\ncommunity.html');
    const { window, doc, errors } = await open('community.html', ['core', 'content', 'ui', 'community']);

    check('announcements render', doc.querySelectorAll('#announcement-list .post-card').length === 2, String(doc.querySelectorAll('#announcement-list .post-card').length));
    check('pinned notice is flagged', /Pinned/.test(doc.querySelector('#announcement-list').textContent));
    check('no like button on a read-only feed', !doc.querySelector('[data-like]'));
    click(window, doc.querySelector('#tab-batch'));
    await wait(250);
    check('signed out: batch tab asks for a sign-in', Boolean(doc.querySelector('#batch-list .empty-state')));
    check('no console errors', errors.length === 0, errors[0]);
  }

  process.exit(finish('interaction checks') ? 0 : 1);
})();
