/* Console behaviour that CSS cannot express.
 *
 * Five small things, all of them enhancing markup that already works without
 * this file: the mobile drawer, the "Jump to" combobox, the account menu, the
 * sticky header's shadow, and `aria-sort` on a sorted column.
 *
 * No inline event handlers anywhere — the site's CSP allows scripts from this
 * origin only, and the admin is served under the same policy as the app.
 */
(function () {
  'use strict';

  var body = document.body;
  if (!body || !body.classList.contains('ss-admin')) return;

  var MOBILE = '(max-width: 1024px)';

  /* ------------------------------------------------------------ the drawer */

  var toggle = document.getElementById('toggle-nav-sidebar');
  var sidebar = document.getElementById('nav-sidebar');

  function setOpen(open) {
    body.classList.toggle('nav-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  if (toggle) {
    toggle.setAttribute('aria-expanded', 'false');
    toggle.addEventListener('click', function () {
      setOpen(!body.classList.contains('nav-open'));
    });
  }

  /* Choosing a screen closes the drawer, so the destination is visible. */
  if (sidebar) {
    sidebar.addEventListener('click', function (event) {
      if (event.target.closest('a') && window.matchMedia(MOBILE).matches) setOpen(false);
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && body.classList.contains('nav-open')) setOpen(false);
  });

  document.addEventListener('click', function (event) {
    if (!body.classList.contains('nav-open')) return;
    if (sidebar && sidebar.contains(event.target)) return;
    if (toggle && toggle.contains(event.target)) return;
    setOpen(false);
  });

  /* --------------------------------------------------------------- jump-to */

  var jumpForm = document.querySelector('.ss-jump');
  var jump = document.getElementById('ss-jump-input');
  var datalist = document.getElementById('ss-jump-list');
  var results = document.getElementById('ss-jump-results');
  var active = -1;

  if (jumpForm && jump && datalist && results) {
    var screens = [];
    var options = datalist.options;
    for (var i = 0; i < options.length; i += 1) {
      var label = options[i].value;
      var path = options[i].getAttribute('data-url') || '';
      // "Add course" and similar actions are links, not screens.
      if (!label || !path) continue;
      screens.push({ label: label, url: path, group: groupOf(path) });
    }

    function groupOf(path) {
      var parts = path.split('/').filter(Boolean); // ["admin", "courses", "course"]
      return parts.length > 2 ? parts[1].replace(/-/g, ' ') : '';
    }

    function close() {
      active = -1;
      results.hidden = true;
      results.innerHTML = '';
      jump.setAttribute('aria-expanded', 'false');
      jump.removeAttribute('aria-activedescendant');
    }

    function paint(matches, query) {
      if (!query || !matches.length) {
        results.innerHTML = query
          ? '<li class="ss-jump-none" role="option" aria-disabled="true">No screen matches “' +
            escapeHtml(query) + '”</li>'
          : '';
        results.hidden = !query;
        jump.setAttribute('aria-expanded', query ? 'true' : 'false');
        return;
      }

      results.innerHTML = matches
        .map(function (screen, index) {
          return (
            '<li role="option" id="ss-jump-opt-' + index + '" aria-selected="false">' +
            '<a href="' + escapeHtml(screen.url) + '" tabindex="-1">' +
            '<span>' + highlight(screen.label, query) + '</span>' +
            (screen.group ? '<span class="ss-jump-group">' + escapeHtml(screen.group) + '</span>' : '') +
            '</a></li>'
          );
        })
        .join('');
      results.hidden = false;
      jump.setAttribute('aria-expanded', 'true');
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, function (ch) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
      });
    }

    function highlight(label, query) {
      var at = label.toLowerCase().indexOf(query.toLowerCase());
      if (at < 0) return escapeHtml(label);
      return (
        escapeHtml(label.slice(0, at)) +
        '<strong>' + escapeHtml(label.slice(at, at + query.length)) + '</strong>' +
        escapeHtml(label.slice(at + query.length))
      );
    }

    function search(query) {
      var wanted = query.trim().toLowerCase();
      if (!wanted) return [];
      var starts = [];
      var contains = [];
      screens.forEach(function (screen) {
        var label = screen.label.toLowerCase();
        if (label.indexOf(wanted) === 0) starts.push(screen);
        else if (label.indexOf(wanted) !== -1) contains.push(screen);
      });
      return starts.concat(contains).slice(0, 8);
    }

    function move(step) {
      var items = results.querySelectorAll('li[role="option"] a');
      if (!items.length) return;
      active = (active + step + items.length) % items.length;
      for (var n = 0; n < items.length; n += 1) {
        items[n].parentNode.setAttribute('aria-selected', n === active ? 'true' : 'false');
      }
      jump.setAttribute('aria-activedescendant', items[active].parentNode.id);
      items[active].scrollIntoView({ block: 'nearest' });
    }

    jump.addEventListener('input', function () {
      active = -1;
      paint(search(jump.value), jump.value.trim());
    });

    jump.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (results.hidden) paint(search(jump.value), jump.value.trim());
        move(1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        move(-1);
      } else if (event.key === 'Enter') {
        var items = results.querySelectorAll('li[role="option"] a');
        var target = items[active >= 0 ? active : 0];
        if (target) {
          event.preventDefault();
          window.location.href = target.getAttribute('href');
        }
      } else if (event.key === 'Escape') {
        close();
      }
    });

    jump.addEventListener('blur', function () {
      // A click on a result is a blur first; let it land before closing.
      window.setTimeout(close, 120);
    });

    jumpForm.addEventListener('submit', function (event) {
      event.preventDefault();
    });

    /* "/" focuses the box, as long as nobody is already typing. */
    document.addEventListener('keydown', function (event) {
      if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return;
      var el = document.activeElement;
      if (el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable)) return;
      event.preventDefault();
      jump.focus();
    });
  }

  /* ---------------------------------------------------------- account menu */

  var account = document.getElementById('ss-account');
  if (account) {
    document.addEventListener('click', function (event) {
      if (account.open && !account.contains(event.target)) account.open = false;
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && account.open) {
        account.open = false;
        var summary = account.querySelector('summary');
        if (summary) summary.focus();
      }
    });
  }

  /* --------------------------------------------------- header shadow on scroll */

  var header = document.getElementById('header');
  if (header) {
    var onScroll = function () {
      header.classList.toggle('is-scrolled', window.scrollY > 4);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }


  /* -------------------------------------------------- a failed save is announced */

  /* role="alert" only speaks for changes that happen after the page settles, so
     the summary is also focused on load: a screen reader reads it, and the
     keyboard user lands where the problem is described. */
  var summary = document.querySelector('.ss-form-errors');
  if (summary) summary.focus({ preventScroll: false });

  /* ------------------------------------------------ widgets without a name */

  var inlineCount = 0;

  /* Django renders some controls with a label beside them instead of a label
     bound to them: a tabular inline puts each widget under a column head, and
     a split date-time field writes "Date:" and "Time:" as loose text. Nothing
     announces those, so a screen-reader user meets "edit text, blank".

     Three passes, narrowest first. Each bails out the moment a control already
     has a name, so a ModelAdmin that labels its own fields is left alone. */

  function named(control) {
    if (control.getAttribute('aria-label') || control.getAttribute('aria-labelledby')) return true;
    if (control.id && document.querySelector('label[for="' + control.id + '"]')) return true;
    return !!(control.closest('label') && control.closest('label').textContent.trim());
  }

  function nameFrom(control, text) {
    if (!text || control.type === 'hidden' || named(control)) return;
    control.setAttribute('aria-label', text);
  }

  /* 1. A table cell borrows its column heading — inline rows and the editable
        cells on a changelist both work this way. */
  Array.prototype.forEach.call(document.querySelectorAll('#content-main table'), function (table) {
    var headers = Array.prototype.map.call(
      table.querySelectorAll('thead th'),
      function (th) { return (th.textContent || '').trim(); }
    );
    Array.prototype.forEach.call(table.querySelectorAll('tbody tr'), function (row) {
      Array.prototype.forEach.call(row.children, function (cell, index) {
        var label = headers[index];
        if (!label) return;
        Array.prototype.forEach.call(cell.querySelectorAll('input, select, textarea'), function (control) {
          nameFrom(control, label);
        });
      });
    });

    /* The inline table sits under its own <h2>; point at it so it is announced
       as "Questions" rather than as an unlabelled grid. */
    var heading = table.closest('.inline-related') &&
      table.closest('.inline-related').querySelector('.inline-heading');
    if (heading && !table.getAttribute('aria-label') && !table.querySelector('caption')
        && !table.getAttribute('aria-labelledby')) {
      if (!heading.id) heading.id = 'ss-inline-heading-' + (inlineCount += 1);
      table.setAttribute('aria-labelledby', heading.id);
    }
  });

  /* 2. A form row's own label, when the control lost its `for`. Only rows with a
        single label: a row of checkboxes has no one name to inherit. */
  Array.prototype.forEach.call(document.querySelectorAll('#content-main .form-row'), function (row) {
    var labels = row.querySelectorAll('label');
    if (labels.length !== 1) return;
    var text = (labels[0].textContent || '').replace(/\s+/g, ' ').trim().replace(/:$/, '');
    if (!text) return;
    Array.prototype.forEach.call(row.querySelectorAll('input, select, textarea'), function (control) {
      nameFrom(control, text);
    });
  });

  /* 3. Last resort: the field's own name, in words. Better than silence. */
  Array.prototype.forEach.call(document.querySelectorAll('#content-main input, #content-main select'), function (control) {
    if (named(control) || control.type === 'hidden') return;
    var hint = (control.name || '').replace(/^.*-/, '').replace(/_/g, ' ').trim();
    if (!hint) return;
    nameFrom(control, hint.charAt(0).toUpperCase() + hint.slice(1));
  });

  /* A reference to an element that does not exist tells a screen reader nothing.
     Django emits one when a tabular inline has help text but no help element. */
  Array.prototype.forEach.call(
    document.querySelectorAll('[aria-describedby], [aria-labelledby]'),
    function (el) {
      ['aria-describedby', 'aria-labelledby'].forEach(function (attr) {
        var ids = (el.getAttribute(attr) || '').split(/\s+/).filter(Boolean);
        var kept = ids.filter(function (id) { return !!document.getElementById(id); });
        if (kept.length !== ids.length) {
          if (kept.length) el.setAttribute(attr, kept.join(' '));
          else el.removeAttribute(attr);
        }
      });
    }
  );

  /* --------------------------------------------------------------- aria-sort */

  var sorted = document.querySelectorAll('.results thead th.sorted');
  for (var s = 0; s < sorted.length; s += 1) {
    sorted[s].setAttribute(
      'aria-sort',
      sorted[s].classList.contains('descending') ? 'descending' : 'ascending'
    );
  }

  /* The nav filter hides rows with a `hidden` attribute; Django's own script
     only filters the sidebar when the rail is in its slide-out state. Keep
     the empty groups out of sight instead of leaving bare captions. */
  var navFilter = document.getElementById('nav-filter');
  if (navFilter && sidebar) {
    navFilter.addEventListener('input', function () {
      var query = navFilter.value.trim().toLowerCase();
      var groups = sidebar.querySelectorAll('.ss-nav-group');
      Array.prototype.forEach.call(groups, function (group) {
        var rows = group.querySelectorAll('tbody tr');
        var shown = 0;
        Array.prototype.forEach.call(rows, function (row) {
          var match = !query || row.textContent.toLowerCase().indexOf(query) !== -1;
          row.hidden = !match;
          if (match) shown += 1;
        });
        group.hidden = shown === 0;
      });
    });
  }
})();
