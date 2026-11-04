/**
 * The batch outline: move a section or a class, then save the order once.
 *
 * The screen is one list of sections, each holding its classes. Three ways to
 * change the order, all of them writing to the same DOM:
 *
 *   • drag the handle (pointer events, so a finger works as well as a mouse);
 *   • press ↑ / ↓ — on the row's buttons, or on the handle itself with the
 *     arrow keys — which is what WCAG 2.5.7 asks for: the same outcome without
 *     a dragging movement;
 *   • pick another section from the class's menu, which moves it there.
 *
 * Nothing is sent until "Save order". The whole order goes in one request, so
 * the server can validate it as a whole and the database is never left half
 * renumbered. The request carries the revision the page was built from; if
 * somebody else saved in the meantime the server answers 409 and this script
 * says so instead of silently overwriting their work.
 *
 * Without this file the screen still reads correctly — the lists, the titles
 * and the links are in the HTML — and the arrow buttons and menus simply do
 * nothing.
 */
(function () {
  'use strict';

  var form = document.querySelector('[data-outline]');
  if (!form) return;

  var sectionList = form.querySelector('[data-outline-sections]');
  var saveButton = form.querySelector('[data-outline-save]');
  var resetButton = form.querySelector('[data-outline-reset]');
  var status = form.querySelector('#outline-status');
  if (!sectionList || !saveButton || !status) return;

  var saveUrl = form.getAttribute('data-save-url') || window.location.pathname;
  var revision = form.getAttribute('data-revision') || '';
  var csrf = form.querySelector('input[name="csrfmiddlewaretoken"]');
  var pristine = sectionList.cloneNode(true);
  var moves = 0;
  var saving = false;

  function rowsOf(list) {
    return Array.prototype.slice.call(list.querySelectorAll('[data-outline-lesson]'));
  }

  function itemTitle(item) {
    var title = item.querySelector('.ss-outline-title, .ss-outline-lesson-title');
    return title ? title.textContent.trim() : 'that row';
  }

  function listName(list) {
    var section = list.closest('[data-outline-section]');
    var title = section && section.querySelector('.ss-outline-title');
    return title ? title.textContent.trim() : 'another section';
  }

  function setStatus(text, tone) {
    status.textContent = text;
    status.classList.toggle('is-dirty', tone === 'dirty');
    status.classList.toggle('is-error', tone === 'error');
  }

  function setDirty(dirty) {
    saveButton.disabled = !dirty || saving;
    resetButton.disabled = !dirty || saving;
    form.classList.toggle('is-dirty', dirty);
  }

  /** Something moved: say what, and turn Save on. */
  function noteMove(message) {
    moves += 1;
    setDirty(true);
    setStatus(message + ' ' + (moves === 1 ? '1 change' : moves + ' changes') + ' not saved yet.', 'dirty');
  }

  /** Button states and the "this section is empty" notes, after any change. */
  function syncState() {
    Array.prototype.forEach.call(form.querySelectorAll('[data-outline-list]'), function (list) {
      var rows = rowsOf(list);
      rows.forEach(function (row, index) {
        var up = row.querySelector('[data-outline-move="up"]');
        var down = row.querySelector('[data-outline-move="down"]');
        if (up) up.disabled = index === 0;
        if (down) down.disabled = index === rows.length - 1;
      });
      var section = list.closest('[data-outline-section]');
      var note = section && section.querySelector('[data-outline-empty]');
      if (note) note.hidden = rows.length > 0;
    });

    var sections = Array.prototype.slice.call(sectionList.children);
    sections.forEach(function (section, index) {
      var up = section.querySelector('[data-outline-head] [data-outline-move="up"]');
      var down = section.querySelector('[data-outline-head] [data-outline-move="down"]');
      if (up) up.disabled = index === 0;
      if (down) down.disabled = index === sections.length - 1;
    });
  }

  /** Each class's menu must name the section it is actually in. */
  function syncPicks() {
    Array.prototype.forEach.call(sectionList.querySelectorAll('[data-outline-lesson]'), function (row) {
      var pick = row.querySelector('[data-outline-pick]');
      var list = row.parentElement;
      if (pick && list && list.hasAttribute('data-outline-list')) {
        pick.value = list.getAttribute('data-folder') || '';
      }
    });
  }

  /** Swap an item with its neighbour inside its own list. */
  function moveItem(item, direction, keepFocus) {
    var list = item.parentElement;
    if (!list) return;
    var sibling = direction < 0 ? item.previousElementSibling : item.nextElementSibling;
    if (!sibling || !sibling.hasAttribute(list === sectionList ? 'data-outline-section' : 'data-outline-lesson')) {
      return;
    }
    if (direction < 0) list.insertBefore(item, sibling);
    else list.insertBefore(sibling, item);
    syncPicks();
    syncState();
    var what = item.hasAttribute('data-outline-lesson') ? 'class' : 'section';
    noteMove('Moved the ' + what + ' “' + itemTitle(item) + '” ' + (direction < 0 ? 'up' : 'down') + '.');
    if (keepFocus) {
      // Focus follows the row so the next arrow key moves the same thing;
      // a mouse click leaves focus where it was.
      var handle = item.querySelector('[data-outline-handle]');
      if (handle) handle.focus();
    }
  }

  function moveBetweenSections(row, pick) {
    var target = form.querySelector('[data-outline-list][data-folder="' + pick.value + '"]');
    if (!target || target === row.parentElement) return;
    target.appendChild(row);
    syncPicks();
    syncState();
    noteMove('Moved “' + itemTitle(row) + '” to ' + listName(target) + '.');
  }

  /* ------------------------------------------------------------- controls */

  form.addEventListener('click', function (event) {
    var button = event.target.closest('[data-outline-move]');
    if (!button) return;
    var item = button.closest('[data-outline-lesson], [data-outline-section]');
    if (!item) return;
    moveItem(item, button.getAttribute('data-outline-move') === 'up' ? -1 : 1);
  });

  form.addEventListener('change', function (event) {
    var pick = event.target.closest('[data-outline-pick]');
    if (!pick) return;
    var row = pick.closest('[data-outline-lesson]');
    if (!row) return;
    moveBetweenSections(row, pick);
  });

  form.addEventListener('keydown', function (event) {
    var handle = event.target.closest('[data-outline-handle]');
    if (!handle) return;
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
    var item = handle.closest('[data-outline-lesson], [data-outline-section]');
    if (!item) return;
    event.preventDefault();
    moveItem(item, event.key === 'ArrowUp' ? -1 : 1, true);
  });

  /* --------------------------------------------------------------- drag */

  var drag = null;

  function highlight(list) {
    Array.prototype.forEach.call(form.querySelectorAll('.is-drop-target'), function (node) {
      node.classList.remove('is-drop-target');
    });
    if (list) list.classList.add('is-drop-target');
  }

  /** Which list the pointer is over — a class may cross into any section. */
  function listUnder(item, x, y) {
    if (!item.hasAttribute('data-outline-lesson')) return sectionList;
    if (typeof document.elementFromPoint !== 'function') return item.parentElement;
    var node = document.elementFromPoint(x, y);
    var list = node && node.closest('[data-outline-list]');
    return list || item.parentElement;
  }

  /** The item the dragged row should sit in front of, or null for the end. */
  function referenceAt(list, item, y) {
    var children = Array.prototype.slice.call(list.children);
    for (var i = 0; i < children.length; i += 1) {
      var child = children[i];
      if (child === item) continue;
      var box = child.getBoundingClientRect();
      if (y < box.top + box.height / 2) return child;
    }
    return null;
  }

  function isRow(node, item) {
    return node.hasAttribute(item.hasAttribute('data-outline-lesson') ? 'data-outline-lesson' : 'data-outline-section');
  }

  form.addEventListener('pointerdown', function (event) {
    var handle = event.target.closest('[data-outline-handle]');
    if (!handle || (event.button !== undefined && event.button !== 0)) return;
    var item = handle.closest('[data-outline-lesson], [data-outline-section]');
    if (!item) return;
    drag = { item: item, handle: handle, id: event.pointerId, x: event.clientX, y: event.clientY, active: false };
    if (handle.setPointerCapture) {
      try {
        handle.setPointerCapture(event.pointerId);
      } catch (error) {
        /* A pointer that is already gone cannot be captured; the drag still works. */
      }
    }
    event.preventDefault();
  });

  form.addEventListener('pointermove', function (event) {
    if (!drag || event.pointerId !== drag.id) return;
    if (!drag.active) {
      if (Math.abs(event.clientX - drag.x) < 5 && Math.abs(event.clientY - drag.y) < 5) return;
      drag.active = true;
      drag.item.classList.add('is-dragging');
    }
    event.preventDefault();

    var list = listUnder(drag.item, event.clientX, event.clientY);
    if (!list) return;
    highlight(list);
    var reference = referenceAt(list, drag.item, event.clientY);
    if (reference && !isRow(reference, drag.item)) return;
    if (reference === drag.item.nextElementSibling) return;
    list.insertBefore(drag.item, reference);
  });

  function endDrag(event) {
    if (!drag || (event.pointerId !== undefined && event.pointerId !== drag.id)) return;
    var item = drag.item;
    var wasActive = drag.active;
    if (drag.handle.releasePointerCapture) {
      try {
        drag.handle.releasePointerCapture(drag.id);
      } catch (error) {
        /* Released when the pointer left; nothing to undo. */
      }
    }
    item.classList.remove('is-dragging');
    highlight(null);
    drag = null;
    if (!wasActive) return;
    syncPicks();
    syncState();
    noteMove('Moved “' + itemTitle(item) + '”.');
  }

  form.addEventListener('pointerup', endDrag);
  form.addEventListener('pointercancel', endDrag);

  /* --------------------------------------------------------------- save */

  function collect() {
    return Array.prototype.map.call(sectionList.children, function (section) {
      var folder = section.getAttribute('data-folder');
      return {
        folder: folder ? Number(folder) : null,
        lessons: rowsOf(section).map(function (row) {
          return Number(row.getAttribute('data-lesson'));
        })
      };
    });
  }

  function showFailure(message, isConflict) {
    setStatus(message, 'error');
    if (isConflict) {
      var reload = document.createElement('a');
      reload.href = window.location.href;
      reload.textContent = ' Reload the page';
      status.appendChild(reload);
    }
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (saving) return;
    saving = true;
    saveButton.disabled = true;
    resetButton.disabled = true;
    saveButton.textContent = 'Saving…';
    setStatus('Saving…', '');

    window
      .fetch(saveUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf ? csrf.value : ''
        },
        body: JSON.stringify({ revision: revision, sections: collect() })
      })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            return { ok: response.ok, status: response.status, data: data };
          });
      })
      .then(function (result) {
        saving = false;
        saveButton.textContent = 'Save order';
        if (result.ok) {
          revision = result.data.revision || revision;
          form.setAttribute('data-revision', revision);
          moves = 0;
          setDirty(false);
          setStatus(result.data.message || 'Saved.', 'ok');
          return;
        }
        setDirty(true);
        showFailure(
          result.data.message || 'That order did not save. Try again.',
          result.status === 409
        );
      })
      .catch(function () {
        saving = false;
        saveButton.textContent = 'Save order';
        setDirty(true);
        showFailure(
          'The console could not reach the server. Your order is still on screen — try Save again.',
          false
        );
      });
  });

  resetButton.addEventListener('click', function () {
    sectionList.replaceWith(pristine.cloneNode(true));
    sectionList = form.querySelector('[data-outline-sections]');
    moves = 0;
    setDirty(false);
    syncPicks();
    syncState();
    setStatus('Back to the order you opened.', '');
    var handle = sectionList.querySelector('[data-outline-handle]');
    if (handle) handle.focus();
  });

  window.addEventListener('beforeunload', function (event) {
    if (!form.classList.contains('is-dirty')) return;
    event.preventDefault();
    event.returnValue = '';
  });

  syncPicks();
  syncState();
})();
