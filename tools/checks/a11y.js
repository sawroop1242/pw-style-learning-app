/**
 * Structural accessibility sweep over every page.
 *
 * This is not a substitute for axe: it checks the failures that come from
 * hand-written markup — missing h1, unlabelled controls, a control with no
 * accessible name, `aria-controls` pointing at nothing, duplicate ids, images
 * without alt text.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');
const { ROOT } = require('./harness');

const pages = fs.readdirSync(ROOT).filter((f) => f.endsWith('.html')).sort();
let bad = 0;

for (const page of pages) {
  const dom = new JSDOM(fs.readFileSync(path.join(ROOT, page), 'utf8'));
  const doc = dom.window.document;
  const issues = [];

  const h1 = doc.querySelectorAll('h1').length;
  if (h1 !== 1) issues.push(`h1 count ${h1}`);
  if (!doc.querySelector('main')) issues.push('no main');

  for (const img of doc.querySelectorAll('img')) {
    if (!img.hasAttribute('alt')) issues.push(`img without alt: ${img.getAttribute('src')}`);
  }

  for (const el of doc.querySelectorAll('[aria-controls]')) {
    const id = el.getAttribute('aria-controls');
    if (!doc.getElementById(id)) issues.push(`aria-controls -> missing #${id}`);
  }

  for (const el of doc.querySelectorAll('input, select, textarea')) {
    const id = el.getAttribute('id');
    const labelled =
      el.getAttribute('aria-label') ||
      el.closest('label') ||
      (id && doc.querySelector(`label[for="${id}"]`));
    if (!labelled && el.type !== 'hidden') issues.push(`unlabelled ${el.tagName.toLowerCase()}${id ? '#' + id : ''}`);
  }

  for (const btn of doc.querySelectorAll('button')) {
    const text = (btn.textContent || '').trim();
    if (!text && !btn.getAttribute('aria-label')) issues.push('button without accessible name');
  }

  for (const a of doc.querySelectorAll('a')) {
    const text = (a.textContent || '').trim();
    if (!text && !a.getAttribute('aria-label')) issues.push(`link without name: ${a.getAttribute('href')}`);
  }

  const ids = new Set();
  for (const el of doc.querySelectorAll('[id]')) {
    if (ids.has(el.id)) issues.push(`duplicate id #${el.id}`);
    ids.add(el.id);
  }

  if (issues.length) {
    bad += 1;
    console.log(`✗ ${page}`);
    issues.forEach((i) => console.log('   -', i));
  } else {
    console.log(`✓ ${page}`);
  }
}

console.log(bad ? `\n${bad} page(s) with issues` : '\nno structural accessibility problems');
process.exit(bad ? 1 : 0);
