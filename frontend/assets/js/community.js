/**
 * Community — announcements from faculty and student discussion.
 *
 * There is no community endpoint in the API yet, so these are the bundled
 * sample threads and every action says so instead of pretending to post.
 */

import { $, $$, esc, toast } from './core.js';
import { mountChrome, icon } from './ui.js';
import { COMMUNITY } from './data.js';

mountChrome('community');

function postCard(post) {
  return `
    <article class="post-card">
      <div class="post-head">
        <span class="post-avatar">${esc(post.initials)}</span>
        <span class="post-who">
          <strong>${esc(post.author)}</strong>
          <small>${esc(post.time)}</small>
        </span>
      </div>
      <h3>${esc(post.title)}</h3>
      <p>${esc(post.body)}</p>
      <div class="post-actions">
        <button type="button" data-like aria-pressed="false">
          ${icon('heart')} <span data-likes>${post.likes}</span>
        </button>
        <button type="button" data-reply>
          ${icon('message')} ${post.comments}
        </button>
        <button type="button" data-share>
          ${icon('share')} Share
        </button>
      </div>
    </article>`;
}

function render() {
  $('#discussion-list').innerHTML = COMMUNITY.discussion.map(postCard).join('');
  $('#announcement-list').innerHTML = COMMUNITY.announcements.map(postCard).join('');
}

/* Tabs, honouring #announcements so the sidebar link opens the right panel. */
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
if (location.hash === '#announcements') selectTab(1);

/* Post actions */
document.addEventListener('click', (e) => {
  const like = e.target.closest('[data-like]');
  if (like) {
    const on = like.getAttribute('aria-pressed') !== 'true';
    like.setAttribute('aria-pressed', String(on));
    like.classList.toggle('is-on', on);
    const count = like.querySelector('[data-likes]');
    count.textContent = String(Number(count.textContent) + (on ? 1 : -1));
    return;
  }
  if (e.target.closest('[data-reply]') || e.target.closest('[data-compose]')) {
    toast('Threaded replies arrive with the community API — this build shows the sample threads.', 'info', 5200);
    return;
  }
  if (e.target.closest('[data-share]')) {
    const card = e.target.closest('.post-card');
    const title = card?.querySelector('h3')?.textContent?.trim() || 'StudySpace';
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(`${title} — ${location.href}`).then(
        () => toast('Link copied.', 'success'),
        () => toast('Could not copy the link in this browser.', 'error')
      );
    } else {
      toast('Copy the address bar to share this thread.', 'info');
    }
  }
});

render();
