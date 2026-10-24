# Front-end checks

Dev-only verification for `frontend/`. Nothing here is shipped: the folder is
outside the served directory and only `jsdom`/`css-tree` are installed, on
demand.

The front end has no build step, so there is no test runner in the app itself.
These scripts load the real pages in jsdom, execute the real modules, and assert
on the DOM the user would see.

```bash
cd tools/checks
npm install            # jsdom + css-tree, dev only

node check.js          # every page renders content, shell and no console errors
node a11y.js           # h1, labels, accessible names, aria-controls, duplicate ids
node interact.js       # drawer, filters, the exam window end to end, likes
node css.js            # every stylesheet parses; every class used exists
```

`check.js`, `a11y.js`, `interact.js` and `css.js` run **offline** — the network
is unreachable on purpose, which is what exercises the bundled fixture fallback.

## Live checks

`live.js` does the opposite: it points the pages at a running API and asserts
that server rows are what render. Start both servers first:

```bash
# terminal 1 — API
cd backend
ENVIRONMENT=development DEBUG=true SECRET_KEY=dev-only-not-secret-key-1234567890abcdef \
  python manage.py migrate && python manage.py seed_demo
ENVIRONMENT=development DEBUG=true SECRET_KEY=dev-only-not-secret-key-1234567890abcdef \
  python manage.py runserver 127.0.0.1:8000

# terminal 2 — site with /api proxied
python3 tools/serve.py --port 8080

# terminal 3
cd tools/checks && node live.js
```

Point it elsewhere with `CHECK_ORIGIN=https://staging.example node live.js`.

`seed_demo` creates a small catalogue — six batches, four test series, five
timed tests with questions and choices — and is safe to re-run. `--clear`
removes exactly the rows it made. See the command's docstring for why the data
is shaped the way it is.

## What these scripts do not cover

- **No real browser.** jsdom has no layout engine, so stacking, overflow,
  sticky positioning and painted contrast are not verified here. They were
  checked against the design references by hand.
- **No cross-browser behaviour.** `color-mix()`, `:has()` and sticky headers
  degrade differently in older engines.
- **`live.js` needs seeded data.** Against an empty database it fails at the
  first assertion by design.
