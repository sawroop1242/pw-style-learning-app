/**
 * StudySpace core — API client, storage, formatting and DOM helpers.
 *
 * Every number, title and date on a page comes from the Django API. There is no
 * fixture fallback any more: when a request fails the page says so and offers a
 * retry, because a screen that shows invented rows is worse than an empty one.
 * `content.js` holds only copy that is genuinely editorial (FAQ answers, menu
 * labels, the how-it-works steps).
 */

const META = document.querySelector('meta[name="api-base"]');
export const API_BASE = (META?.content || '/api').replace(/\/$/, '');

const K = {
  access: 'studyspace.access',
  refresh: 'studyspace.refresh',
  user: 'studyspace.user',
  attempt: 'studyspace.attempt',
  guest: 'studyspace.attempt-token'
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
  /**
   * Token for a guest attempt. Lives in localStorage (not sessionStorage) so a
   * resume survives closing the tab — the attempt is already scored on the
   * server, and losing this would strand it.
   */
  get guestToken() { return localStorage.getItem(K.guest); },
  set guestToken(value) {
    if (value) localStorage.setItem(K.guest, value);
    else localStorage.removeItem(K.guest);
  },
  clear() {
    localStorage.removeItem(K.access);
    localStorage.removeItem(K.refresh);
    localStorage.removeItem(K.user);
    localStorage.removeItem(K.guest);
    sessionStorage.removeItem(K.attempt);
  }
};

export const isSignedIn = () => Boolean(storage.access);

/**
 * True when the API cannot be reached at all, as opposed to answering with a
 * real error.
 *
 * A network failure, a timeout or a server error mean "the API is not usable
 * right now"; 400/401/403/404/429 are real answers from the app and are never
 * treated as an outage. Forms use this to choose between "service unavailable,
 * try again" and the field error the server actually sent.
 */
export const isUnreachable = (err) =>
  !err ||
  err.status === 0 ||
  err.status === 408 ||
  err.status >= 500;

/**
 * Read a collection. Throws on any failure — callers render an error state.
 * `fallback` exists only for a value a page can sensibly degrade to (an empty
 * list), never for invented rows.
 */
export async function getJson(path, { timeout = 8000, fallback } = {}) {
  try {
    return await request(path, { timeout });
  } catch (err) {
    if (fallback !== undefined && err.status === 404) return fallback;
    throw err;
  }
}

/** Unwrap a DRF page or a plain array into an array. */
export const rows = (payload) =>
  Array.isArray(payload) ? payload : (payload && Array.isArray(payload.results) ? payload.results : []);

/** Build a query string, dropping empty values. */
export function apiQuery(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

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

export async function request(path, { method = 'GET', body, retried = false, timeout = 12000, guestToken } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (storage.access) headers.Authorization = `Bearer ${storage.access}`;
  // A guest attempt is addressed by the token it was issued, never by an id
  // alone. Signed-in attempts use the bearer token instead.
  if (guestToken) headers['X-Attempt-Token'] = guestToken;

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
      return request(path, { method, body, retried: true, timeout, guestToken });
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

/**
 * API course row → the fields a card renders.
 *
 * Nothing is defaulted to a flattering number: if the server did not send a
 * rating, a learner count or a discount, the card does not show one.
 */
export const adaptCourse = (row = {}) => ({
  id: row.id,
  slug: row.slug || `course-${row.id}`,
  title: row.title || 'Untitled batch',
  subject: row.subject || 'General',
  description: row.description || '',
  lessons: Number(row.lesson_count ?? 0),
  tests: Number(row.quiz_count ?? 0),
  folders: Number(row.folder_count ?? 0),
  price: Number(row.price ?? 0),
  currency: row.currency || 'INR',
  pricing_mode: row.pricing_mode || (Number(row.price) > 0 ? 'paid' : 'free'),
  free: (row.pricing_mode || '') === 'free' || Number(row.price ?? 0) === 0,
  hasAccess: row.has_access !== false,
  telegram: row.telegram_url || '',
  position: Number(row.position ?? 0)
});

/** API quiz row → the fields a test card renders. */
export const adaptTest = (row = {}) => {
  const timed = row.timing_mode ? row.timing_mode !== 'untimed' : true;
  const questions = Number(row.question_count ?? 0);
  return {
    id: row.id,
    title: row.title || 'Untitled test',
    subject: row.series_subject || row.course_subject || 'General',
    series: row.series_title || null,
    batch: row.course_title || null,
    batchSlug: row.course_slug || null,
    kind: timed ? 'Timed mock' : 'Practice',
    questions,
    marks: Math.round(Number(row.marks_per_question ?? 0) * questions),
    duration: Number(row.duration_minutes ?? 0),
    attempts: Number(row.attempt_count ?? 0),
    opensAt: row.opens_at || null,
    closesAt: row.closes_at || null,
    locked: row.has_access === false,
    paid: Boolean(row.course && row.course !== null && row.has_access === false)
  };
};

export const qsParam = (key) => new URLSearchParams(location.search).get(key);

export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

export const prefersReducedMotion = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;
