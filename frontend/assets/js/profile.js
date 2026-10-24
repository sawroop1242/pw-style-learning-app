/** Profile — identity, quick stats and the settings menu. */

import { $, esc, initials, storage, isSignedIn, auth } from './core.js';
import { mountChrome, icon, toast } from './ui.js';
import { PROFILE, DASHBOARD } from './data.js';

mountChrome('profile');

function signedInOrDemo() {
  const user = storage.user;
  const signedIn = isSignedIn() && user;
  return {
    signedIn: Boolean(signedIn),
    name: signedIn ? user.username : PROFILE.name,
    email: signedIn ? user.email || PROFILE.email : PROFILE.email
  };
}

function render() {
  const who = signedInOrDemo();
  $('#profile-avatar').textContent = initials(who.name);
  $('#profile-name').textContent = who.name;
  $('#profile-email').textContent = who.email;
  $('#stat-enrolled').textContent = String(DASHBOARD.stats.courses);
  $('#stat-streak').textContent = String(DASHBOARD.student.streak);
  $('#stat-tests').textContent = String(DASHBOARD.stats.testsTaken);

  $('#profile-menu').innerHTML = PROFILE.menu
    .map(
      (item) => `
      <a class="menu-row" href="${item.href}">
        <span class="menu-icon">${icon(item.icon)}</span>
        <span>${esc(item.label)}</span>
        <span class="menu-chevron">${icon('chevron-right')}</span>
      </a>`
    )
    .join('');

  const note = $('#profile-note');
  if (who.signedIn) {
    note.textContent = 'Signed in. Your notes, bookmarks and progress are visible only to you.';
  }
}

document.querySelector('[data-sign-out]')?.addEventListener('click', async () => {
  await auth.logout();
  toast('Signed out.', 'success');
  render();
  setTimeout(() => { location.href = 'index.html'; }, 600);
});

render();
