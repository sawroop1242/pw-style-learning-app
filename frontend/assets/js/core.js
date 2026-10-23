/**
 * StudySpace core — API client, storage, formatting and DOM helpers.
 *
 * The site is a static PWA. Every data read goes through `live()` which tries
 * the Django API first and silently falls back to the bundled fixtures so the
 * UI is fully explorable without a backend (GitHub Pages, offline preview).
 */

const META = document.querySelector('meta[name="api-base"]');
export const API_BASE = (META?.content || '/api').replace(/\/$/, '');

const K = {
  access: 'studyspace.access',
  refresh: 'studyspace.refresh',
  user: 'studyspace.user',
  preview: 'studyspace.preview',
  attempt: 'studyspace.attempt'
};

/* ------------------------------------------------------------------ */
/* Storage                                                             */
/* ------------------------------------------------------------------ */

const safeParse = (raw) => {
  try { return raw ? JSON.parse(raw) : null; } catch { return null; }
};

export const storage = {
  get access() { return localStorage.getItem(K.access); },
  get refresh() { return localStorage.getItem(K.refresh); },
  get user() { return safeParse(localStorage.getItem(K.user)); },
  set session({ access, refresh, user }) {
    if (access) localStorage.setItem(K.access, access);
    if (refresh) localStorage.setItem(K.refresh, refresh);
    if (user) localStorage.setItem(K.user, JSON.stringify(user));
  },
  /** In-progress test attempt (this tab only). */
  get attempt() { return sessionStorage.getItem(K.attempt); },
  set attempt(value) {
    if (value) sessionStorage.setItem(K.attempt, value);
    else sessionStorage.removeItem(K.attempt);
  },
  clear() {
    localStorage.removeItem(K.access);
    localStorage.removeItem(K.refresh);
    localStorage.removeItem(K.user);
    sessionStorage.removeItem(K.attempt);
  }
};

export const isSignedIn = () => Boolean(storage.access);

/**
 * True when the API cannot be reached at all, as opposed to answering with a
 * real error.
 *
 * A static preview has no API behind it: `POST /api/...` is answered by the
 * file server with 501 or 404, not with a network failure. Treating those as
 * "the server said no" used to surface `Request failed (501)` on the sign-in
 * form. 404/405/408 and 5xx all mean "there is no working API here", which is
 * exactly the case the offline demo exists for. 400/401/403/429 are real
 * answers and are never swallowed by this helper.
 */
export const isUnreachable = (err) =>
  !err ||
  err.status === 0 ||
  err.status === 404 ||
  err.status === 405 ||
  err.status === 408 ||
  err.status >= 500;

/** True once any read has fallen back to fixtures. */
export const isPreview = () => sessionStorage.getItem(K.preview) === '1';
const markPreview = () => sessionStorage.setItem(K.preview, '1');

/* ------------------------------------------------------------------ */
/* HTTP                                                                */
/* ------------------------------------------------------------------ */

export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

function messageFrom(data, status) {
  if (!data) return `Request failed (${status})`;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  if (data.non_field_errors) return data.non_field_errors[0];
  const first = Object.entries(data).find(([, v]) => v);
  if (first) {
    const [field, value] = first;
    const text = Array.isArray(value) ? value[0] : value;
    return `${field.replace(/_/g, ' ')}: ${text}`;
  }
  return `Request failed (${status})`;
}

async function refreshToken() {
  const refresh = storage.refresh;
  if (!refresh) throw new ApiError('No refresh token', 401);
  const res = await fetch(`${API_BASE}/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh })
  });
  if (!res.ok) {
    storage.clear();
    throw new ApiError('Session expired', 401);
  }
  const data = await res.json();
  storage.session = { access: data.access, refresh: data.refresh || refresh };
  return data.access;
}

export async function request(path, { method = 'GET', body, retried = false, timeout = 12000 } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (storage.access) headers.Authorization = `Bearer ${storage.access}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal
    });
  } catch (err) {
    clearTimeout(timer);
    if (err.name === 'AbortError') throw new ApiError('The request timed out.', 408);
    throw new ApiError('Network unavailable.', 0);
  }
  clearTimeout(timer);

  if (res.status === 401 && !retried && storage.refresh) {
    try {
      await refreshToken();
      return request(path, { method, body, retried: true, timeout });
    } catch {
      storage.clear();
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }
  }

  const type = res.headers.get('content-type') || '';
  const data = type.includes('application/json') ? await res.json() : await res.text();

  if (!res.ok) throw new ApiError(messageFrom(data, res.status), res.status, data);
  return data;
}

/**
 * Read a collection with fixture fallback.
 * `path` is the API route; `fixture` is used when the API is unreachable.
 */
export async function live(path, fixture, { timeout = 2500 } = {}) {
  try {
    const data = await request(path, { timeout });
    return { data, live: true };
  } catch (err) {
    if (err.status === 401 && path.startsWith('/courses')) {
      // Fall through to fixtures for public pages.
    }
    if (err.status === 0 || err.status === 404 || err.status === 408 || err.status >= 500) {
      markPreview();
      return { data: fixture, live: false };
    }
    throw err;
  }
}

/* ------------------------------------------------------------------ */
/* Auth                                                               */
/* ------------------------------------------------------------------ */

export const auth = {
  async login({ username, password }) {
    const data = await request('/token/', {
      method: 'POST',
      body: { username_or_email: username, password }
    });
    storage.session = { access: data.access, refresh: data.refresh };
    const me = await request('/auth/me/').catch(() => null);
    storage.session = { user: me || { username } };
    return me || { username };
  },

  async register({ username, email, password, passwordConfirm }) {
    await request('/auth/register/', {
      method: 'POST',
      body: { username, email, password, password_confirm: passwordConfirm }
    });
    return auth.login({ username, password });
  },

  async logout() {
    const refresh = storage.refresh;
    if (refresh) {
      await request('/auth/logout/', { method: 'POST', body: { refresh } }).catch(() => {});
    }
    storage.clear();
  }
};

/* ------------------------------------------------------------------ */
/* Formatting                                                         */
/* ------------------------------------------------------------------ */

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0
});

export const money = (value) => (Number(value) > 0 ? inr.format(Number(value)) : 'Free');

export const number = (value) => new Intl.NumberFormat('en-IN').format(Number(value) || 0);

export function compact(value) {
  const n = Number(value) || 0;
  if (n >= 10000000) return `${(n / 10000000).toFixed(1).replace(/\.0$/, '')}Cr`;
  if (n >= 100000) return `${(n / 100000).toFixed(1).replace(/\.0$/, '')}L`;
  if (n >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  return String(n);
}

export function discountPercent(price, mrp) {
  if (!mrp || mrp <= price) return 0;
  return Math.round(((mrp - price) / mrp) * 100);
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function shortDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function longDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function countdown(iso) {
  const diff = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(diff)) return '';
  if (diff <= 0) return 'Started';
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  if (days > 0) return `Starts in ${days}d`;
  if (hours > 0) return `Starts in ${hours}h`;
  return 'Starts soon';
}

export const mmss = (totalSeconds) => {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (v) => String(v).padStart(2, '0');
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
};

export const initials = (name = '') =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'S';

export const initialsFrom = initials;

/* ------------------------------------------------------------------ */
/* DOM helpers                                                        */
/* ------------------------------------------------------------------ */

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/** Escape untrusted text before interpolating into innerHTML. */
export function esc(value = '') {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[ch]);
}

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function debounce(fn, wait = 220) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

/* ------------------------------------------------------------------ */
/* Row adapters: API payloads → card view models                      */
/* ------------------------------------------------------------------ */

export const adaptCourse = (row = {}) => ({
  id: row.id,
  slug: row.slug || `course-${row.id}`,
  title: row.title || 'Untitled batch',
  subject: row.subject || 'General',
  exam: row.exam || row.subject || '',
  durationMonths: row.duration_months ?? row.durationMonths ?? null,
  faculty: row.faculty || [],
  lessons: row.lessons ?? row.lesson_count ?? 0,
  tests: row.tests ?? row.quiz_count ?? 0,
  learners: row.learners ?? row.student_count ?? 0,
  rating: Number(row.rating ?? 4.7),
  ratingCount: row.ratingCount ?? row.rating_count ?? 0,
  language: row.language || 'English',
  price: Number(row.price ?? 0),
  mrp: Number(row.mrp ?? 0),
  pricing_mode: row.pricing_mode || (Number(row.price) > 0 ? 'paid' : 'free'),
  badge: row.badge || null
});

export const adaptTest = (row = {}) => ({
  id: row.id,
  title: row.title || 'Untitled test',
  exam: row.exam || 'General',
  kind: row.kind || 'Mock',
  questions: row.questions ?? row.question_count ?? 0,
  duration: row.duration ?? row.duration_minutes ?? 0,
  attempts: row.attempts ?? row.attempt_count ?? 0,
  startsAt: row.startsAt ?? row.starts_at ?? null,
  price: Number(row.price ?? 0),
  badge: row.badge || null
});

export const qsParam = (key) => new URLSearchParams(location.search).get(key);

export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

export const prefersReducedMotion = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;
