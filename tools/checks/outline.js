/**
 * Outline screen check: does `staff/outline.js` actually move things and save?
 *
 * `courses/tests/test_admin_outline.py` proves the server refuses an order it
 * cannot trust. This file proves the screen produces the order it is looking at
 * — and that the three ways of changing it (arrow buttons, the section menu,
 * the arrow keys on a handle) all end in the same request.
 *
 * The DOM below is the contract the template renders, trimmed to the elements
 * the script reads. It is written by hand on purpose: a check that parses the
 * Django template would pass even if the template stopped emitting a handle.
 *
 * Dragging is exercised with stubbed geometry: jsdom has no layout, so the
 * "dragging" block below gives every row a 38px box and points
 * `elementFromPoint` at the list under the pointer. That is enough to drive the
 * script's pointerdown → pointermove → pointerup path, including a class
 * crossing into another section. What it cannot prove is the browser's own
 * pointer capture — the gesture still deserves one manual pass.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const { reporter } = require('./harness');

const SCRIPT = path.resolve(__dirname, '../../backend/static/staff/outline.js');
const { check, finish } = reporter();

const HTML = `<!doctype html><html><body>
<form data-outline data-revision="rev-1" data-save-url="/admin/courses/course/1/outline/">
  <input type="hidden" name="csrfmiddlewaretoken" value="csrf-token">
  <ol data-outline-sections>
    <li data-outline-section data-folder="11">
      <div data-outline-head>
        <button type="button" data-outline-handle><span></span></button>
        <span class="ss-outline-title">Units</span>
        <button type="button" data-outline-move="up"></button>
        <button type="button" data-outline-move="down"></button>
      </div>
      <ol data-outline-list data-folder="11">
        <li data-outline-lesson data-lesson="1">
          <button type="button" data-outline-handle></button>
          <span class="ss-outline-lesson-title">Measurement</span>
          <select data-outline-pick>
            <option value="">No section</option>
            <option value="11" selected>Units</option>
            <option value="12">Motion</option>
          </select>
          <button type="button" data-outline-move="up"></button>
          <button type="button" data-outline-move="down"></button>
        </li>
        <li data-outline-lesson data-lesson="2">
          <button type="button" data-outline-handle></button>
          <span class="ss-outline-lesson-title">Errors</span>
          <select data-outline-pick>
            <option value="">No section</option>
            <option value="11" selected>Units</option>
            <option value="12">Motion</option>
          </select>
          <button type="button" data-outline-move="up"></button>
          <button type="button" data-outline-move="down"></button>
        </li>
      </ol>
      <p data-outline-empty hidden></p>
    </li>
    <li data-outline-section data-folder="12">
      <div data-outline-head>
        <button type="button" data-outline-handle><span></span></button>
        <span class="ss-outline-title">Motion</span>
        <button type="button" data-outline-move="up"></button>
        <button type="button" data-outline-move="down"></button>
      </div>
      <ol data-outline-list data-folder="12">
        <li data-outline-lesson data-lesson="3">
          <button type="button" data-outline-handle></button>
          <span class="ss-outline-lesson-title">Velocity</span>
          <select data-outline-pick>
            <option value="">No section</option>
            <option value="11">Units</option>
            <option value="12" selected>Motion</option>
          </select>
          <button type="button" data-outline-move="up"></button>
          <button type="button" data-outline-move="down"></button>
        </li>
      </ol>
      <p data-outline-empty hidden></p>
    </li>
  </ol>
  <p id="outline-status" role="status" aria-live="polite">Nothing changed yet.</p>
  <button type="button" data-outline-reset disabled>Undo changes</button>
  <button type="submit" data-outline-save disabled>Save order</button>
</form>
</body></html>`;

/** Give every row a box, so "above/below" has an answer without a layout. */
function stubGeometry(window) {
  const { document } = window;
  window.Element.prototype.getBoundingClientRect = function () {
    const siblings = this.parentElement ? [...this.parentElement.children] : [];
    const index = Math.max(0, siblings.indexOf(this));
    return { top: index * 40, bottom: index * 40 + 38, height: 38, left: 0, right: 320, width: 320 };
  };
  const point = { node: null };
  document.elementFromPoint = () => point.node;
  return point;
}

function pointer(target, type, window, { x = 0, y = 0 } = {}) {
  const event = new window.Event(type, { bubbles: true, cancelable: true });
  event.pointerId = 1;
  event.button = 0;
  event.clientX = x;
  event.clientY = y;
  target.dispatchEvent(event);
  return event;
}

function makeScreen(fetchImpl) {
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (error) => console.error('jsdom:', error.message));
  const dom = new JSDOM(HTML, { url: 'https://admin.example/admin/courses/course/1/outline/', runScripts: 'outside-only' });
  dom.window.fetch = fetchImpl;
  dom.window.eval(fs.readFileSync(SCRIPT, 'utf8'));
  return { window: dom.window, doc: dom.window.document };
}

/** A fetch that answers with `body`/`status` and records what it was sent. */
function recordingFetch(status = 200, body = {}) {
  const calls = [];
  const impl = (url, init) => {
    calls.push({ url, init, payload: JSON.parse(init.body) });
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body)
    });
  };
  return { impl, calls };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function lessonIds(doc, folder) {
  return [...doc.querySelectorAll(`[data-outline-list][data-folder="${folder}"] [data-outline-lesson]`)].map(
    (row) => row.dataset.lesson
  );
}

function sectionIds(doc) {
  return [...doc.querySelectorAll('[data-outline-section]')].map((row) => row.dataset.folder);
}

(async () => {
  /* ------------------------------ controls ------------------------------ */
  {
    console.log('\ncontrols');
    const { window, doc } = makeScreen(recordingFetch().impl);
    const save = doc.querySelector('[data-outline-save]');
    const reset = doc.querySelector('[data-outline-reset]');

    check('save starts disabled', save.disabled === true);
    check('undo starts disabled', reset.disabled === true);

    const rows = [...doc.querySelectorAll('[data-outline-lesson]')];
    check('the first class cannot move up', rows[0].querySelector('[data-outline-move="up"]').disabled === true);
    check('the last class in a section cannot move down', rows[1].querySelector('[data-outline-move="down"]').disabled === true);
    check('the last section cannot move down', doc.querySelectorAll('[data-outline-section]')[1].querySelector('[data-outline-head] [data-outline-move="down"]').disabled === true);

    rows[1].querySelector('[data-outline-move="up"]').click();
    check('↑ swaps the class with the one above', lessonIds(doc, '11').join(',') === '2,1', lessonIds(doc, '11').join(','));
    check('saving is offered once something moved', save.disabled === false);
    check('the status says how many changes are waiting', /1 change not saved/.test(doc.querySelector('#outline-status').textContent), doc.querySelector('#outline-status').textContent);

    doc.querySelectorAll('[data-outline-section]')[0].querySelector('[data-outline-head] [data-outline-move="down"]').click();
    check('↓ swaps the section with the one below', sectionIds(doc).join(',') === '12,11', sectionIds(doc).join(','));
    check('the status counts both moves', /2 changes not saved/.test(doc.querySelector('#outline-status').textContent), doc.querySelector('#outline-status').textContent);

    reset.click();
    check('undo puts the sections back', sectionIds(doc).join(',') === '11,12', sectionIds(doc).join(','));
    check('undo puts the classes back', lessonIds(doc, '11').join(',') === '1,2', lessonIds(doc, '11').join(','));
    check('undo disables save again', doc.querySelector('[data-outline-save]').disabled === true);
  }

  /* ------------------------------- keyboard ----------------------------- */
  {
    console.log('\nkeyboard');
    const { window, doc } = makeScreen(recordingFetch().impl);
    const handle = doc.querySelectorAll('[data-outline-list][data-folder="11"] [data-outline-handle]')[0];
    const down = new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true });
    handle.dispatchEvent(down);
    check('ArrowDown on a handle moves the class down', lessonIds(doc, '11').join(',') === '2,1', lessonIds(doc, '11').join(','));
    check('focus stays on the row that moved', doc.activeElement && doc.activeElement.closest('[data-lesson]')?.dataset.lesson === '1', doc.activeElement?.tagName);

    const up = new window.KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true, cancelable: true });
    doc.activeElement.dispatchEvent(up);
    check('ArrowUp moves it back', lessonIds(doc, '11').join(',') === '1,2', lessonIds(doc, '11').join(','));
  }

  /* -------------------------------- dragging ---------------------------- */
  {
    console.log('\ndragging');
    const { window, doc } = makeScreen(recordingFetch().impl);
    const point = stubGeometry(window);
    const list12 = doc.querySelector('[data-outline-list][data-folder="12"]');
    const handle = doc.querySelector('[data-lesson="1"] [data-outline-handle]');

    point.node = list12;
    pointer(handle, 'pointerdown', window, { y: 0 });
    // The first few pixels are a click, not a drag; past the threshold the row
    // follows the pointer.
    pointer(handle, 'pointermove', window, { y: 2 });
    pointer(handle, 'pointermove', window, { y: 8 });
    pointer(handle, 'pointermove', window, { y: 4 });
    check('a class dragged into another section lands there', lessonIds(doc, '12').join(',') === '1,3', lessonIds(doc, '12').join(','));
    check('and leaves the section it came from', lessonIds(doc, '11').join(',') === '2', lessonIds(doc, '11').join(','));
    pointer(handle, 'pointerup', window, { y: 4 });
    check('the drop asks for a save', doc.querySelector('[data-outline-save]').disabled === false);
    check('the section menu follows the drop', doc.querySelector('[data-lesson="1"] [data-outline-pick]').value === '12');
    check('the drop is announced', /Moved/.test(doc.querySelector('#outline-status').textContent), doc.querySelector('#outline-status').textContent.slice(0, 60));

    // Sections drag within their own list, not into a class list.
    const secondSection = doc.querySelectorAll('[data-outline-section]')[1];
    const sectionHandle = secondSection.querySelector('[data-outline-head] [data-outline-handle]');
    point.node = doc.querySelector('[data-outline-list][data-folder="11"]');
    pointer(sectionHandle, 'pointerdown', window, { y: 0 });
    pointer(sectionHandle, 'pointermove', window, { y: 10 });
    pointer(sectionHandle, 'pointerup', window, { y: 10 });
    check('a dragged section changes the section order', sectionIds(doc).join(',') === '12,11', sectionIds(doc).join(','));
    check('sections did not leak into a class list', doc.querySelectorAll('[data-outline-list] [data-outline-section]').length === 0);
  }

  /* ------------------------------ section menu -------------------------- */
  {
    console.log('\nsection menu');
    const { window, doc } = makeScreen(recordingFetch().impl);
    const pick = doc.querySelector('[data-lesson="1"] [data-outline-pick]');
    pick.value = '12';
    pick.dispatchEvent(new window.Event('change', { bubbles: true }));
    check('a class moves to the chosen section', lessonIds(doc, '12').join(',') === '3,1', lessonIds(doc, '12').join(','));
    check('and leaves the old one', lessonIds(doc, '11').join(',') === '2', lessonIds(doc, '11').join(','));
    check('the menu agrees with where it is now', pick.value === '12');
    check('moving a class offers a save', doc.querySelector('[data-outline-save]').disabled === false);
  }

  /* -------------------------------- saving ------------------------------ */
  {
    console.log('\nsaving');
    const fetchStub = recordingFetch(200, { ok: true, message: 'Saved — 2 sections and 3 classes, in this order.', revision: 'rev-2' });
    const { window, doc } = makeScreen(fetchStub.impl);
    doc.querySelectorAll('[data-outline-list][data-folder="11"] [data-outline-move="up"]')[1].click();
    doc.querySelector('[data-outline]').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await tick();
    await tick();

    const call = fetchStub.calls[0];
    check('a save posts to the outline URL', call && call.url === '/admin/courses/course/1/outline/', call?.url);
    check('it sends the revision the page was built from', call?.payload.revision === 'rev-1', call?.payload.revision);
    check('it sends the CSRF token', call?.init.headers['X-CSRFToken'] === 'csrf-token');
    check('it sends every section in order', JSON.stringify(call?.payload.sections.map((s) => s.folder)) === '[11,12]', JSON.stringify(call?.payload.sections.map((s) => s.folder)));
    check('it sends every class in its new order', JSON.stringify(call?.payload.sections[0].lessons) === '[2,1]', JSON.stringify(call?.payload.sections[0].lessons));
    check('the page shows the server\'s answer', /Saved/.test(doc.querySelector('#outline-status').textContent), doc.querySelector('#outline-status').textContent);
    check('a saved order disables Save again', doc.querySelector('[data-outline-save]').disabled === true);
    check('the revision advances for the next save', doc.querySelector('[data-outline]').dataset.revision === 'rev-2');
  }

  /* ------------------------------- conflict ----------------------------- */
  {
    console.log('\nconflict');
    const fetchStub = recordingFetch(409, {
      error: 'conflict',
      message: 'Someone else changed this outline while you were arranging it. Reload the page to see their order before saving yours.'
    });
    const { window, doc } = makeScreen(fetchStub.impl);
    doc.querySelectorAll('[data-outline-list][data-folder="11"] [data-outline-move="up"]')[1].click();
    doc.querySelector('[data-outline]').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await tick();
    await tick();

    const status = doc.querySelector('#outline-status');
    check('a 409 is shown, not swallowed', /Someone else changed this outline/.test(status.textContent), status.textContent.slice(0, 60));
    check('it offers a way to see the current order', Boolean(status.querySelector('a[href]')));
    check('the order stays on screen, still saveable', doc.querySelector('[data-outline-save]').disabled === false);
    check('the status is marked as an error', status.classList.contains('is-error'));
  }

  /* --------------------------- nothing to save -------------------------- */
  {
    console.log('\nno changes');
    const fetchStub = recordingFetch(200, { ok: true });
    const { window, doc } = makeScreen(fetchStub.impl);
    doc.querySelector('[data-outline]').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    await tick();
    check('submitting an unchanged outline still posts what is on screen', fetchStub.calls.length === 1, String(fetchStub.calls.length));
  }

  const ok = finish('outline checks');
  process.exit(ok ? 0 : 1);
})();
