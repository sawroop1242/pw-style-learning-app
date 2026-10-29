/**
 * Shared boot helper for the StudySpace DOM checks.
 *
 * The front end is plain ES modules with no build step. jsdom cannot execute
 * `<script type="module">` from disk, so each module is rewritten in memory:
 * `export` becomes a plain declaration and `import` reads from a module table.
 * Nothing here ships to the browser.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.resolve(__dirname, '../../frontend');

function transform(src, name) {
  const exported = new Map();
  let out = src;

  out = out.replace(/^export\s+((?:async\s+)?(?:const|let|var|function\*?|class))\s+([A-Za-z0-9_$]+)/gm, (m, kw, id) => {
    exported.set(id, id);
    return `${kw} ${id}`;
  });
  out = out.replace(/^export\s*\{([^}]*)\}\s*;?/gm, (m, list) => {
    const assigns = [];
    for (const part of list.split(',')) {
      const bits = part.trim().split(/\s+as\s+/);
      if (!bits[0]) continue;
      exported.set(bits[0], bits[1] || bits[0]);
      if (bits[1] && bits[1] !== bits[0]) assigns.push(`const ${bits[1]} = ${bits[0]};`);
    }
    return assigns.join('\n');
  });
  out = out.replace(/import\s*\{([^}]*)\}\s*from\s*'\.\/([\w.-]+)'\s*;?/g, (m, list, file) => {
    const spec = list
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean)
      .map((p) => p.replace(/\s+as\s+/, ': '))
      .join(', ');
    return `const { ${spec} } = __modules['${file.replace(/\.js$/, '')}'];`;
  });
  out = out.replace(/import\.meta\.url/g, `'https://studyspace.example/assets/js/${name}.js'`);

  const ret = [...exported.entries()].map(([local, alias]) => (alias === local ? `${local}` : `${alias}: ${local}`));
  return `__modules['${name}'] = (function(){\n'use strict';\n${out}\nreturn { ${ret.join(', ')} };\n})();`;
}

/**
 * @param {string} page  file name in frontend/, e.g. 'index.html'
 * @param {string[]} mods modules to load, in dependency order
 * @param {object} opts
 *   query    — search string appended to the document URL
 *   fetcher  — (url, init) => Promise<Response>; omitted means the network is
 *              unreachable, which is how the fixture fallback is exercised
 *   fullscreen — jsdom has no Fullscreen API at all, so a check that wants to
 *              press the stage's full-screen button has to say so; this installs
 *              the two methods and the two properties the page touches
 */
async function boot(page, mods, { query = '', fetcher = null, seedStorage = null, fullscreen = false } = {}) {
  const html = fs.readFileSync(path.join(ROOT, page), 'utf8');
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => {
    const msg = e.detail?.message || e.message || String(e);
    if (/Not implemented: navigation/i.test(msg)) return;
    errors.push('jsdomError: ' + msg);
  });

  const dom = new JSDOM(html, {
    url: `https://studyspace.example/${page}${query}`,
    runScripts: 'outside-only',
    pretendToBeVisual: true,
    virtualConsole: vc
  });
  const { window } = dom;

  // Some pages only render account data when a session exists; seed it before
  // any module runs so the boot path is the same as a returning visitor.
  if (seedStorage) {
    for (const [key, value] of Object.entries(seedStorage)) window.localStorage.setItem(key, value);
  }

  window.fetch = fetcher
    ? (input, init = {}) => {
        // jsdom's AbortSignal hangs Node's fetch; drop it and keep the rest.
        const { signal, ...rest } = init;
        const url = typeof input === 'string' ? input : input.url;
        return fetcher(url, rest);
      }
    : () => Promise.reject(new TypeError('Failed to fetch'));

  if (fullscreen) {
    // jsdom implements none of this; mimic only what player.js touches.
    Object.defineProperty(window.document, 'fullscreenEnabled', { value: true, configurable: true });
    Object.defineProperty(window.document, 'fullscreenElement', { value: null, writable: true, configurable: true });
    window.Element.prototype.requestFullscreen = function requestFullscreen() {
      window.__fullscreenElement = this;
      window.document.fullscreenElement = this;
      window.document.dispatchEvent(new window.Event('fullscreenchange'));
      return Promise.resolve();
    };
    window.document.exitFullscreen = function exitFullscreen() {
      window.__fullscreenElement = null;
      window.document.fullscreenElement = null;
      window.document.dispatchEvent(new window.Event('fullscreenchange'));
      return Promise.resolve();
    };
  }

  window.matchMedia = (q) => ({
    matches: false, media: q, addListener() {}, removeListener() {},
    addEventListener() {}, removeEventListener() {}, dispatchEvent() {}
  });
  window.scrollTo = () => {};
  window.Element.prototype.scrollIntoView = () => {};
  window.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
  Object.defineProperty(window.navigator, 'serviceWorker', {
    value: {
      register: () => Promise.resolve({ update: () => Promise.resolve(), addEventListener: () => {} }),
      ready: Promise.resolve({}), controller: null, addEventListener: () => {}
    },
    configurable: true
  });
  window.addEventListener('error', (e) => errors.push('window error: ' + (e.error?.stack || e.message)));
  window.addEventListener('unhandledrejection', (e) => errors.push('unhandled rejection: ' + (e.reason?.stack || e.reason)));

  const src =
    'var __modules = {};\n' +
    mods.map((m) => transform(fs.readFileSync(path.join(ROOT, 'assets/js', m + '.js'), 'utf8'), m)).join('\n');
  window.eval(src);
  await new Promise((r) => setTimeout(r, 700));
  return { window, errors, doc: window.document };
}

const click = (w, el) => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true, view: w }));
const key = (w, el, k) => el.dispatchEvent(new w.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));
const type = (w, el, value) => {
  el.value = value;
  el.dispatchEvent(new w.Event('input', { bubbles: true }));
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function reporter() {
  const results = [];
  return {
    results,
    check(name, ok, detail = '') {
      results.push({ name, ok: Boolean(ok) });
      console.log(`${ok ? '  ✓' : '  ✗'} ${name}${detail ? '  — ' + detail : ''}`);
      return Boolean(ok);
    },
    finish(label) {
      const failed = results.filter((r) => !r.ok);
      console.log(`\n${results.length - failed.length}/${results.length} ${label} passed`);
      return failed.length === 0;
    }
  };
}

module.exports = { ROOT, boot, click, key, type, wait, reporter, transform };
