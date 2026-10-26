/**
 * Announcements.
 *
 * `/api/community/` is a read-only feed of notices written by faculty, so this
 * page shows exactly that: no likes, no reply box, no composed posts. The
 * second tab narrows the feed to the batches the signed-in learner can open.
 */

import { $$, esc, getJson, rows, apiQuery, shortDate, isSignedIn } from './core.js';
import { mountChrome, icon, emptyState, errorState, wireRetry } from './ui.js';

mountChrome('community');

function postCard(post) {
  const initials = (post.author_name || 'Faculty')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join('');
  return `
    <article class="post-card">
      <div class="post-head">
        <span class="post-avatar">${esc(initials || 'SS')}</span>
        <span class="post-who">
          <strong>${esc(post.author_name || 'Faculty')}</strong>
          <small>${esc(post.course_title || 'All batches')} · ${esc(shortDate(post.created_at))}</small>
        </span>
        ${post.pinned ? '<span class="badge badge-live">Pinned</span>' : ''}
      </div>
      <h3>${esc(post.title)}</h3>
      <p>${esc(post.body || '')}</p>
      ${
        post.course_slug
          ? `<div class="post-actions"><a class="link" href="course.html?slug=${encodeURIComponent(post.course_slug)}">Open the batch ${icon('arrow-right')}</a></div>`
          : ''
      }
    </article>`;
}

function paint(host, list, empty) {
  host.innerHTML = list.length
    ? list.map(postCard).join('')
    : emptyState({
        title: 'No announcements yet',
        body: 'Notices from your faculty appear here as soon as they are posted.',
        iconName: 'message',
        ...empty
      });
}

function fail(err) {
  const markup = errorState({
    title: 'Announcements could not load',
    body: err.message || 'The server did not answer.',
    retryLabel: 'Try again'
  });
  document.getElementById('announcement-list').innerHTML = markup;
  document.getElementById('batch-list').innerHTML = '';
}

async function loadAll() {
  try {
    paint(document.getElementById('announcement-list'), rows(await getJson(`/community/${apiQuery({ page_size: 40 })}`)));
  } catch (err) {
    fail(err);
  }
}

async function loadBatchOnly() {
  const host = document.getElementById('batch-list');
  host.innerHTML = '<p class="small muted">Loading your batch notices…</p>';

  if (!isSignedIn()) {
    host.innerHTML = emptyState({
      title: 'Sign in to filter by batch',
      body: 'Batch notices are addressed to the batches on your account. The All tab shows every public notice.',
      actionLabel: 'Sign in',
      actionHref: 'login.html?next=community.html',
      iconName: 'user'
    });
    return;
  }

  try {
    const mine = rows(await getJson(`/courses/${apiQuery({ mine: 1, page_size: 40 })}`));
    if (!mine.length) {
      paint(host, [], {
        title: 'No batches on your account',
        body: 'Join or unlock a batch and its notices appear here.'
      });
      return;
    }
    const feed = await Promise.all(
      mine.map((course) =>
        getJson(`/community/${apiQuery({ course: course.id, page_size: 10 })}`)
          .then((payload) => rows(payload))
          .catch(() => [])
      )
    );
    const seen = new Set();
    const merged = feed
      .flat()
      .filter((post) => (seen.has(post.id) ? false : seen.add(post.id)))
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    paint(host, merged, {
      title: 'Nothing posted to your batches yet',
      body: 'When a teacher publishes a notice for one of your batches it lands here.'
    });
  } catch (err) {
    host.innerHTML = errorState({
      title: 'Your batch notices could not load',
      body: err.message || 'The server did not answer.',
      retryLabel: 'Try again'
    });
  }
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
  if (index === 1) loadBatchOnly();
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTab(index));
  tab.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    selectTab(next);
  });
});
if (location.hash === '#batch') selectTab(1);

wireRetry();
loadAll();
