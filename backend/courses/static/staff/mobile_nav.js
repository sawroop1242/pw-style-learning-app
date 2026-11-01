'use strict';

/*
 * The navigation rail on a phone.
 *
 * Django's admin hides the rail and its toggle completely below 768px, so on a
 * phone the console had no navigation at all. The CSS in staff/admin.css turns
 * the same rail into a drawer; this script makes the toggle behave like one.
 *
 * Django's toggle keeps an open/closed flag in localStorage and reads it once,
 * when its deferred script starts — before the viewport is known for sure — so
 * a first visit on a phone opens the drawer over the page, and its flag then
 * disagrees with the screen for the rest of the session. On small screens this
 * replaces the button with an identical one of its own (cloning drops the
 * listener that was bound to the old node) and toggles the drawer directly.
 * On a desktop nothing is touched and Django's own behaviour is unchanged.
 */
{
    const MOBILE = window.matchMedia('(max-width: 767px)');

    const start = () => {
        const main = document.getElementById('main');
        const nav = document.getElementById('nav-sidebar');
        const button = document.getElementById('toggle-nav-sidebar');
        if (!main || !nav || !button || !MOBILE.matches) {
            return;
        }

        const toggle = button.cloneNode(true);
        button.parentNode.replaceChild(toggle, button);

        const setOpen = (open) => {
            main.classList.toggle('shifted', open);
            toggle.setAttribute('aria-expanded', String(open));
            nav.setAttribute('aria-expanded', String(open));
        };

        toggle.addEventListener('click', () => {
            setOpen(!main.classList.contains('shifted'));
        });

        // Tapping the dimmed page, or pressing Escape, closes the drawer.
        document.addEventListener('click', (event) => {
            if (!main.classList.contains('shifted')) {
                return;
            }
            if (nav.contains(event.target) || toggle.contains(event.target)) {
                return;
            }
            setOpen(false);
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && main.classList.contains('shifted')) {
                setOpen(false);
            }
        });

        // Closed until asked for, whatever the stored preference says.
        setOpen(false);
    };

    // Deferred scripts run in document order, so Django's nav_sidebar.js has
    // already bound its handler by the time this runs.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
}
