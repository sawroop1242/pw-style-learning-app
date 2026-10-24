/**
 * StudySpace UI — icon set, chrome (header / tabbar / footer) and the shared
 * component builders used across pages.
 */

import {
  $, $$, esc, money, compact, discountPercent, shortDate, countdown,
  initials, isSignedIn, isPreview, storage
} from './core.js';

/* ------------------------------------------------------------------ */
/* Icons                                                              */
/* ------------------------------------------------------------------ */

const ICONS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.4-3.4"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  bell: '<path d="M18 9a6 6 0 1 0-12 0c0 5-2 6-2 6h16s-2-1-2-6"/><path d="M10.5 20a2 2 0 0 0 3 0"/>',
  user: '<circle cx="12" cy="8" r="3.6"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H19v3H6.5"/>',
  'book-open': '<path d="M12 6.5C10.5 5 8 4.5 4.5 4.5v13c3.5 0 6 .5 7.5 2 1.5-1.5 4-2 7.5-2v-13C16 4.5 13.5 5 12 6.5z"/><path d="M12 6.5v13"/>',
  cap: '<path d="m3 9 9-4 9 4-9 4z"/><path d="M7 11v4.5c0 1.4 2.2 2.5 5 2.5s5-1.1 5-2.5V11"/>',
  atom: '<circle cx="12" cy="12" r="2"/><ellipse cx="12" cy="12" rx="9.5" ry="4"/><ellipse cx="12" cy="12" rx="9.5" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="9.5" ry="4" transform="rotate(120 12 12)"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-9.3A4.2 4.2 0 0 1 12 8a4.2 4.2 0 0 1 7.5 2.7C19.5 15.4 12 20 12 20z"/>',
  shield: '<path d="M12 3.5 5 6.2v5.4c0 4.2 2.9 7.6 7 8.9 4.1-1.3 7-4.7 7-8.9V6.2z"/>',
  'shield-check': '<path d="M12 3.5 5 6.2v5.4c0 4.2 2.9 7.6 7 8.9 4.1-1.3 7-4.7 7-8.9V6.2z"/><path d="m9 11.8 2.2 2.2 4-4"/>',
  brief: '<rect x="3" y="7.5" width="18" height="12" rx="2.2"/><path d="M9 7.5V5.8A1.8 1.8 0 0 1 10.8 4h2.4A1.8 1.8 0 0 1 15 5.8v1.7"/><path d="M3 13h18"/>',
  cpu: '<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M10 3v3M14 3v3M10 18v3M14 18v3M3 10h3M3 14h3M18 10h3M18 14h3"/>',
  building: '<path d="M4 21V6.5L12 3l8 3.5V21"/><path d="M9 21v-5h6v5"/><path d="M8.5 9h2M13.5 9h2M8.5 12.5h2M13.5 12.5h2"/>',
  'arrow-right': '<path d="M5 12h13M13 6.5l5.5 5.5-5.5 5.5"/>',
  'arrow-left': '<path d="M19 12H6M11 6.5 5.5 12l5.5 5.5"/>',
  'chevron-down': '<path d="m6 9.5 6 6 6-6"/>',
  'chevron-right': '<path d="m9.5 6 6 6-6 6"/>',
  'chevron-left': '<path d="m14.5 6-6 6 6 6"/>',
  play: '<path d="M8 5.5v13l11-6.5z"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  users: '<circle cx="9" cy="8.5" r="3.2"/><path d="M3 19a6 6 0 0 1 12 0"/><path d="M16 5.8a3.2 3.2 0 0 1 0 6.2"/><path d="M18 19a6 6 0 0 0-2-4.4"/>',
  star: '<path d="m12 4 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 9.7l5.4-.8z" fill="currentColor" stroke="none"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7"/>',
  'check-circle': '<circle cx="12" cy="12" r="8.5"/><path d="m8.5 12.3 2.4 2.4 4.6-4.7"/>',
  'x-circle': '<circle cx="12" cy="12" r="8.5"/><path d="m9.5 9.5 5 5M14.5 9.5l-5 5"/>',
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
  unlock: '<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 6.8-1.2"/>',
  download: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5"/><path d="M4.5 19.5h15"/>',
  smartphone: '<rect x="6.5" y="2.5" width="11" height="19" rx="2.6"/><path d="M10.5 18.5h3"/>',
  apple: '<path d="M15.5 3.5c.2 1.5-.5 2.8-1.3 3.7-.9 1-2.1 1.6-3.3 1.5-.2-1.4.5-2.8 1.3-3.7.9-.9 2.3-1.5 3.3-1.5z"/><path d="M18.5 16.6c-.6 1.4-1 2-1.8 3.2-1.1 1.6-2.7 3.6-4.6 3.6-1.7 0-2.2-1.1-4.5-1.1s-2.8 1.1-4.5 1.1c-1.9 0-3.4-1.8-4.5-3.4C-2.6 16-3 10.2-.6 7.7 1.2 5.9 3.4 5.2 5.4 5.2c1.9 0 3.1 1.1 4.7 1.1 1.5 0 2.5-1.1 4.7-1.1 1.8 0 3.7.6 4.8 2-2.9 1.7-2.3 5.9 1 8.4z" transform="scale(.92) translate(1.5 -1.2)"/>',
  playstore: '<path d="M4.5 3.2 15 12 4.5 20.8c-.3-.2-.5-.6-.5-1V4.2c0-.4.2-.8.5-1z"/><path d="m15 12 3.4 3.4 2.4-1.4c.6-.4.6-1.6 0-2L18.4 10.6z"/><path d="M4.5 3.2 18.4 10.6M4.5 20.8 18.4 13.4"/>',
  flame: '<path d="M12 21c3.6 0 6-2.4 6-5.5 0-4-3.5-5.6-3.5-9.5 0-1-.4-2-1.2-3 0 3.2-2.3 4.2-3.6 6.2-.9 1.4-1.2 2.7-1.2 4 0 .8-.5 1.3-1.1 1.3S6.4 14 6.4 13c-.6 1-1 2.1-1 3.4C5.4 18.6 8.4 21 12 21z"/>',
  chart: '<path d="M4 20V4"/><path d="M4 20h16"/><rect x="7.5" y="12" width="3" height="5" rx="1"/><rect x="12.5" y="8.5" width="3" height="8.5" rx="1"/><rect x="17.5" y="5.5" width="3" height="11.5" rx="1" transform="translate(-1)"/>',
  note: '<path d="M6 3.5h8l4.5 4.5v12.5H6z"/><path d="M14 3.5V8h4.5"/><path d="M9 12h6M9 15.5h6"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="16" rx="2.4"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  trophy: '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 5.5H5.5V7A2.5 2.5 0 0 0 8 9.5M16 5.5h2.5V7A2.5 2.5 0 0 1 16 9.5"/><path d="M12 13v3.5M9 20h6M10 16.5h4"/>',
  target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
  'wifi-off': '<path d="m3 4 18 18"/><path d="M9.5 17.5a3.5 3.5 0 0 1 5 0"/><path d="M6.5 14.2a8 8 0 0 1 3-1.7"/><path d="M17.8 15.4a8 8 0 0 0-3-2.1"/><path d="M3.5 10.4A13 13 0 0 1 8 8.1"/><path d="M16 8.1a13 13 0 0 1 4.5 2.3"/>',
  alert: '<path d="M12 4.5 3 20h18z"/><path d="M12 10v4.5M12 17.4v.1"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11.5v5M12 8v.1"/>',
  eye: '<path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
  'eye-off': '<path d="m3 4 18 18"/><path d="M10 6.8A9.7 9.7 0 0 1 12 6.5c6 0 9.5 5.5 9.5 5.5a17 17 0 0 1-3.3 3.7"/><path d="M6.3 8.3A17.4 17.4 0 0 0 2.5 12S6 17.5 12 17.5a9.5 9.5 0 0 0 3.6-.7"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  logout: '<path d="M15 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2.5"/><path d="M10 12h11M17.5 8.5 21 12l-3.5 3.5"/>',
  settings: '<circle cx="12" cy="12" r="3.2"/><path d="M19.4 14.8a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.2a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.4 1z"/>',
  home: '<path d="m4 10.5 8-6.5 8 6.5V20a1.5 1.5 0 0 1-1.5 1.5H15v-6H9v6H5.5A1.5 1.5 0 0 1 4 20z"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 12.5 9 5 9-5"/><path d="m3 16.5 9 5 9-5"/>',
  'file-text': '<path d="M6 3.5h8l4.5 4.5v12.5H6z"/><path d="M14 3.5V8h4.5"/><path d="M9 13h6M9 16.5h4"/>',
  zap: '<path d="M13 2.5 5 13.5h5.5L11 21.5 19 10.5h-5.5z"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/><path d="M12 3.5c2.2 2.4 3.4 5.4 3.4 8.5s-1.2 6.1-3.4 8.5c-2.2-2.4-3.4-5.4-3.4-8.5S9.8 5.9 12 3.5z"/>',
  mail: '<rect x="3" y="5.5" width="18" height="13" rx="2.2"/><path d="m3.8 6.8 8.2 6 8.2-6"/>',
  phone: '<path d="M7 3.5h3l1.5 4-2 1.4a12 12 0 0 0 5.6 5.6l1.4-2 4 1.5v3a2.5 2.5 0 0 1-2.7 2.5C10.3 18.9 5.1 13.7 4.5 6.2A2.5 2.5 0 0 1 7 3.5z"/>',
  youtube: '<rect x="2.5" y="5.5" width="19" height="13" rx="4"/><path d="m10.5 9.5 5 2.5-5 2.5z" fill="currentColor" stroke="none"/>',
  instagram: '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17" cy="7" r="1" fill="currentColor" stroke="none"/>',
  twitter: '<path d="M20 5.5c-.7.4-1.5.6-2.3.7a4 4 0 0 0 1.8-2.2c-.8.5-1.7.8-2.6 1a4 4 0 0 0-6.9 3.6A11.4 11.4 0 0 1 3.5 4.5a4 4 0 0 0 1.2 5.3c-.6 0-1.2-.2-1.7-.5a4 4 0 0 0 3.2 4c-.5.1-1 .2-1.6.1a4 4 0 0 0 3.7 2.8A8 8 0 0 1 3 18a11.3 11.3 0 0 0 6.1 1.8c7.4 0 11.4-6.1 11.4-11.4v-.5c.8-.6 1.5-1.3 2-2.1z" fill="currentColor" stroke="none"/>',
  linkedin: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M7 10v7M7 7v.1M11 17v-4a2 2 0 0 1 4 0v4"/>',
  bookmark: '<path d="M6.5 3.5h11v17l-5.5-4-5.5 4z"/>',
  filter: '<path d="M3.5 5.5h17l-6.5 7.5v6l-4 2v-8z"/>',
  sort: '<path d="M7 4v16M4 7l3-3 3 3"/><path d="M17 20V4M14 17l3 3 3-3"/>',
  timer: '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 9.5v4l2.5 1.5"/><path d="M9.5 2.5h5"/>',
  flag: '<path d="M5.5 21V4h9l-1 3 1 3h-9"/><path d="M5.5 4v3"/>',
  trash: '<path d="M4 7h16"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7"/><path d="M6.5 7l.8 12a2 2 0 0 0 2 1.9h5.4a2 2 0 0 0 2-1.9l.8-12"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  refresh: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.8 4.5v4.2h-4.2"/>',
  sparkles: '<path d="m12 3 1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7z"/><path d="m18.5 15 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
  lightbulb: '<path d="M9 17.5h6"/><path d="M10 20.5h4"/><path d="M12 3.5a6 6 0 0 0-3.6 10.8c.5.4.8 1 .8 1.6v1.6h5.6v-1.6c0-.6.3-1.2.8-1.6A6 6 0 0 0 12 3.5z"/>',
  award: '<circle cx="12" cy="9" r="5.5"/><path d="m8.5 13.8-1.5 7 5-2.6 5 2.6-1.5-7"/>',
  edit: '<path d="M4 20h4l10-10a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  share: '<circle cx="18" cy="5.5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="18.5" r="2.5"/><path d="m8.2 10.7 7.6-3.9M8.2 13.3l7.6 3.9"/>',
  grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.6"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12M4 6v.1M4 12v.1M4 18v.1"/>',
  'external-link': '<path d="M13 5h6v6"/><path d="M19 5 10 14"/><path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
  message: '<path d="M20.5 12a8.5 8.5 0 1 1-4.3-7.4"/><path d="M20.5 4.5 12 13l-3-1"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6"/>',
  flask: '<path d="M9.5 3.5h5"/><path d="M10.5 3.5v5.2L5.6 17a2.4 2.4 0 0 0 2.1 3.6h8.6a2.4 2.4 0 0 0 2.1-3.6l-4.9-8.3V3.5"/><path d="M7.5 14h9"/>',
  pause: '<path d="M9 4.5v15M15 4.5v15" stroke-width="2.6"/>',
  megaphone: '<path d="M3.5 10.5v3a1.5 1.5 0 0 0 1.5 1.5h2l7 4V5l-7 4H5a1.5 1.5 0 0 0-1.5 1.5z"/><path d="M17 8.5a4.5 4.5 0 0 1 0 7"/><path d="M6.5 15v4.5a1.5 1.5 0 0 0 3 0V16"/>',
  wrench: '<path d="M14.5 6.5a4 4 0 1 0 4.9 4.9L21 13l-8 8-2-2 8-8z"/><path d="m5 19 4-4"/><path d="M4 8.5 6.5 6l2.5 2.5-2.5 2.5z"/>'
};

const SPRITE = `<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true"><defs><linearGradient id="scoreGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#6d28d9"/><stop offset="100%" stop-color="#a78bfa"/></linearGradient></defs>${Object.entries(
  ICONS
)
  .map(
    ([name, path]) =>
      `<symbol id="i-${name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${path}</symbol>`
  )
  .join('')}</svg>`;

export function mountSprite() {
  if (!document.getElementById('icon-sprite')) {
    const wrap = document.createElement('div');
    wrap.id = 'icon-sprite';
    wrap.innerHTML = SPRITE;
    document.body.prepend(wrap);
  }
}

export const icon = (name, cls = '') =>
  `<svg class="${cls}" aria-hidden="true" focusable="false"><use href="#i-${name}"/></svg>`;

/* ------------------------------------------------------------------ */
/* Toasts & dialogs                                                   */
/* ------------------------------------------------------------------ */

let toastHost;

export function toast(message, type = 'info', ms = 4200) {
  if (!toastHost) {
    toastHost = document.createElement('div');
    toastHost.className = 'toast-stack';
    toastHost.setAttribute('role', 'status');
    toastHost.setAttribute('aria-live', 'polite');
    document.body.append(toastHost);
  }
  const glyph = type === 'success' ? 'check-circle' : type === 'error' ? 'x-circle' : 'info';
  const node = document.createElement('div');
  node.className = `toast toast-${type}`;
  node.innerHTML = `${icon(glyph)}<div>${esc(message)}</div>`;
  toastHost.append(node);
  setTimeout(() => {
    node.style.transition = 'opacity .3s';
    node.style.opacity = '0';
    setTimeout(() => node.remove(), 320);
  }, ms);
}

/** Accessible confirm dialog resolved as a promise. */
export function confirmDialog({ title, body = '', confirmText = 'Confirm', cancelText = 'Cancel', danger = false }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'modal';
    overlay.innerHTML = `
      <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="dlg-title">
        <div class="modal-head">
          <h2 class="modal-title" id="dlg-title">${esc(title)}</h2>
          <button class="icon-btn" data-close aria-label="Close" style="width:32px;height:32px">${icon('x')}</button>
        </div>
        <p class="modal-body">${esc(body)}</p>
        <div class="modal-foot">
          <button class="btn btn-ghost" data-close>${esc(cancelText)}</button>
          <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-ok>${esc(confirmText)}</button>
        </div>
      </div>`;

    const close = (value) => {
      overlay.classList.remove('is-open');
      document.body.classList.remove('is-locked');
      setTimeout(() => overlay.remove(), 200);
      document.removeEventListener('keydown', onKey);
      resolve(value);
    };
    const onKey = (e) => { if (e.key === 'Escape') close(false); };

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay || e.target.closest('[data-close]')) close(false);
      if (e.target.closest('[data-ok]')) close(true);
    });
    document.addEventListener('keydown', onKey);
    document.body.append(overlay);
    document.body.classList.add('is-locked');
    requestAnimationFrame(() => overlay.classList.add('is-open'));
    overlay.querySelector('[data-ok]').focus();
  });
}

/* ------------------------------------------------------------------ */
/* Chrome                                                             */
/* ------------------------------------------------------------------ */

const NAV = [
  { href: 'index.html', label: 'Home', id: 'home', icon: 'home' },
  { href: 'courses.html', label: 'Batches', id: 'courses', icon: 'book' },
  { href: 'tests.html', label: 'Test Series', id: 'tests', icon: 'file-text' },
  { href: 'community.html#announcements', label: 'Announcements', id: 'announcements', icon: 'megaphone' },
  { href: 'community.html', label: 'Community', id: 'community', icon: 'users' },
  { href: 'downloads.html', label: 'Downloads', id: 'downloads', icon: 'download' },
  { href: 'dashboard.html#tools', label: 'Study Tools', id: 'tools', icon: 'sparkles' }
];

const TABS = [
  { href: 'index.html', label: 'Home', id: 'home', icon: 'home' },
  { href: 'courses.html', label: 'Batches', id: 'courses', icon: 'book' },
  { href: 'tests.html', label: 'Test Series', id: 'tests', icon: 'file-text' },
  { href: 'profile.html', label: 'Profile', id: 'profile', icon: 'user' }
];

/* The little shell card at the foot of the sidebar: sign-in prompt or the
   signed-in student. Kept deliberately short — the sidebar is a nav rail,
   not a billboard. */
function sidebarFoot() {
  const user = storage.user;
  if (isSignedIn() && user) {
    return `
      <div class="side-foot">
        <a class="side-user" href="dashboard.html">
          <span class="avatar">${esc(initials(user.username || 'Student'))}</span>
          <span class="side-user-text">
            <strong>${esc(user.username || 'Student')}</strong>
            <small>My learning</small>
          </span>
        </a>
      </div>`;
  }
  return `
    <div class="side-foot">
      <p class="side-foot-note">Sign in to pick up where you left off.</p>
      <a class="btn btn-primary btn-sm btn-block" href="login.html">Sign in</a>
      <a class="side-foot-link" href="login.html#register">Create a free account</a>
    </div>`;
}

export function renderHeader(active = '') {
  const host = document.getElementById('site-header');
  if (!host) return;
  document.body.classList.add('has-shell');
  const user = storage.user;

  host.innerHTML = `
    <aside class="sidebar" id="sidebar" aria-label="Sidebar">
      <a class="brand" href="index.html" aria-label="StudySpace home">
        <span class="brand-mark">${icon('zap')}</span>
        <span class="brand-text">StudySpace<small>Learn · Practise · Rank</small></span>
      </a>
      <nav class="side-nav" aria-label="Primary">
        ${NAV.map(
          (item) => `
          <a class="side-link" href="${item.href}" ${item.id === active ? 'aria-current="page"' : ''}>
            ${icon(item.icon)}<span>${item.label}</span>
          </a>`
        ).join('')}
      </nav>
      ${sidebarFoot()}
    </aside>
    <div class="sidebar-scrim" data-scrim hidden></div>

    <header class="topbar">
      <button class="icon-btn topbar-menu" aria-label="Open menu" aria-expanded="false" data-menu-toggle>${icon('menu')}</button>
      <a class="topbar-brand" href="index.html" aria-label="StudySpace home">
        <span class="brand-mark">${icon('zap')}</span>
        <span class="brand-text">StudySpace</span>
      </a>
      <div class="topbar-search" role="search">
        ${icon('search')}
        <input type="search" placeholder="Search batches, tests, subjects" aria-label="Search" data-global-search>
        <kbd>/</kbd>
      </div>
      <div class="topbar-actions">
        <button class="icon-btn" aria-label="Search" data-search-toggle>${icon('search')}</button>
        <button class="icon-btn has-dot" aria-label="Notifications" data-tip="Notifications">${icon('bell')}</button>
        ${
          isSignedIn() && user
            ? `<a class="user-chip" href="dashboard.html" aria-label="Signed in as ${esc(user.username || 'Student')}">
                 <span class="avatar">${esc(initials(user.username || 'Student'))}</span>
               </a>`
            : `<a class="btn btn-primary btn-sm topbar-cta" href="login.html">Sign in</a>`
        }
      </div>
    </header>`;

  const sidebar = host.querySelector('.sidebar');
  const scrim = host.querySelector('[data-scrim]');
  const menuBtn = host.querySelector('[data-menu-toggle]');

  const closeDrawer = () => {
    sidebar.classList.remove('is-open');
    document.body.classList.remove('is-locked');
    scrim.hidden = true;
    menuBtn.setAttribute('aria-expanded', 'false');
    menuBtn.innerHTML = icon('menu');
    menuBtn.setAttribute('aria-label', 'Open menu');
  };
  const openDrawer = () => {
    sidebar.classList.add('is-open');
    document.body.classList.add('is-locked');
    scrim.hidden = false;
    menuBtn.setAttribute('aria-expanded', 'true');
    menuBtn.innerHTML = icon('x');
    menuBtn.setAttribute('aria-label', 'Close menu');
  };

  menuBtn?.addEventListener('click', () => {
    if (sidebar.classList.contains('is-open')) closeDrawer();
    else openDrawer();
  });
  scrim?.addEventListener('click', closeDrawer);
  sidebar?.querySelectorAll('a').forEach((a) => a.addEventListener('click', closeDrawer));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar?.classList.contains('is-open')) {
      closeDrawer();
      menuBtn?.focus();
    }
  });

  const search = host.querySelector('[data-global-search]');
  search?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && search.value.trim()) {
      location.href = `courses.html?q=${encodeURIComponent(search.value.trim())}`;
    }
  });

  host.querySelector('[data-search-toggle]')?.addEventListener('click', () => {
    const open = document.body.classList.toggle('is-search-open');
    if (open) search?.focus();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !/input|textarea|select/i.test(document.activeElement.tagName)) {
      e.preventDefault();
      search?.focus();
    }
  });
}

export function renderTabbar(active = '') {
  const host = document.getElementById('site-tabbar');
  if (!host) return;
  host.innerHTML = `
    <nav class="tabbar" aria-label="Mobile navigation">
      <ul>
        ${TABS.map(
          (tab) => `
          <li>
            <a href="${tab.href}" ${tab.id === active ? 'aria-current="page"' : ''}>
              ${icon(tab.icon)}<span>${tab.label}</span>
            </a>
          </li>`
        ).join('')}
      </ul>
    </nav>`;
}

export function renderFooter() {
  const host = document.getElementById('site-footer');
  if (!host) return;
  const year = new Date().getFullYear();
  host.innerHTML = `
    <footer class="site-footer">
      <div class="container">
        <div class="footer-grid">
          <div class="footer-brand">
            <a class="brand" href="index.html">
              <span class="brand-mark">${icon('zap')}</span>
              <span class="brand-text">StudySpace<small>Learn · Practise · Rank</small></span>
            </a>
            <p>Structured courses, exam-pattern tests and revision tools for Indian students. Learn at your own pace, on any device.</p>
            <p class="footer-contact">
              <a href="mailto:support@studyspace.example">support@studyspace.example</a>
            </p>
          </div>
          <div class="footer-col">
            <h4>Learn</h4>
            <ul>
              <li><a href="courses.html?exam=JEE">JEE</a></li>
              <li><a href="courses.html?exam=NEET">NEET</a></li>
              <li><a href="courses.html?exam=UPSC">UPSC</a></li>
              <li><a href="courses.html?exam=SSC">SSC &amp; Banking</a></li>
              <li><a href="courses.html">All batches</a></li>
            </ul>
          </div>
          <div class="footer-col">
            <h4>Practise</h4>
            <ul>
              <li><a href="tests.html">Test series</a></li>
              <li><a href="tests.html">Previous year papers</a></li>
              <li><a href="tests.html">Daily practice</a></li>
              <li><a href="dashboard.html">My results</a></li>
            </ul>
          </div>
          <div class="footer-col">
            <h4>Company</h4>
            <ul>
              <li><a href="legal.html#about">About us</a></li>
              <li><a href="legal.html#accessibility">Accessibility</a></li>
              <li><a href="legal.html#contact">Contact</a></li>
              <li><a href="legal.html#privacy">Data &amp; privacy</a></li>
            </ul>
          </div>
          <div class="footer-col">
            <h4>Support</h4>
            <ul>
              <li><a href="legal.html#codes">Help centre</a></li>
              <li><a href="legal.html#codes">Redeem a code</a></li>
              <li><a href="legal.html#privacy">Privacy policy</a></li>
              <li><a href="legal.html#terms">Terms of use</a></li>
            </ul>
          </div>
        </div>
        <div class="footer-bottom">
          <span>© ${year} StudySpace. Built as a learning project.</span>
          <span style="display:flex;align-items:center;gap:14px">
            <span>Made for India</span>
            ${isPreview() ? '<span class="preview-flag">Preview · sample data</span>' : ''}
          </span>
        </div>
      </div>
    </footer>`;
}

/* ------------------------------------------------------------------ */
/* Cards                                                              */
/* ------------------------------------------------------------------ */

const THUMB_TONES = {
  Physics: 'thumb-physics',
  Chemistry: 'thumb-chemistry',
  Biology: 'thumb-biology',
  Mathematics: 'thumb-maths',
  Maths: 'thumb-maths',
  Reasoning: 'thumb-reasoning',
  English: 'thumb-english',
  'Computer Science': 'thumb-computer',
  'General Studies': 'thumb-default',
  Science: 'thumb-default'
};

export const thumbTone = (subject) => THUMB_TONES[subject] || 'thumb-default';

const BADGE_LABEL = {
  live: 'Live',
  new: 'New',
  bestseller: 'Bestseller',
  free: 'Free'
};

export function batchCard(course) {
  const faculty = course.faculty || [];
  const faces = faculty.slice(0, 4);
  const extra = faculty.length - faces.length;
  const badge = course.pricing_mode === 'free'
    ? '<span class="badge badge-free">Free</span>'
    : course.badge === 'live'
      ? '<span class="badge badge-live">Live</span>'
      : course.badge === 'bestseller'
        ? '<span class="badge badge-hot">Bestseller</span>'
        : '';

  return `
    <article class="batch-card">
      <a class="batch-cover ${thumbTone(course.subject)}" href="course.html?slug=${encodeURIComponent(course.slug)}" aria-label="${esc(course.title)}">
        ${badge}
        <span class="cover-tag">${esc(course.exam || course.subject || 'Batch')}</span>
        <span class="cover-faces">
          ${faces.length
            ? faces.map((f) => `<span class="cover-face">${esc(f.initials || initials(f.name))}</span>`).join('')
            : `<span class="cover-face">${esc(initials(course.subject || 'StudySpace'))}</span>`}
          ${extra > 0 ? `<span class="cover-more">+${extra}</span>` : ''}
        </span>
        ${course.withBooks ? '<span class="cover-pill">with Hindi Books</span>' : ''}
      </a>
      <div class="batch-body">
        <h3 class="batch-title">
          <a href="course.html?slug=${encodeURIComponent(course.slug)}">${esc(course.title)}</a>
        </h3>
        <p class="batch-meta">
          <span>${esc(course.subject || 'General')}</span>
          <span>${esc(course.language || 'Hinglish')}</span>
        </p>
        <p class="batch-start">
          ${icon('calendar')}
          <span>${course.startsOn ? `Starts on ${shortDate(course.startsOn)}` : 'Starts soon'}</span>
        </p>
        <div class="batch-foot">
          <a class="btn btn-primary btn-sm batch-cta" href="course.html?slug=${encodeURIComponent(course.slug)}">
            View Details ${icon('arrow-right')}
          </a>
        </div>
      </div>
    </article>`;
}

export function todayClassCard(item) {
  const live = item.status === 'live';
  return `
    <article class="today-card">
      <div class="today-video ${live ? 'is-live' : ''}">
        <span class="today-face">${esc(initials(item.faculty))}</span>
        ${live ? '<span class="today-live">LIVE NOW</span>' : `<span class="today-time">${esc(item.status)}</span>`}
      </div>
      <div class="today-body">
        <h3>${esc(item.title)}</h3>
        <p>${esc(item.faculty)} · ${esc(item.subject)}</p>
        <div class="today-foot">
          <span class="today-clock">${icon('clock')} ${esc(item.time)}</span>
          <a class="link" href="${item.status === 'live' ? `player.html?lesson=${encodeURIComponent(item.slug || 'number-system-1')}` : 'courses.html'}">
            ${live ? 'Join' : 'Remind me'} ${icon('arrow-right')}
          </a>
        </div>
      </div>
    </article>`;
}

export function testCard(test) {
  const free = !test.price;
  const marks = test.marks || (test.questions ? test.questions * 2 : 0);
  return `
    <article class="test-card">
      <div class="test-card-top">
        <span class="test-eyebrow">${esc(test.exam)} · ${esc(test.kind)}</span>
        <span class="badge ${free ? 'badge-free' : 'badge-paid'}">${free ? 'Free' : money(test.price)}</span>
      </div>
      <h3 class="test-title">${esc(test.title)}</h3>
      <p class="test-meta">
        ${test.questions} Questions · ${marks} Marks
      </p>
      <p class="test-meta">
        ${test.duration} minutes · ${compact(test.attempts)} attempts
      </p>
      <div class="test-card-foot">
        <span class="tiny subtle">${countdown(test.startsAt) || shortDate(test.startsAt) || 'Always open'}</span>
        ${
          test.locked
            ? '<span class="badge badge-outline">Enrol to unlock</span>'
            : `<a class="btn btn-primary btn-sm" href="test-player.html?test=${test.id}">Start Test</a>`
        }
      </div>
    </article>`;
}

export function skeletonBatchGrid(count = 6) {
  return Array.from({ length: count })
    .map(
      () => `
      <div class="batch-card" aria-hidden="true">
        <div class="skeleton" style="aspect-ratio:16/8.4"></div>
        <div class="batch-body">
          <div class="skeleton skeleton-title"></div>
          <div class="skeleton skeleton-text" style="width:60%"></div>
          <div class="skeleton skeleton-text" style="width:80%"></div>
          <div class="skeleton skeleton-text" style="width:40%"></div>
        </div>
      </div>`
    )
    .join('');
}

export function emptyState({ title, body, actionLabel, actionHref, iconName = 'search' }) {
  return `
    <div class="empty-state">
      ${icon(iconName)}
      <h3>${esc(title)}</h3>
      <p>${esc(body)}</p>
      ${actionLabel ? `<a class="btn btn-primary" href="${actionHref || '#'}">${esc(actionLabel)}</a>` : ''}
    </div>`;
}

/** Wire the page chrome in one call. */
export function mountChrome(active) {
  mountSprite();
  renderHeader(active);
  renderTabbar(active);
  renderFooter();
  highlightPreview();
  registerServiceWorker();
}

/** Registered once per page so offline works from any entry point. */
function registerServiceWorker() {
  const sw = navigator.serviceWorker;
  if (!sw || location.protocol === 'file:') return;

  // A page that was already controlled should reload once when the new worker
  // takes over, so a deploy is never shown as new HTML with last release's CSS.
  const wasControlled = Boolean(sw.controller);
  let reloaded = false;

  if (typeof sw.addEventListener === 'function') {
    sw.addEventListener('controllerchange', () => {
      if (!wasControlled || reloaded) return;
      reloaded = true;
      location.reload();
    });
  }

  window.addEventListener('load', async () => {
    try {
      const registration = await sw.register(new URL('../../sw.js', import.meta.url), {
        updateViaCache: 'none'
      });
      if (typeof registration?.update === 'function') registration.update().catch(() => {});

      if (typeof registration?.addEventListener === 'function') {
        registration.addEventListener('updatefound', () => {
          const worker = registration.installing;
          worker?.addEventListener('statechange', () => {
            if (worker.state === 'installed' && sw.controller) worker.postMessage('SKIP_WAITING');
          });
        });
      }
    } catch {
      /* unsupported, private mode or a sandboxed iframe — the site still works */
    }
  });
}

function highlightPreview() {
  document.querySelectorAll('[data-preview-only]').forEach((node) => {
    node.hidden = !isPreview();
  });
}
