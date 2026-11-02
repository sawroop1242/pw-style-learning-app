/* Console behaviour that CSS cannot express.
 *
 * Three things, all small: open the navigation rail as a drawer on a phone,
 * remember whether the rail was left collapsed on a desktop, and turn the
 * "Jump to" box into a real navigation control over the models this account
 * may open.
 *
 * No inline event handlers anywhere — the site's CSP allows scripts from this
 * origin only, and the admin is served under the same policy as the app.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'ss-admin-nav';
  var body = document.body;
  if (!body || !body.classList.contains('ss-admin')) return;

  /* ------------------------------------------------------------- the rail */

  var toggle = document.getElementById('toggle-nav-sidebar');
  var sidebar = document.getElementById('nav-sidebar');

  function setCollapsed(collapsed) {
    body.classList.toggle('nav-collapsed', collapsed);
    if (toggle) toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    try {
      window.localStorage.setItem(STORAGE_KEY, collapsed ? 'collapsed' : 'open');
    } catch (error) {
      /* Private mode: the rail simply forgets, which is fine. */
    }
  }

  function setOpen(open) {
    body.classList.toggle('nav-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      if (window.matchMedia('(max-width: 1024px)').matches) {
        setOpen(!body.classList.contains('nav-open'));
      } else {
        setCollapsed(!body.classList.contains('nav-collapsed'));
      }
    });
  }

  try {
    if (window.localStorage.getItem(STORAGE_KEY) === 'collapsed') {
      setCollapsed(true);
    }
  } catch (error) {
    /* ignore */
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') setOpen(false);
  });

  /* A click outside the open drawer closes it, so the page underneath is
   * immediately usable on a phone. */
  document.addEventListener('click', function (event) {
    if (!body.classList.contains('nav-open')) return;
    if (sidebar && sidebar.contains(event.target)) return;
    if (toggle && toggle.contains(event.target)) return;
    setOpen(false);
  });

  /* ------------------------------------------------------------ jump-to */

  var jump = document.getElementById('ss-jump-input');
  var list = document.getElementById('ss-jump-list');
  if (!jump || !list) return;

  function targetFor(query) {
    var wanted = query.trim().toLowerCase();
    if (!wanted) return null;
    var options = list.options;
    var starts = null;
    var contains = null;
    for (var i = 0; i < options.length; i += 1) {
      var label = options[i].value.toLowerCase();
      if (label === wanted) return options[i].getAttribute('data-url');
      if (!starts && label.indexOf(wanted) === 0) starts = options[i].getAttribute('data-url');
      if (!contains && label.indexOf(wanted) !== -1) contains = options[i].getAttribute('data-url');
    }
    return starts || contains;
  }

  jump.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter') return;
    var url = targetFor(jump.value);
    if (!url) return;
    event.preventDefault();
    window.location.href = url;
  });

  /* Choosing an option from the datalist fires `input` with the full label. */
  jump.addEventListener('input', function () {
    var url = targetFor(jump.value);
    var exact = false;
    for (var i = 0; i < list.options.length; i += 1) {
      if (list.options[i].value.toLowerCase() === jump.value.trim().toLowerCase()) exact = true;
    }
    if (url && exact) window.location.href = url;
  });

  /* "/" focuses the box, as long as the user is not already typing. */
  document.addEventListener('keydown', function (event) {
    if (event.key !== '/' || event.metaKey || event.ctrlKey) return;
    var active = document.activeElement;
    var typing = active && /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName);
    if (typing || (active && active.isContentEditable)) return;
    event.preventDefault();
    jump.focus();
  });
})();
