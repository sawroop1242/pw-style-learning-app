/** Legal page: chrome plus a scroll-spy for the "On this page" rail. */

import { mountChrome } from './ui.js';

mountChrome('');

const links = [...document.querySelectorAll('.legal-nav a[href^="#"]')];
const sections = links
  .map((link) => document.querySelector(link.getAttribute('href')))
  .filter(Boolean);

if (sections.length && links.length === sections.length) {
  const headerH = () => (document.querySelector('.site-header')?.offsetHeight || 64) + 24;

  const setActive = (id) => {
    links.forEach((link) => {
      const isActive = link.getAttribute('href') === `#${id}`;
      link.classList.toggle('is-active', isActive);
      if (isActive) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  };

  let frame = null;
  const onScroll = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      const line = window.scrollY + headerH() + 8;

      // Bottom of the page always highlights the last section.
      if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 4) {
        setActive(sections[sections.length - 1].id);
        return;
      }

      let current = sections[0];
      for (const section of sections) {
        if (section.offsetTop <= line) current = section;
      }
      setActive(current.id);
    });
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll, { passive: true });
  onScroll();
}
