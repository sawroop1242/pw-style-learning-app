/**
 * Stylesheet checks: every sheet parses, and every class the markup uses exists
 * somewhere in the CSS.
 *
 * `MISSING` output is a defect unless it is a dynamic prefix — a class built as
 * `avatar-${tone}` or `toast-${type}` shows up as a bare prefix like `avatar-`.
 */
const fs = require('fs');
const path = require('path');
const csstree = require('css-tree');
const { ROOT } = require('./harness');

const CSS_DIR = path.join(ROOT, 'assets/css');
const JS_DIR = path.join(ROOT, 'assets/js');

let failures = 0;

/* ------------------------- parse every stylesheet ------------------------ */
const defined = new Set();
for (const file of fs.readdirSync(CSS_DIR).filter((f) => f.endsWith('.css'))) {
  const source = fs.readFileSync(path.join(CSS_DIR, file), 'utf8');
  try {
    const ast = csstree.parse(source, { positions: true });
    csstree.walk(ast, {
      visit: 'ClassSelector',
      enter(node) {
        defined.add(node.name);
      }
    });
    console.log(`✓ ${file}`);
  } catch (err) {
    failures += 1;
    console.log(`✗ ${file} — ${err.message}`);
  }
}

/* ------------------------- collect used classes -------------------------- */
const used = new Map();
const add = (name, origin) => {
  if (!used.has(name)) used.set(name, new Set());
  used.get(name).add(origin);
};

const htmlFiles = fs.readdirSync(ROOT).filter((f) => f.endsWith('.html'));
for (const file of htmlFiles) {
  const html = fs.readFileSync(path.join(ROOT, file), 'utf8');
  for (const m of html.matchAll(/class="([^"]*)"/g)) {
    for (const name of m[1].split(/\s+/)) if (name) add(name, file);
  }
}

for (const file of fs.readdirSync(JS_DIR).filter((f) => f.endsWith('.js'))) {
  const js = fs.readFileSync(path.join(JS_DIR, file), 'utf8');
  for (const m of js.matchAll(/class="([^"$]*)"/g)) {
    for (const name of m[1].split(/\s+/)) if (name) add(name, file);
  }
  for (const m of js.matchAll(/classList\.(?:add|remove|toggle)\('([\w-]+)'/g)) add(m[1], file);
}

/* ------------------------------ report ---------------------------------- */
const missing = [...used.entries()].filter(([name]) => !defined.has(name));

console.log(`\n${used.size} classes used, ${defined.size} defined`);
if (missing.length) {
  console.log(`${missing.length} missing from CSS:`);
  for (const [name, origins] of missing) {
    console.log(`  ${name}  [${[...origins].join(', ')}]`);
    // A trailing dash means the class is assembled at runtime.
    if (!name.endsWith('-')) failures += 1;
  }
}

console.log(failures === 0 ? '\nCSS OK' : `\n${failures} CSS problem(s)`);
process.exit(failures === 0 ? 0 : 1);
