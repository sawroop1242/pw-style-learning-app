/**
 * Profile — who is signed in and what the API knows about them.
 *
 * Every number on this page is a `count` the API returned for this account:
 * the batches it can open, the notes it wrote and the attempts it has sat.
 * A guest sees the sign-in prompt instead of borrowed figures.
 */

import { $, esc, initials, storage, isSignedIn, auth, getJson, apiQuery } from './core.js';
import { mountChrome, icon, toast, emptyState } from './ui.js';
import { PROFILE_MENU } from './content.js';

mountChrome('profile');

function guestView() {
  $('#profile-avatar').textContent = '—';
  $('#profile-name').textContent = 'Guest';
  $('#profile-email').textContent = 'Not signed in on this device';
  ['#stat-enrolled', '#stat-notes', '#stat-tests'].forEach((selector) => {
    const node = $(selector);
    if (node) node.textContent = '—';
  });
  const note = $('#profile-note');
  note.className = 'empty-state';
  note.style.padding = '0';
  note.innerHTML = emptyState({
    title: 'You are browsing signed out',
    body: 'Signing in attaches your notes, progress and attempts to your account. You can still attempt any open test as a guest.',
    actionLabel: 'Sign in',
    actionHref: 'login.html?next=profile.html',
    iconName: 'user'
  });
  $('[data-sign-out]').hidden = true;
}

function renderMenu() {
  $('#profile-menu').innerHTML = PROFILE_MENU.map(
    (item) => `
      <a class="menu-row" href="${item.href}">
        <span class="menu-icon">${icon(item.icon)}</span>
        <span>${esc(item.label)}</span>
        <span class="menu-chevron">${icon('chevron-right')}</span>
      </a>`
  ).join('');
}

function setStat(selector, value) {
  const node = $(selector);
  if (node) node.textContent = value === null || value === undefined ? '—' : String(value);
}

async function load() {
  renderMenu();

  if (!isSignedIn()) {
    guestView();
    return;
  }

  // The cached identity shows immediately; the API is authoritative.
  const cached = storage.user || {};
  $('#profile-avatar').textContent = initials(cached.username || 'SS');
  $('#profile-name').textContent = cached.username || 'Student';
  $('#profile-email').textContent = cached.email || '';

  try {
    const me = await getJson('/auth/me/');
    $('#profile-name').textContent = me.username;
    $('#profile-email').textContent = me.email || '';
    $('#profile-avatar').textContent = initials(me.username || 'SS');
    const role = $('#profile-role');
    if (role) role.textContent = me.role ? String(me.role).replace(/_/g, ' ') : 'student';
    const note = $('#profile-note');
    note.className = 'tiny subtle';
    note.textContent = `Signed in since ${new Date(me.date_joined).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    })}. Your notes, progress and attempts are visible only to you.`;
  } catch (err) {
    if (err.status === 401) {
      await auth.logout();
      guestView();
      return;
    }
    const note = $('#profile-note');
    note.className = 'tiny subtle';
    note.textContent = 'Your profile could not be refreshed. Showing what this device remembers.';
  }

  const [batches, notes, attempts] = await Promise.allSettled([
    getJson(`/courses/${apiQuery({ mine: 1, page_size: 1 })}`),
    getJson(`/notes/${apiQuery({ page_size: 1 })}`),
    getJson(`/quiz-attempts/${apiQuery({ page_size: 1 })}`)
  ]);

  setStat('#stat-enrolled', batches.status === 'fulfilled' ? batches.value.count : null);
  setStat('#stat-notes', notes.status === 'fulfilled' ? notes.value.count : null);
  setStat('#stat-tests', attempts.status === 'fulfilled' ? attempts.value.count : null);
}

$('[data-sign-out]')?.addEventListener('click', async () => {
  await auth.logout();
  toast('Signed out.', 'success');
  location.href = 'index.html';
});

load();
