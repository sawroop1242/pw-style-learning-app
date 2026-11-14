/**
 * The admin console in a real browser.
 *
 * Everything else that checks the console reads the stylesheet and the
 * rendered HTML, and both of them looked perfect while the page on screen was
 * wrong: a `600px` width from Django's own dashboard rules, a flex item whose
 * padding sat outside its `max-width`, a `.module` surface painted inside the
 * navy rail, a white wordmark on a white card. None of those are visible in
 * the CSS text — they are what the browser computes when the two meet.
 *
 * This runs Chromium against a live server and asks the browser:
 *
 *   · does the document scroll sideways at any width?
 *   · is any text drawn below WCAG AA against the background it actually
 *     lands on?
 *   · is the top bar's height the value the page reserves for it, so the
 *     first heading is not underneath it?
 *   · does the rail keep its dark surface, and its own contrast?
 *   · does the sign-in card render its wordmark legibly?
 *
 * Usage:
 *   python manage.py runserver 8010          # in backend/, with data seeded
 *   node admin-render.js                     # ADMIN_BASE / ADMIN_USER /
 *                                            # ADMIN_PASSWORD override
 *
 * It is opt-in, not part of `node markup.js`: it needs a server, an account
 * and a Chromium binary, none of which the other checks assume. See
 * docs/ADMIN_CONSOLE.md for how CI runs it.
 */
const puppeteer = require('puppeteer-core');

const BASE = process.env.ADMIN_BASE || 'http://127.0.0.1:8010';
const USER = process.env.ADMIN_USER || 'admin';
const PASSWORD = process.env.ADMIN_PASSWORD || 'admin12345';
const EXECUTABLE = process.env.CHROME_PATH || '/tmp/chromium';

const PAGES = [
  ['dashboard', '/admin/'],
  ['course list', '/admin/courses/course/'],
  ['filtered list', '/admin/courses/course/?is_published__exact=1'],
  ['course add', '/admin/courses/course/add/'],
  ['course change', '/admin/courses/course/1/change/'],
  ['history', '/admin/courses/course/1/history/'],
  ['delete', '/admin/courses/course/1/delete/'],
  ['users', '/admin/auth/user/'],
  ['password change', '/admin/password_change/']
];

const WIDTHS = [1440, 1024, 390];

let failures = 0;
const fail = (where, message) => {
  failures += 1;
  console.log(`  ✗ ${where}: ${message}`);
};

/* ----------------------------- colour maths ----------------------------- */

const parseColour = (value) => {
  const m = value.match(/[\d.]+/g);
  return m ? m.map(Number) : null;
};

const luminance = ([r, g, b]) => {
  const f = (v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
};

const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

/**
 * The background a piece of text actually lands on, walking up until something
 * opaque paints. A gradient returns null: the colour cannot be measured from
 * computed styles, and guessing it produces false alarms — which is how an
 * audit stops being trusted.
 */
const paintedBackground = (el) => {
  for (let node = el; node; node = node.parentElement) {
    if (getComputedStyle(node).backgroundImage !== 'none') return null;
    const rgba = parseColour(getComputedStyle(node).backgroundColor);
    if (!rgba || rgba.length === 3 || rgba[3] > 0.5) {
      if (rgba) return rgba.slice(0, 3);
    }
  }
  return [255, 255, 255];
};

/* ------------------------------- the page ------------------------------- */

const inspect = () => {
  /* Everything below this line runs inside the page, so it cannot call the
   * Node helpers above — a bare `parseColour` here is a ReferenceError, not a
   * check. The two colour functions are therefore defined locally. */
  const rgba = (value) => {
    const m = value.match(/[\d.]+/g);
    return m ? m.map(Number) : null;
  };
  const paint = (el) => {
    for (let node = el; node; node = node.parentElement) {
      if (getComputedStyle(node).backgroundImage !== 'none') return null;
      const c = rgba(getComputedStyle(node).backgroundColor);
      if (!c || c.length === 3 || c[3] > 0.5) {
        if (c) return c.slice(0, 3);
      }
    }
    return [255, 255, 255];
  };
  const contrastOf = (a, b) => {
    const lum = ([r, g, bl]) => {
      const f = (v) => {
        v /= 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bl);
    };
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };

  const issues = { overflow: [], contrast: [], bars: [] };

  for (const el of document.querySelectorAll('body *')) {
    const style = getComputedStyle(el);
    if (style.position === 'fixed' || style.display === 'none' || style.visibility === 'hidden') continue;
    const box = el.getBoundingClientRect();
    if (box.width === 0 && box.height === 0) continue;
    // Off-canvas (the closed rail drawer) is not on screen.
    if (box.right <= 0 || box.left >= window.innerWidth) continue;

    let clipped = false;
    for (let p = el.parentElement; p; p = p.parentElement) {
      if (getComputedStyle(p).overflowX !== 'visible') { clipped = true; break; }
    }
    if (box.right > window.innerWidth + 1 && !clipped) {
      const id = `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}.${[...el.classList].slice(0, 2).join('.')}`;
      issues.overflow.push(`${id} runs to ${Math.round(box.right)}px`);
    }

    const own = [...el.childNodes]
      .filter((n) => n.nodeType === 3 && n.textContent.trim())
      .map((n) => n.textContent.trim())
      .join(' ');
    if (!own || !el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue;

    const fg = rgba(style.color);
    const bg = fg && (fg.length === 3 || fg[3] > 0.5) ? paint(el) : null;
    if (!fg || !bg) continue;

    const size = parseFloat(style.fontSize);
    const large = size >= 24 || (size >= 18.66 && parseInt(style.fontWeight, 10) >= 700);
    // A decorative glyph marked aria-hidden only has to clear 3:1 (a UI mark);
    // real text has to clear 4.5:1 (or 3:1 when large).
    const decorative = el.getAttribute('aria-hidden') === 'true';
    const floor = decorative ? 3 : large ? 3 : 4.5;
    const ratio = contrastOf(fg.slice(0, 3), bg);
    if (ratio < floor) {
      const id = `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}.${[...el.classList].slice(0, 2).join('.')}`;
      issues.contrast.push(`"${own.slice(0, 30)}" ${id} ${ratio.toFixed(2)}:1 (needs ${floor})`);
    }
  }

  // The bar is `position: fixed`; the page must reserve its real height.
  const header = document.getElementById('header');
  const main = document.getElementById('main');
  if (header && main) {
    const h = Math.round(header.getBoundingClientRect().height);
    const reserved = Math.round(parseFloat(getComputedStyle(main).paddingTop));
    if (Math.abs(h - reserved) > 1) {
      issues.bars.push(`header is ${h}px tall but the page reserves ${reserved}px`);
    }
    const h1 = document.querySelector('#content h1');
    if (h1 && h1.getBoundingClientRect().top < h - 1) {
      issues.bars.push(`the page title starts at ${Math.round(h1.getBoundingClientRect().top)}px, under a ${h}px bar`);
    }
  }

  return issues;
};

/* -------------------------------- runner -------------------------------- */

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EXECUTABLE,
    headless: 'shell',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--font-render-hinting=none'],
    defaultViewport: { width: 1440, height: 900 }
  });

  let account;
  try {
    account = await browser.newPage();
    await account.setCacheEnabled(false);
    const res = await account.goto(`${BASE}/admin/login/`, { waitUntil: 'networkidle0' });
    if (!res || res.status() !== 200) throw new Error(`login page answered ${res ? res.status() : 'nothing'}`);

    /* Signed out first: this page has its own layout, and it is the screen that
     * showed a white wordmark on a white card. */
    for (const width of [1440, 390]) {
      await account.setViewport({ width, height: 900 });
      await account.reload({ waitUntil: 'networkidle0' });
      /* The wordmark is white on purpose: it sits on the navy backdrop, and
       * the card below it is white. So the check is not "is the colour white"
       * but "what does the browser say is behind it" — which is exactly the
       * question that failed when a grey `#container` slab was painted there. */
      const login = await account.evaluate(() => {
        const brand = document.querySelector('#site-name a');
        const card = document.querySelector('#content');
        const behind = (el) => {
          for (let node = el; node; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (style.backgroundImage !== 'none') return { kind: 'gradient', value: style.backgroundImage };
            const m = style.backgroundColor.match(/[\d.]+/g);
            if (m && (m.length === 3 || Number(m[3]) > 0.5)) return { kind: 'colour', value: m.slice(0, 3).map(Number) };
          }
          return { kind: 'none', value: null };
        };
        return {
          backdrop: getComputedStyle(document.body).backgroundImage.slice(0, 20),
          brandColour: getComputedStyle(brand).color.match(/[\d.]+/g).slice(0, 3).map(Number),
          brandOn: behind(brand),
          cardRadius: getComputedStyle(card).borderTopLeftRadius,
          brandVisible: brand.checkVisibility()
        };
      });
      console.log(`login @${width}`);
      if (!login.backdrop.startsWith('radial-gradient')) fail('login', `no navy backdrop (${login.backdrop})`);
      if (!login.brandVisible) fail('login', 'the wordmark is not visible');
      if (login.brandOn.kind === 'colour' && luminance(login.brandOn.value) > 0.5) {
        fail('login', `the wordmark is drawn on a light surface (${login.brandOn.value.join(',')})`);
      }
      if (login.brandOn.kind === 'none') fail('login', 'nothing is painted behind the wordmark');
      if (login.cardRadius === '0px') fail('login', 'the card lost its radius');
    }

    /* Now signed in. */
    await account.goto(`${BASE}/admin/login/`, { waitUntil: 'networkidle0' });
    await account.type('#id_username', USER);
    await account.type('#id_password', PASSWORD);
    await Promise.all([
      account.waitForNavigation({ waitUntil: 'networkidle0' }),
      account.click('input[type=submit]')
    ]);
    if (!account.url().includes('/admin/')) throw new Error(`sign-in did not land on the console (${account.url()})`);

    for (const width of WIDTHS) {
      await account.setViewport({ width, height: 900 });
      for (const [name, path] of PAGES) {
        const res = await account.goto(`${BASE}${path}`, { waitUntil: 'networkidle0' });
        const where = `${name} @${width}`;
        if (!res || res.status() !== 200) {
          fail(where, `answered ${res ? res.status() : 'nothing'}`);
          continue;
        }
        const issues = await account.evaluate(inspect);
        const scroll = await account.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        if (scroll > 0) fail(where, `the page scrolls sideways by ${scroll}px`);
        for (const line of issues.overflow) fail(where, `overflow: ${line}`);
        for (const line of issues.contrast) fail(where, `contrast: ${line}`);
        for (const line of issues.bars) fail(where, `bar: ${line}`);
        if (!issues.overflow.length && !issues.contrast.length && !issues.bars.length && scroll <= 0) {
          console.log(`  ✓ ${where}`);
        }
      }
    }

    /* The rail has to stay a dark surface. A generic `.module` card rule once
     * painted every group white inside it. */
    await account.setViewport({ width: 1440, height: 900 });
    await account.goto(`${BASE}/admin/`, { waitUntil: 'networkidle0' });
    /* Django's dashboard layout (`#content { width: 600px }`, floating columns)
     * can survive a grid and still leave the page technically fine — no
     * overflow, no contrast failure — while the main column is squeezed into a
     * fifth of the screen and the activity column sits outside the box. Width
     * and overlap are therefore asserted, not inferred. */
    const layout = await account.evaluate(() => {
      const main = document.querySelector('#content-main');
      const related = document.querySelector('#content-related');
      const content = document.querySelector('#content');
      const box = (el) => (el ? el.getBoundingClientRect() : null);
      const m = box(main), r = box(related), c = box(content);
      return {
        mainWidth: m ? Math.round(m.width) : 0,
        contentWidth: c ? Math.round(c.width) : 0,
        relatedLeft: r ? Math.round(r.left) : null,
        mainRight: m ? Math.round(m.right) : null,
      };
    });
    if (layout.contentWidth && layout.mainWidth / layout.contentWidth < 0.55) {
      fail('dashboard', `the work column is ${layout.mainWidth}px of ${layout.contentWidth}px`);
    }
    if (layout.relatedLeft !== null && layout.mainRight !== null && layout.relatedLeft < layout.mainRight - 1) {
      fail('dashboard', 'the activity column overlaps the work column');
    }

    const rail = await account.evaluate(() => {
      const group = document.querySelector('#nav-sidebar .ss-nav-group');
      const sidebar = document.querySelector('#nav-sidebar');
      return {
        groupBg: group ? getComputedStyle(group).backgroundColor : 'missing',
        sidebarBg: getComputedStyle(sidebar).backgroundColor
      };
    });
    if (rail.sidebarBg !== 'rgb(14, 23, 41)') fail('rail', `sidebar is ${rail.sidebarBg}, not navy`);
    if (rail.groupBg !== 'rgba(0, 0, 0, 0)') fail('rail', `a group paints ${rail.groupBg} inside the rail`);

  } catch (err) {
    failures += 1;
    console.log(`✗ ${err.message}`);
  } finally {
    await browser.close();
  }

  console.log(failures === 0 ? '\nADMIN RENDER OK' : `\n${failures} problem(s)`);
  process.exit(failures === 0 ? 0 : 1);
})();
