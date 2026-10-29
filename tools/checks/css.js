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

/* ------------------------------------------------------------------ */
/* Cascade order                                                       */
/* ------------------------------------------------------------------ */

/*
 * A mobile override placed *before* the base rule loses to it at equal
 * specificity. That is not hypothetical: `.tab { white-space: nowrap }` came
 * after the 640px block, so tab labels stayed on one line and were clipped
 * inside their own button — "Announcements" rendered as "Announcemen/ts".
 *
 * The rule: inside one file, a selector declared in a @media block must not be
 * re-declared outside any media block at a later position.
 */
console.log('\nCascade order');
{
  const cssDir = path.resolve(__dirname, '../../frontend/assets/css');
  let problems = 0;

  for (const file of fs.readdirSync(cssDir).filter((f) => f.endsWith('.css')).sort()) {
    const css = fs.readFileSync(path.join(cssDir, file), 'utf8');
    const media = []; // [start, end]
    const mediaRe = /@media[^{]*\{/g;
    let m;
    while ((m = mediaRe.exec(css))) {
      let depth = 1;
      let i = mediaRe.lastIndex;
      while (i < css.length && depth > 0) {
        if (css[i] === '{') depth += 1;
        else if (css[i] === '}') depth -= 1;
        i += 1;
      }
      media.push([m.index, i]);
      mediaRe.lastIndex = i;
    }
    const inMedia = (pos) => media.some(([a, b]) => pos >= a && pos < b);

    const plain = new Map(); // selector -> last declaration position
    const guarded = new Map(); // selector -> earliest position inside @media
    const ruleRe = /([^{}@]+)\{/g;
    while ((m = ruleRe.exec(css))) {
      const pos = m.index;
      for (const sel of m[1].split(',').map((s) => s.trim()).filter(Boolean)) {
        if (inMedia(pos)) {
          if (!guarded.has(sel) || guarded.get(sel) > pos) guarded.set(sel, pos);
        } else {
          plain.set(sel, pos);
        }
      }
    }

    const bad = [...guarded.entries()]
      .filter(([sel, at]) => plain.has(sel) && plain.get(sel) > at)
      .map(([sel]) => sel);

    if (bad.length) {
      problems += bad.length;
      console.log(`  ✗ ${file}: ${bad.join(', ')} — a later plain rule overrides the mobile block`);
    } else {
      console.log(`  ✓ ${file}`);
    }
  }

  if (problems) {
    failures += problems;
    console.log(`\n${problems} mobile override(s) lose the cascade.`);
  }
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
