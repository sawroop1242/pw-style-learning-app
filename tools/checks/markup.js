/**
 * Markup checks: the HTML and CSS defects a browser hides.
 *
 * `check.js` boots every page and asks whether it *renders*; this file asks
 * whether the documents are well formed in the first place. The two are
 * different failures, and the second kind is the one that reaches production
 * quietly:
 *
 *   • a **tag that does not parse** — a stray comma after an attribute, an
 *     unclosed element, a duplicated attribute. The browser recovers, so the
 *     page "works", but the attribute after the mistake is dropped.
 *   • a **file that is not there** — a favicon or a stylesheet pointed at a
 *     path that does not exist. The page loads; one request 404s on every
 *     visit.
 *   • a **custom property that was never defined** — `var(--surface-1)` where
 *     the token is `--surface-raised`: no error anywhere, the declaration is
 *     simply dropped and the element paints without its background.
 *   • a **broken reference between elements** — `aria-controls` / `label[for]`
 *     naming an id that does not exist, or an id that occurs twice. Screen
 *     readers follow those references and land nowhere.
 *
 * Every check below is deterministic and needs no server: it reads the files
 * the browser would read. `live.js` proves the same pages against the API.
 */
const fs = require('fs');
const path = require('path');
const parse5 = require('parse5');
const csstree = require('css-tree');
const { JSDOM } = require('jsdom');
const { ROOT } = require('./harness');

const CSS_DIR = path.join(ROOT, 'assets/css');
const pages = fs.readdirSync(ROOT).filter((f) => f.endsWith('.html')).sort();
const sheets = fs.readdirSync(CSS_DIR).filter((f) => f.endsWith('.css')).sort();

let failures = 0;
let checks = 0;

/** One run of a rule over every page; `problems` is `[page, message]` pairs. */
function rule(name, run) {
  checks += 1;
  const problems = [];
  for (const page of pages) {
    const html = fs.readFileSync(path.join(ROOT, page), 'utf8');
    const doc = new JSDOM(html, { url: `https://studyspace.example/${page}` }).window.document;
    run(page, html, doc, problems);
  }
  if (problems.length) {
    failures += problems.length;
    console.log(`✗ ${name} — ${problems.length}`);
    for (const [page, message] of problems.slice(0, 12)) console.log(`    ${page}: ${message}`);
    if (problems.length > 12) console.log(`    … ${problems.length - 12} more`);
  } else {
    console.log(`✓ ${name}`);
  }
}

/* ------------------------------- parsing -------------------------------- */

// Errors a browser silently repairs and a template cannot avoid; everything
// else is a real defect in the source.
const IGNORED_PARSE_ERRORS = new Set([
  'missing-doctype',
  'non-void-html-element-start-tag-with-trailing-solidus',
  'non-conforming-doctype'
]);

rule('every page parses without a recoverable error', (page, html, doc, problems) => {
  const errors = [];
  parse5.parse(html, { onParseError: (error) => errors.push(error) });
  for (const error of errors) {
    if (IGNORED_PARSE_ERRORS.has(error.code)) continue;
    problems.push([page, `${error.code} at line ${error.startLine}, column ${error.startCol}`]);
  }
});

/* ------------------------------ references ------------------------------- */

/** Files a page points at that the browser would fetch. */
function localRefs(doc) {
  const refs = [];
  const push = (value, what) => {
    if (!value) return;
    if (/^(?:[a-z]+:|\/\/|#|data:|mailto:|tel:)/i.test(value)) return;
    refs.push([value.split(/[?#]/)[0], what]);
  };
  doc.querySelectorAll('link[href]').forEach((el) => push(el.getAttribute('href'), `<link rel="${el.rel}">`));
  doc.querySelectorAll('script[src]').forEach((el) => push(el.getAttribute('src'), '<script src>'));
  doc.querySelectorAll('img[src]').forEach((el) => push(el.getAttribute('src'), `<img src>`));
  doc.querySelectorAll('a[href]').forEach((el) => push(el.getAttribute('href'), '<a href>'));
  return refs;
}

rule('every file a page points at exists', (page, html, doc, problems) => {
  for (const [ref, what] of localRefs(doc)) {
    if (!ref) continue;
    if (!fs.existsSync(path.join(ROOT, ref))) problems.push([page, `${what} → ${ref} (404)`]);
  }
});

// The shell list is one document, not one per page, so it is checked once.
checks += 1;
{
  const shell = listShellEntries();
  const missing = shell.filter((entry) => !fs.existsSync(path.join(ROOT, entry)));
  if (missing.length) {
    failures += missing.length;
    console.log(`✗ every file the service worker precaches exists — ${missing.length}`);
    missing.forEach((entry) => console.log(`    sw.js: ${entry} (404)`));
  } else {
    console.log(`✓ every file the service worker precaches exists (${shell.length} entries)`);
  }
}

/** Every file the service worker precaches, as paths relative to `frontend/`. */
function listShellEntries() {
  const source = fs.readFileSync(path.join(ROOT, 'sw.js'), 'utf8');
  return [...source.matchAll(/'\.\/([^']+)'/g)]
    .map((match) => match[1])
    .filter((entry) => entry && !entry.includes('${'));
}

/* --------------------------------- CSS ---------------------------------- */

// One pass over every stylesheet: what it defines, what it uses.
const definedVars = new Map();
const usedVars = [];
for (const sheet of sheets) {
  const source = fs.readFileSync(path.join(CSS_DIR, sheet), 'utf8');
  let ast;
  try {
    ast = csstree.parse(source, { positions: true });
  } catch (error) {
    failures += 1;
    console.log(`✗ ${sheet} does not parse — ${error.message}`);
    continue;
  }
  csstree.walk(ast, {
    visit: 'Declaration',
    enter(node) {
      const property = node.property.toLowerCase();
      const value = csstree.generate(node.value);
      if (property.startsWith('--')) {
        if (!definedVars.has(property)) definedVars.set(property, sheet);
        return;
      }
      for (const match of value.matchAll(/var\(\s*(--[\w-]+)/g)) {
        usedVars.push([match[1], sheet, node.loc?.start.line ?? 0]);
      }
    }
  });
}

checks += 1;
{
  const missing = usedVars.filter(([name]) => !definedVars.has(name));
  if (missing.length) {
    failures += missing.length;
    console.log(`✗ every CSS custom property is defined — ${missing.length}`);
    for (const [name, sheet, line] of missing.slice(0, 12)) {
      console.log(`    ${sheet}:${line} uses ${name}, which no stylesheet defines`);
    }
  } else {
    console.log(`✓ every CSS custom property is defined (${definedVars.size} tokens, ${usedVars.length} uses)`);
  }
}

const styledClasses = new Set();
for (const sheet of sheets) {
  const source = fs.readFileSync(path.join(CSS_DIR, sheet), 'utf8');
  for (const match of source.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)) styledClasses.add(match[1]);
}

rule('every class the markup uses is styled somewhere', (page, html, doc, problems) => {
  for (const el of doc.querySelectorAll('[class]')) {
    for (const name of el.getAttribute('class').split(/\s+/)) {
      if (name && !styledClasses.has(name)) problems.push([page, `class "${name}" has no rule in any stylesheet`]);
    }
  }
});

/* ----------------------------- structure -------------------------------- */

rule('no id appears twice', (page, html, doc, problems) => {
  const seen = new Map();
  for (const el of doc.querySelectorAll('[id]')) seen.set(el.id, (seen.get(el.id) || 0) + 1);
  for (const [id, count] of seen) if (count > 1) problems.push([page, `#${id} appears ${count} times`]);
});

rule('every aria reference points at an element', (page, html, doc, problems) => {
  for (const attr of ['aria-controls', 'aria-labelledby', 'aria-describedby', 'aria-owns']) {
    for (const el of doc.querySelectorAll(`[${attr}]`)) {
      for (const id of el.getAttribute(attr).split(/\s+/).filter(Boolean)) {
        if (!doc.getElementById(id)) problems.push([page, `${attr}="${id}" on <${el.tagName.toLowerCase()}> names nothing`]);
      }
    }
  }
});

rule('every label points at a control', (page, html, doc, problems) => {
  for (const label of doc.querySelectorAll('label[for]')) {
    const target = doc.getElementById(label.getAttribute('for'));
    if (!target) problems.push([page, `label for="${label.getAttribute('for')}" names nothing`]);
  }
});

rule('every button and input states its type', (page, html, doc, problems) => {
  // `<button>` inside a form defaults to submit, which is how a "cancel" ends
  // up posting the form; `<input>` defaults to text, which turns a numeric
  // field into a keyboard trap on a phone.
  for (const button of doc.querySelectorAll('button:not([type])')) {
    const inForm = Boolean(button.closest('form'));
    problems.push([page, `<button${inForm ? ' (inside a form)' : ''}> "${button.textContent.trim().slice(0, 24)}" has no type`]);
  }
  for (const input of doc.querySelectorAll('input:not([type])')) {
    problems.push([page, `<input name="${input.name || input.id || '?'}"> has no type`]);
  }
});

rule('every image has an alt attribute', (page, html, doc, problems) => {
  for (const img of doc.querySelectorAll('img:not([alt])')) {
    problems.push([page, `<img src="${img.getAttribute('src')}"> has no alt`]);
  }
});

rule('every heading has a name', (page, html, doc, problems) => {
  for (const heading of doc.querySelectorAll('h1, h2')) {
    const text = (heading.textContent || '').replace(/\s+/g, ' ').trim();
    if (!text) problems.push([page, `<${heading.tagName.toLowerCase()}> is empty`]);
  }
});

rule('only one main landmark is visible', (page, html, doc, problems) => {
  // A file that swaps whole views (the exam window) may hold several `main`
  // elements, but only one may be visible at a time.
  const visible = [...doc.querySelectorAll('main')].filter((el) => !el.closest('[hidden]'));
  if (visible.length > 1) problems.push([page, `${visible.length} <main> elements are visible at once`]);
});

rule('no dead links in the markup', (page, html, doc, problems) => {
  for (const link of doc.querySelectorAll('a[href="#"], a[href=""]')) {
    // Runtime fillers are allowed only when the script is expected to give the
    // link a destination; say so in the markup with `data-placeholder`.
    if (link.hasAttribute('data-placeholder')) continue;
    problems.push([page, `<a href="#"> "${link.textContent.trim().slice(0, 30)}" has no destination`]);
  }
});

/* -------------------------------- report -------------------------------- */

console.log(`\n${checks} checks across ${pages.length} pages and ${sheets.length} stylesheets`);
console.log(failures === 0 ? 'MARKUP OK' : `${failures} markup problem(s)`);
process.exit(failures === 0 ? 0 : 1);
