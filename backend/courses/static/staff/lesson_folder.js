/**
 * Lesson admin: every section, grouped by the batch it belongs to.
 *
 * The section dropdown used to be a flat list of every folder in the
 * catalogue, which made it impossible to tell which batch a section came
 * from. It is still one list — nothing is hidden or disabled, so you can pick
 * a section from any batch — but the options are grouped by batch, the batch
 * you selected comes first, and each group is labelled with its batch.
 *
 * Sections belong to exactly one batch, so picking a section from another
 * batch moves the batch field to match, and says so. Without that the form
 * would save and then fail the model's "folder must belong to the same course
 * as the lesson" check, which is a worse way to find out.
 */
(function () {
  'use strict';

  var NOTE_ID = 'lesson-folder-note';

  function wire() {
    var course = document.getElementById('id_course');
    var folder = document.getElementById('id_folder');
    if (!course || !folder) return;

    // The empty choice stays and stays first: a lesson may sit at the top of
    // its batch with no section.
    var placeholder = folder.querySelector('option[value=""]');

    var note = document.getElementById(NOTE_ID);
    if (!note) {
      note = document.createElement('p');
      note.id = NOTE_ID;
      note.className = 'help';
      note.style.marginTop = '6px';
      folder.parentNode.appendChild(note);
    }

    function batchTitles() {
      var titles = {};
      Array.prototype.forEach.call(course.options, function (option) {
        if (option.value) titles[option.value] = option.text.trim();
      });
      return titles;
    }

    function groupOptions() {
      var groups = {};
      var order = [];
      Array.prototype.forEach.call(folder.options, function (option) {
        if (!option.value) return;
        var key = option.getAttribute('data-course') || '';
        if (!groups[key]) {
          groups[key] = [];
          order.push(key);
        }
        groups[key].push(option);
      });
      return { groups: groups, order: order };
    }

    function rebuild(selectedCourse) {
      var titles = batchTitles();
      var collected = groupOptions();
      var keep = folder.value;

      // Drop the previous optgroups; the options themselves are moved, not
      // recreated, so their values, labels and selected state survive.
      Array.prototype.slice.call(folder.querySelectorAll('optgroup')).forEach(function (group) {
        group.parentNode.removeChild(group);
      });

      var keys = collected.order.slice();
      if (selectedCourse) {
        keys.sort(function (a, b) {
          if (a === selectedCourse) return -1;
          if (b === selectedCourse) return 1;
          return (titles[a] || a).localeCompare(titles[b] || b);
        });
      } else {
        keys.sort(function (a, b) {
          return (titles[a] || a).localeCompare(titles[b] || b);
        });
      }

      keys.forEach(function (key) {
        var label = titles[key] || 'Unassigned batch';
        if (selectedCourse && key === selectedCourse) {
          label = 'This batch — ' + label;
        } else {
          label = 'Other batch — ' + label;
        }
        var group = document.createElement('optgroup');
        group.label = label;
        collected.groups[key].forEach(function (option) {
          group.appendChild(option);
        });
        folder.appendChild(group);
      });

      // Re-select after moving nodes; browsers drop it when the parent moves.
      folder.value = keep;

      if (placeholder) {
        placeholder.textContent = selectedCourse
          ? '— no section, this class sits at the top of the batch —'
          : '— no section —';
      }
    }

    function currentLabel() {
      var option = folder.options[folder.selectedIndex];
      if (!option || !option.value) return '';
      return option.text.trim();
    }

    function apply() {
      rebuild(course.value);
      note.textContent = '';
    }

    course.addEventListener('change', apply);

    folder.addEventListener('change', function () {
      var option = folder.options[folder.selectedIndex];
      if (!option || !option.value) {
        apply();
        return;
      }
      var owner = option.getAttribute('data-course') || '';
      if (course.value && owner && owner !== course.value) {
        course.value = owner;
        rebuild(course.value);
        note.textContent =
          'The batch changed to match “' + currentLabel() + '”, because a ' +
          'section belongs to one batch.';
      } else {
        apply();
      }
    });

    apply();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }
})();
