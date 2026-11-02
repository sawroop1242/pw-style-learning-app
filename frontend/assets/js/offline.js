/**
 * offline.html — retry the navigation when the network is back.
 *
 * Its own file rather than an inline <script>: the Content-Security-Policy is
 * `script-src 'self'`, which blocks inline blocks outright. A policy with an
 * exception for "just this one page" is a policy with a hole in it.
 */
const retry = document.getElementById('retry');
if (retry) {
  retry.addEventListener('click', () => location.reload());
}
