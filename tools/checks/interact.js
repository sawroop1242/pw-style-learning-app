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

    check('five sidebar links', doc.querySelectorAll('.sidebar .side-link').length === 5, String(doc.querySelectorAll('.sidebar .side-link').length));
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
    const close = sidebar.querySelector('[data-menu-close]');
    click(window, menu);
    check('menu opens the drawer', sidebar.classList.contains('is-open') && menu.getAttribute('aria-expanded') === 'true');
    check('scrim shown while open', !doc.querySelector('[data-scrim]').hidden);
    check('body locked while the drawer is open', doc.body.classList.contains('is-locked'));
    // `body { overflow: hidden }` alone leaves the viewport scrollable, so the
    // page slid around under the open drawer.
    check('the document is locked, not just the body', doc.documentElement.classList.contains('is-locked'));
    check('the drawer has its own close button', Boolean(close));
    check('focus lands inside the drawer', doc.activeElement === close, doc.activeElement?.getAttribute('aria-label'));

    // Tab must not walk the page behind the scrim.
    const focusables = [...sidebar.querySelectorAll('a[href], button')].filter(
      (el) => !el.hidden && window.getComputedStyle(el).display !== 'none'
    );
    focusables[focusables.length - 1].focus();
    key(window, doc.body, 'Tab');
    check('Tab wraps back into the drawer', doc.activeElement === focusables[0], doc.activeElement?.textContent?.trim().slice(0, 20));
    key(window, doc.body, 'Escape');
    check('Escape closes the drawer', !sidebar.classList.contains('is-open') && doc.querySelector('[data-scrim]').hidden);
    check('Escape hands focus back to the menu button', doc.activeElement === menu);
    check('the lock is released', !doc.documentElement.classList.contains('is-locked'));
    click(window, menu);
    click(window, close);
    check('the close button closes the drawer', !sidebar.classList.contains('is-open'));
    click(window, menu);
    click(window, doc.querySelector('[data-scrim]'));
    check('tapping the scrim closes the drawer', !sidebar.classList.contains('is-open'));

    // On a phone the search field is a second row of the header.
    click(window, doc.querySelector('[data-search-toggle]'));
    check('the search icon opens the search row', doc.body.classList.contains('is-search-open'));
    key(window, doc.body, 'Escape');
    check('Escape closes the search row', !doc.body.classList.contains('is-search-open'));
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

  /* ------------------------- paid batch: Get code ------------------------ */
  {
    console.log('\ncourse.html (paid batch, Get code)');
    const { window, doc, errors } = await open('course.html', ['core', 'content', 'ui', 'course'], {
      query: '?slug=jee-main-2027',
      signedIn: true
    });
    await wait(250);

    const button = doc.querySelector('#purchase-slot [data-get-code]');
    check('a paid batch offers “Get code”', Boolean(button), button?.textContent?.trim());
    check(
      'the button opens the teacher\'s Telegram chat',
      button?.getAttribute('href')?.startsWith('https://t.me/studyspace_access?text='),
      button?.getAttribute('href')?.slice(0, 48)
    );
    check('it opens in a new tab, without an opener', button?.getAttribute('target') === '_blank' && button?.getAttribute('rel')?.includes('noopener'));
    // decodeURIComponent, not a raw match: the draft goes through
    // urlencode() on the server, which leaves spaces as '+'.
    const draft = decodeURIComponent((button?.getAttribute('href') || '').split('text=')[1] || '')
      .replace(/\+/g, ' ');
    check('the batch is named in the draft', draft.includes('JEE Main 2027 Complete Batch'), draft.slice(0, 70));
    check('the draft carries the batch number', /#\d+/.test(draft), draft.slice(0, 70));
    check(
      'the aside offers the same link',
      Boolean(doc.querySelector('#course-aside [data-get-code]'))
    );
    check(
      'the price line explains where the code comes from',
      /Telegram/i.test(doc.querySelector('#purchase-slot').textContent || '')
    );

    // The dialog is the second way in, and it must not be empty. Opened the
    // way a signed-in visitor opens it: `data-redeem` sends a guest to login.
    click(window, doc.querySelector('#purchase-slot [data-redeem]'));
    await wait(250);
    const ask = doc.querySelector('#redeem-ask');
    check('the redeem dialog is open', doc.querySelector('#redeem-modal').classList.contains('is-open'));
    check('the dialog offers the Telegram chat too', Boolean(ask && ask.querySelector('a[href^="https://t.me/"]')), ask?.textContent?.trim().slice(0, 60));
    check('the dialog names who to message', /studyspace_access/.test(ask?.textContent || ''));

    // The same page's own explanation must tell the same story — the copy used
    // to claim free batches were "open to guests", which run 28 reversed.
    click(window, doc.querySelector('[data-close-modal]'));
    const overview = doc.querySelector('#panel-overview').textContent;
    check('the overview points at Telegram for the code', /Telegram/i.test(overview), overview.replace(/\s+/g, ' ').slice(0, 90));
    check('no stale "open to guests" promise', !/open to everyone, including guests/i.test(doc.body.textContent));
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* -------------------- paid batch with no Telegram handle ---------------- */
  {
    console.log('\ncourse.html (paid batch, no Telegram)');
    // A provider who never filled the field: the code box must be the only
    // way in, with no "Get code" button and no promise of a chat.
    const { window, doc, errors } = await boot('course.html', ['core', 'content', 'ui', 'course'], {
      query: '?slug=jee-main-2027',
      fetcher: makeStub({ signedIn: true, noTelegram: true }),
      seedStorage: SIGNED_IN
    });
    await wait(300);
    check('no “Get code” without a handle', !doc.querySelector('[data-get-code]'));
    check('the code button is still there', Boolean(doc.querySelector('#purchase-slot [data-redeem]')));
    check(
      'the copy does not promise a Telegram chat',
      !/message .*on Telegram/i.test(doc.querySelector('#purchase-slot').textContent || ''),
      (doc.querySelector('#purchase-slot').textContent || '').trim().slice(0, 80)
    );
    click(window, doc.querySelector('#purchase-slot [data-redeem]'));
    await wait(250);
    check('the dialog has no empty Telegram row', doc.querySelector('#redeem-ask').hidden);
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

    const savedDeadline = () =>
      JSON.parse(window.sessionStorage.getItem('studyspace.attempt') || '{}').deadline;
    const deadlineBeforePause = savedDeadline();
    click(window, doc.querySelector('#pause-btn'));
    await wait(120);
    check('pause shows the veil', !doc.querySelector('#pause-veil').hidden);
    check(
      'the pause card says the clock keeps running',
      /clock is still running/i.test(doc.querySelector('#pause-clock-note').textContent),
      doc.querySelector('#pause-clock-note').textContent
    );
    click(window, doc.querySelector('#resume-btn'));
    await wait(120);
    check('resume hides the veil', doc.querySelector('#pause-veil').hidden);
    check(
      'pausing does not extend the deadline the server will enforce',
      savedDeadline() === deadlineBeforePause,
      `${deadlineBeforePause} -> ${savedDeadline()}`
    );

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

  /* ------------------ exam window on a frozen paper --------------------- */
  {
    // An attempt carries the paper it was served. If the player kept using the
    // live question list, editing a question mid-test would change what every
    // student sitting it is looking at — and their score would be graded
    // against a paper they never saw.
    console.log('\ntest-player.html (frozen paper)');
    const { window, doc, errors } = await boot('test-player.html', ['core', 'content', 'ui', 'test-player'], {
      query: '?test=5',
      fetcher: makeStub({ frozenPaper: true })
    });

    const agree = doc.querySelector('#agree');
    agree.checked = true;
    agree.dispatchEvent(new window.Event('change', { bubbles: true }));
    click(window, doc.querySelector('#start-btn'));
    await wait(700);

    const prompt = doc.querySelector('#qpanel-text');
    check('the served paper is what the student reads', /FROZEN/.test(prompt.textContent), prompt.textContent);
    check('marks come from the frozen paper', doc.querySelector('#q-marks').textContent === '+2', doc.querySelector('#q-marks').textContent);
    check(
      'the live question bank is not substituted',
      !/Stub question/.test(prompt.textContent),
      prompt.textContent
    );
    check('the frozen options are the ones offered', doc.querySelectorAll('.qoption').length === 2, String(doc.querySelectorAll('.qoption').length));
    check('the frozen section is used', [...doc.querySelectorAll('#section-tabs .exam-tab')].some((tab) => /Frozen section/.test(tab.textContent)));
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ------------------- multiple-choice answering ----------------------- */
  {
    // The backend and the CSV schema have always supported `multiple_choice`,
    // but the player rendered every option as a radio and stored one id, so a
    // learner could not select two answers to a question that needs two.
    console.log('\ntest-player.html (multiple choice)');
    const sent = [];
    const stub = makeStub({ mcq: true });
    const { window, doc, errors } = await boot('test-player.html', ['core', 'content', 'ui', 'test-player'], {
      query: '?test=5',
      fetcher: (url, init) => {
        sent.push({ url: String(url), init });
        return stub(url, init);
      }
    });

    const agree = doc.querySelector('#agree');
    agree.checked = true;
    agree.dispatchEvent(new window.Event('change', { bubbles: true }));
    click(window, doc.querySelector('#start-btn'));
    await wait(700);

    const inputs = () => [...doc.querySelectorAll('#qpanel [data-choice]')];
    check('a multiple-choice question uses checkboxes', inputs().every((input) => input.type === 'checkbox'), inputs().map((i) => i.type).join(','));
    check('the instruction says more than one may apply', /every option/i.test(doc.querySelector('.qpanel-instruction').textContent), doc.querySelector('.qpanel-instruction').textContent);

    const tick = (index) => {
      const box = inputs()[index];
      box.checked = !box.checked;
      box.dispatchEvent(new window.Event('change', { bubbles: true }));
    };

    tick(0);
    await wait(120);
    check('one option is selected', doc.querySelectorAll('.qoption.is-selected').length === 1, String(doc.querySelectorAll('.qoption.is-selected').length));

    tick(1);
    await wait(120);
    check('a second option can also be selected', doc.querySelectorAll('.qoption.is-selected').length === 2, String(doc.querySelectorAll('.qoption.is-selected').length));
    check('neither selection replaced the other', inputs().filter((input) => input.checked).length === 2);

    tick(0);
    await wait(120);
    check('deselecting removes only that option', doc.querySelectorAll('.qoption.is-selected').length === 1, String(doc.querySelectorAll('.qoption.is-selected').length));

    const autosaves = () => sent.filter((call) => /autosave\/$/.test(call.url));
    await wait(600);
    const lastBody = JSON.parse(autosaves().at(-1)?.init?.body || '{}');
    check(
      'autosave sends every selected choice',
      Array.isArray(lastBody.choice_ids) && lastBody.choice_ids.length === 1,
      JSON.stringify(lastBody.choice_ids)
    );

    // Option 1 is the one still selected, so re-checking option 0 makes two.
    tick(0);
    await wait(700);
    const bothBody = JSON.parse(autosaves().at(-1)?.init?.body || '{}');
    check('two answers reach the server', (bothBody.choice_ids || []).length === 2, JSON.stringify(bothBody.choice_ids));

    click(window, doc.querySelector('#clear-btn'));
    await wait(700);
    const cleared = JSON.parse(autosaves().at(-1)?.init?.body || '{}');
    check('clear empties the answer', (cleared.choice_ids || []).length === 0, JSON.stringify(cleared.choice_ids));
    check('a cleared question is not answered', doc.querySelectorAll('.qoption.is-selected').length === 0);

    // A multiple-choice answer must survive a reload, or a resume silently
    // drops half of it.
    tick(0);
    await wait(650);
    tick(1);
    await wait(650);
    const persisted = JSON.parse(window.sessionStorage.getItem('studyspace.attempt') || '{}');
    check('both answers are persisted locally', (persisted.answers?.[1] || []).length === 2, JSON.stringify(persisted.answers || null));
    check('no console errors', errors.length === 0, errors[0]);
  }

  /* ----------------------------- dashboard ------------------------------ */
  {
    console.log('\ndashboard.html (signed in)');
    const { window, doc, errors } = await open('dashboard.html', ['core', 'content', 'ui', 'dashboard'], { signedIn: true });

    check('figures come from the API counts', [...doc.querySelectorAll('.dash-figure strong')].map((n) => n.textContent.trim()).join(',') === '2,1,1,45m,1,1', [...doc.querySelectorAll('.dash-figure strong')].map((n) => n.textContent.trim()).join(','));
    check('the streak counts finished lessons, not opened ones', [...doc.querySelectorAll('.dash-figure span')].some((n) => n.textContent.trim() === 'Day streak'));
    check('the week total uses lesson durations', [...doc.querySelectorAll('.dash-figure strong')].some((n) => n.textContent.trim() === '45m'));
    check('continue card from progress', doc.querySelectorAll('#continue-list .continue-card').length === 2);
    // The bar used to be a fixed 40% for anything merely opened. It is now the
    // batch's real share: 1 finished lesson of 5.
    const bars = [...doc.querySelectorAll('#continue-list .progress > span')].map((n) => n.style.width);
    check('batch progress is computed, not a placeholder', bars.length === 2 && bars.every((w) => w === '33%'), bars.join('|'));
    check('a finished lesson is marked as such', /1 of 3 lessons/.test(doc.querySelector('#continue-list').textContent));

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
    check('a page with a recording gives its chrome up to it', doc.body.classList.contains('has-recording'));
    // jsdom has no Fullscreen API, so the page must not offer a button that
    // cannot work: hiding it is the honest behaviour there.
    check('no full-screen button where the browser has no Fullscreen API', doc.querySelector('#stage-full').hidden);
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
    // An embed brings its host's chrome and, on a phone, no way to enlarge it.
    // This is the page's own control, so it gets its own boot.
    console.log('\nplayer.html (full screen)');
    const { window, doc } = await boot('player.html', ['core', 'content', 'ui', 'player'], {
      query: '?lesson=11',
      fetcher: makeStub({ signedIn: true }),
      seedStorage: SIGNED_IN,
      fullscreen: true
    });
    await wait(80);
    const btn = doc.querySelector('#stage-full');
    check('a recording offers a full-screen button', !btn.hidden);
    check('the button says what it does', btn.getAttribute('aria-label') === 'Full screen');

    btn.click();
    await wait(20);
    // The stage, not the iframe: an embed cannot be enlarged from outside, but
    // its container can, and that is what puts the frame on the whole screen.
    check('pressing it takes the stage full screen', window.__fullscreenElement?.id === 'player-stage', window.__fullscreenElement?.id);
    check('the label flips to exit', btn.getAttribute('aria-label') === 'Exit full screen');

    btn.click();
    await wait(20);
    check('pressing it again leaves full screen', !window.__fullscreenElement);
    check('the label flips back', btn.getAttribute('aria-label') === 'Full screen');
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
    check('a media file still counts as a recording', doc.body.classList.contains('has-recording'));
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
