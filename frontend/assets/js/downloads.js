/** Downloads — lectures, notes and tests saved for offline study. */

import { $, $$, esc, toast } from './core.js';
import { mountChrome, icon } from './ui.js';
import { DOWNLOADS } from './data.js';

mountChrome('downloads');

const KIND_ICON = { video: 'play', pdf: 'note', test: 'file-text' };
const KIND_CTA = { video: 'Open', pdf: 'Open', test: 'Start' };

function rows(items) {
  return items
    .map(
      (item) => `
      <div class="dl-row">
        <span class="dl-thumb">${icon(KIND_ICON[item.kind] || 'download')}</span>
        <span class="dl-main">
          <strong>${esc(item.title)}</strong>
          <small>${esc(item.meta)}</small>
        </span>
        <button class="dl-action" type="button" aria-label="${KIND_CTA[item.kind] || 'Open'} ${esc(item.title)}"
                data-open="${esc(item.title)}" data-kind="${esc(item.kind)}">
          ${icon(item.kind === 'test' ? 'play' : 'download')}
        </button>
      </div>`
    )
    .join('');
}

function render() {
  $('#list-lectures').innerHTML = rows(DOWNLOADS.lectures);
  $('#list-notes').innerHTML = rows(DOWNLOADS.notes);
  $('#list-tests').innerHTML = rows(DOWNLOADS.tests);
}

const tabs = $$('.tabs .tab');
function selectTab(index) {
  tabs.forEach((tab, i) => {
    const selected = i === index;
    tab.setAttribute('aria-selected', String(selected));
    const panel = document.getElementById(tab.getAttribute('aria-controls'));
    if (panel) panel.hidden = !selected;
  });
}
tabs.forEach((tab, i) => {
  tab.addEventListener('click', () => selectTab(i));
  tab.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const next = (i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    selectTab(next);
  });
});

document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-open]');
  if (!btn) return;
  const { open, kind } = btn.dataset;
  if (kind === 'test') {
    location.href = 'test-player.html?test=1';
    return;
  }
  toast(`“${open}” opens inside the class player once it is saved on this device.`, 'info', 4500);
});

render();
