/**
 * Offline interaction suite.
 *
 * Everything here runs with the network unavailable, so it exercises the state
 * machine in the page itself: the shell drawer, tab strips, the exam window
 * (answer → palette → pause → report → submit → result), filters and likes.
 */
const { boot, click, key, wait, reporter } = require('./harness');

const { check, finish } = reporter();

(async () => {
  /* ------------------------------- shell -------------------------------- */
  {
    console.log('\nshell');
    const { window, doc, errors } = await boot('index.html', ['core', 'data', 'ui', 'home']);
    check('seven sidebar links', doc.querySelectorAll('.sidebar .side-link').length === 7, String(doc.querySelectorAll('.sidebar .side-link').length));
    check('Home is the current page', doc.querySelector('.side-link[aria-current="page"]').textContent.trim() === 'Home');
    check('four bottom tabs', doc.querySelectorAll('.tabbar a').length === 4);
    check(
      'tab labels match the reference',
      [...doc.querySelectorAll('.tabbar a span')].map((s) => s.textContent.trim()).join('|') === 'Home|Batches|Test Series|Profile'
    );
    check('no Khazana anywhere in the shell', !/khazana/i.test(doc.body.innerHTML));

    const menu = doc.querySelector('[data-menu-toggle]');
    const sidebar = doc.querySelector('.sidebar');
    click(window, menu);
    check('menu opens the drawer', sidebar.classList.contains('is-open') && menu.getAttribute('aria-expanded') === 'true');
    check('scrim shown while open', !doc.querySelector('[data-scrim]').hidden);
    check('body locked while the drawer is open', doc.body.classList.contains('is-locked'));
    key(window, doc.body, 'Escape');
    check('Escape closes the drawer', !sidebar.classList.contains('is-open') && doc.querySelector('[data-scrim]').hidden);
    check('top bar has search, bell and an account slot',
      Boolean(doc.querySelector('.topbar-search')) &&
      Boolean(doc.querySelector('.topbar [aria-label="Notifications"]')) &&
      Boolean(doc.querySelector('.topbar .user-chip, .topbar .topbar-cta')));
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ------------------------------- home --------------------------------- */
  {
    console.log('\nindex.html');
    const { window, doc, errors } = await boot('index.html', ['core', 'data', 'ui', 'home']);
    check('greeting rendered', /Hello,/.test(doc.querySelector('#welcome-title').textContent));
    check('four quick tiles', doc.querySelectorAll('.quick-tile').length === 4, String(doc.querySelectorAll('.quick-tile').length));
    check('four today cards', doc.querySelectorAll('.today-card').length === 4);
    check('three announcements', doc.querySelectorAll('#home-notices .notice-item').length === 3);
    check('three recommended batches', doc.querySelectorAll('#trending-grid .batch-card').length === 3);
    check('three test cards', doc.querySelectorAll('#home-tests .test-card').length === 3);
    check('five FAQs', doc.querySelectorAll('#faq-list .acc-head').length === 5);

    const heads = [...doc.querySelectorAll('#faq-list .acc-head')];
    check('first FAQ open', heads[0].getAttribute('aria-expanded') === 'true');
    click(window, heads[1]);
    check('opening another closes the first', heads[0].getAttribute('aria-expanded') === 'false');
    check('only one panel visible', [...doc.querySelectorAll('#faq-list .acc-panel')].filter((p) => !p.hidden).length === 1);
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ------------------------------ courses ------------------------------- */
  {
    console.log('\ncourses.html');
    const { window, doc, errors } = await boot('courses.html', ['core', 'data', 'ui', 'courses']);
    const cards = doc.querySelectorAll('#course-grid .batch-card').length;
    check('nine cards on page 1', cards === 9, String(cards));
    check('All tab open by default', doc.querySelector('#tab-all').getAttribute('aria-selected') === 'true');
    click(window, doc.querySelector('#tab-fav'));
    check('Favorite tab reveals the empty state', !doc.querySelector('#panel-fav').hidden && Boolean(doc.querySelector('#fav-empty .empty-state')));
    check('All panel hidden', doc.querySelector('#panel-all').hidden);
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ------------------------------- tests -------------------------------- */
  {
    console.log('\ntests.html');
    const { window, doc, errors } = await boot('tests.html', ['core', 'data', 'ui', 'tests']);
    check('test cards rendered', doc.querySelectorAll('#test-grid .test-card').length > 0, String(doc.querySelectorAll('#test-grid .test-card').length));
    const chips = [...doc.querySelectorAll('#test-filters .chip')];
    check('exam filter chips built', chips.length > 1, String(chips.length));
    const before = doc.querySelectorAll('#test-grid .test-card').length;
    click(window, chips[1]);
    check('filtering narrows the grid', doc.querySelectorAll('#test-grid .test-card').length <= before);
    // The strip is re-rendered on click, so the pressed state is read from the
    // new node rather than the detached one that was clicked.
    const active = doc.querySelectorAll('#test-filters .chip')[1];
    check('active chip is announced', active.getAttribute('aria-pressed') === 'true' && active.classList.contains('is-active'));
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ---------------------------- exam window ----------------------------- */
  {
    console.log('\ntest-player.html');
    const { window, doc, errors } = await boot('test-player.html', ['core', 'data', 'ui', 'test-player'], { query: '?test=1' });

    const start = doc.querySelector('#start-btn');
    check('start is gated on the agreement box', start.disabled);
    const agree = doc.querySelector('#agree');
    agree.checked = true;
    agree.dispatchEvent(new window.Event('change', { bubbles: true }));
    check('agreeing unlocks start', !start.disabled);

    click(window, start);
    await wait(400);

    check('exam view is shown', !doc.querySelector('#exam-view').hidden);
    check('intro view is hidden', doc.querySelector('#intro-view').hidden);

    const digits = [...doc.querySelectorAll('.exam-clock-digits b')].map((n) => n.textContent);
    check('clock is HH:MM:SS', digits.length === 3 && digits.every((d) => /^\d{2}$/.test(d)), digits.join(':'));
    check('pause and full-screen controls exist', Boolean(doc.querySelector('#pause-btn')) && Boolean(doc.querySelector('#fullscreen-btn')));

    const tabs = [...doc.querySelectorAll('#section-tabs .exam-tab')];
    check('section strip lists every section', tabs.length === 4, String(tabs.length));
    check('first section is selected', tabs[0].getAttribute('aria-selected') === 'true');
    check('palette numbers the active section only', doc.querySelectorAll('#palette-groups .pal-btn').length === 3);
    check('legend counts five statuses', doc.querySelectorAll('#legend-counts li').length === 5);
    check('question paper and instructions buttons exist', Boolean(doc.querySelector('#paper-btn')) && Boolean(doc.querySelector('#instructions-btn')));
    check('submit lives in the palette rail', Boolean(doc.querySelector('#submit-rail-btn')));

    check('question number reads like the reference', /^Question No\. 1$/.test(doc.querySelector('#q-number').textContent));
    check('marks shown', doc.querySelector('#q-marks').textContent === '+4' && doc.querySelector('#q-negative').textContent === '-1');
    check('per-question time shown', /^\d{2}:\d{2}$/.test(doc.querySelector('#q-time').textContent), doc.querySelector('#q-time').textContent);

    const opt = doc.querySelectorAll('.qoption input')[1];
    opt.checked = true;
    opt.dispatchEvent(new window.Event('change', { bubbles: true }));
    await wait(200);
    check('chosen option is highlighted', doc.querySelectorAll('.qoption')[1].classList.contains('is-selected'));
    check('palette turns answered', doc.querySelectorAll('.pal-btn')[0].classList.contains('is-answered'));
    check('legend counted the answer', doc.querySelector('#legend-counts li b').textContent === '1');

    click(window, doc.querySelector('#next-btn'));
    await wait(150);
    check('save & next advances', doc.querySelector('#q-number').textContent === 'Question No. 2');

    click(window, doc.querySelector('#mark-btn'));
    await wait(150);
    check('mark for review paints the palette', [...doc.querySelectorAll('.pal-btn')].some((b) => b.classList.contains('is-marked')));
    check('mark for review advances', doc.querySelector('#q-number').textContent === 'Question No. 3');

    click(window, doc.querySelector('#prev-btn'));
    click(window, doc.querySelector('#prev-btn'));
    await wait(150);
    click(window, doc.querySelector('#clear-btn'));
    await wait(150);
    check('clear removes the answer', ![...doc.querySelectorAll('.pal-btn')].some((b) => b.classList.contains('is-answered')));

    key(window, doc.body, 'ArrowRight');
    await wait(100);
    check('arrow keys move between questions', doc.querySelector('#q-number').textContent === 'Question No. 2');
    key(window, doc.body, '3');
    await wait(150);
    check('number keys answer', doc.querySelectorAll('.qoption')[2].classList.contains('is-selected'));

    click(window, doc.querySelectorAll('#section-tabs .exam-tab')[3]);
    await wait(200);
    check('comprehension block appears for its questions', !doc.querySelector('#comprehension').hidden);
    check('figure renders an accessible bar chart', Boolean(doc.querySelector('#comprehension svg[role="img"][aria-label]')));
    check('bars drawn', doc.querySelectorAll('.qchart-bar rect').length === 5);
    check('marks switch per question', doc.querySelector('#q-marks').textContent === '+2');

    click(window, doc.querySelector('#pause-btn'));
    await wait(100);
    check('pause shows the veil', !doc.querySelector('#pause-veil').hidden);
    const frozen = [...doc.querySelectorAll('.exam-clock-digits b')].map((n) => n.textContent).join(':');
    await wait(1200);
    check('clock does not tick while paused', [...doc.querySelectorAll('.exam-clock-digits b')].map((n) => n.textContent).join(':') === frozen);
    click(window, doc.querySelector('#resume-btn'));
    await wait(150);
    check('resume hides the veil', doc.querySelector('#pause-veil').hidden);

    click(window, doc.querySelector('#instructions-btn'));
    await wait(100);
    check('instructions modal opens', doc.querySelector('#instructions-modal').classList.contains('is-open'));
    check('instructions list filled', doc.querySelectorAll('#instruction-list li').length >= 5);
    key(window, doc.body, 'Escape');
    check('Escape closes instructions', !doc.querySelector('#instructions-modal').classList.contains('is-open'));

    click(window, doc.querySelector('#report-btn'));
    await wait(100);
    check('report modal opens on the current question', doc.querySelector('#report-modal').classList.contains('is-open'));
    doc.querySelector('#report-reason').value = 'Chart label missing';
    doc.querySelector('#report-form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await wait(100);
    check('report is stored and marked on the question', doc.querySelector('#report-btn').classList.contains('is-reported'));

    click(window, doc.querySelector('#submit-btn'));
    await wait(150);
    check('submit opens the summary modal', doc.querySelector('#submit-modal').classList.contains('is-open'));
    check('summary rows per section', doc.querySelectorAll('#summary-rows tr').length === 4);
    click(window, doc.querySelector('#confirm-submit'));
    await wait(900);
    check('result view replaces the exam', !doc.querySelector('#result-view').hidden && doc.querySelector('#exam-view').hidden);
    check('score computed locally', /\d/.test(doc.querySelector('#result-hero').textContent || ''));
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ----------------------------- community ------------------------------ */
  {
    console.log('\ncommunity.html');
    const { window, doc, errors } = await boot('community.html', ['core', 'data', 'ui', 'community']);
    check('discussion threads render', doc.querySelectorAll('.post-card').length > 0, String(doc.querySelectorAll('.post-card').length));
    const like = doc.querySelector('[data-like]');
    const before = Number(like.textContent.replace(/\D/g, '')) || 0;
    click(window, like);
    await wait(80);
    const after = Number(like.textContent.replace(/\D/g, '')) || 0;
    check('like increments', after === before + 1, `${before} → ${after}`);
    click(window, like);
    await wait(80);
    check('liking again undoes it', (Number(like.textContent.replace(/\D/g, '')) || 0) === before);
    check('no console errors', errors.length === 0, errors[0]);
  }

  process.exit(finish('interaction checks') ? 0 : 1);
})();
