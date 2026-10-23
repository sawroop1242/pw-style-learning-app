/** Sign in / sign up with a working preview fallback. */

import { $, esc, auth, storage } from './core.js';
import { mountSprite, toast } from './ui.js';

mountSprite();

const state = { mode: 'signin' };

/* ------------------------------------------------------------------ */
/* Tabs                                                               */
/* ------------------------------------------------------------------ */

function setMode(mode) {
  state.mode = mode;
  const isSignin = mode === 'signin';

  $('#tab-signin').setAttribute('aria-selected', String(isSignin));
  $('#tab-signup').setAttribute('aria-selected', String(!isSignin));
  $('#form-signin').hidden = !isSignin;
  $('#form-signup').hidden = isSignin;

  $('#auth-title').textContent = isSignin ? 'Welcome back' : 'Create your account';
  $('#auth-sub').textContent = isSignin
    ? 'Sign in to continue your preparation.'
    : 'Free to start. No card, no trial timer.';

  document.title = `${isSignin ? 'Sign in' : 'Create account'} — StudySpace`;
}

$('#tab-signin').addEventListener('click', () => setMode('signin'));
$('#tab-signup').addEventListener('click', () => setMode('signup'));

if (location.hash === '#register') setMode('signup');

/* ------------------------------------------------------------------ */
/* Password visibility                                                */
/* ------------------------------------------------------------------ */

document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-toggle-pass]');
  if (!btn) return;
  const input = document.getElementById(btn.dataset.togglePass);
  if (!input) return;
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  btn.innerHTML = `<svg><use href="#i-${show ? 'eye-off' : 'eye'}"/></svg>`;
});

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

function fail(id, message) {
  const node = $(id);
  node.textContent = message;
  node.hidden = false;
}

function clearError(id) {
  const node = $(id);
  if (!node) return;
  node.hidden = true;
  node.textContent = '';
}

function busy(button, isBusy, label) {
  button.disabled = isBusy;
  if (isBusy) {
    button.dataset.label = button.textContent;
    button.textContent = label || 'Please wait…';
  } else if (button.dataset.label) {
    button.textContent = button.dataset.label;
  }
}

/** The preview has no backend; fall back to a local demo session. */
function demoSession(name) {
  storage.session = {
    access: 'demo-access-token',
    refresh: 'demo-refresh-token',
    user: { username: name, email: `${name}@example.com`, demo: true }
  };
}

function goNext() {
  const next = new URLSearchParams(location.search).get('next');
  // Only same-site pages, and only a plain file name plus optional query.
  const safe = next && /^[\w.-]+\.html(\?[^<>"'\s]*)?$/.test(next);
  location.href = safe ? next : 'dashboard.html';
}

/* ------------------------------------------------------------------ */
/* Sign in                                                            */
/* ------------------------------------------------------------------ */

$('#form-signin').addEventListener('submit', async (e) => {
  e.preventDefault();
  clearError('#login-error');

  const form = new FormData(e.currentTarget);
  const username = String(form.get('username') || '').trim();
  const password = String(form.get('password') || '');

  if (!username || !password) {
    fail('#login-error', 'Enter both your username and password.');
    return;
  }

  const btn = $('#login-submit');
  busy(btn, true, 'Signing in…');

  try {
    const user = await auth.login({ username, password });
    toast(`Welcome back, ${user?.username || username}.`, 'success');
    setTimeout(goNext, 400);
  } catch (err) {
    if (err.status === 0) {
      // No API in the static preview — accept the demo credentials.
      demoSession(username);
      toast('Preview mode: signed in with a local demo session.', 'info', 5000);
      setTimeout(goNext, 700);
    } else if (err.status === 401 || err.status === 400) {
      fail('#login-error', 'Those details did not match an account. Check your password and try again.');
    } else {
      fail('#login-error', err.message || 'Could not sign in right now. Please try again.');
    }
  } finally {
    busy(btn, false);
  }
});

/* ------------------------------------------------------------------ */
/* Sign up                                                            */
/* ------------------------------------------------------------------ */

$('#form-signup').addEventListener('submit', async (e) => {
  e.preventDefault();
  clearError('#signup-error');

  const form = new FormData(e.currentTarget);
  const name = String(form.get('name') || '').trim();
  const email = String(form.get('email') || '').trim();
  const password = String(form.get('password') || '');
  const confirm = String(form.get('passwordConfirm') || '');
  const terms = form.get('terms');

  if (!name || !email || !password) {
    fail('#signup-error', 'Fill in every field to create your account.');
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    fail('#signup-error', 'That email address does not look right.');
    return;
  }
  if (password.length < 8) {
    fail('#signup-error', 'Use at least 8 characters for your password.');
    return;
  }
  if (password !== confirm) {
    fail('#signup-error', 'The two passwords do not match.');
    return;
  }
  if (!terms) {
    fail('#signup-error', 'Please accept the terms to continue.');
    return;
  }

  const btn = $('#signup-submit');
  busy(btn, true, 'Creating account…');

  const username = name.toLowerCase().replace(/[^a-z0-9]+/g, '.').replace(/^\.|\.$/g, '').slice(0, 30) || 'student';

  try {
    await auth.register({ username, email, password, passwordConfirm: confirm });
    toast('Account created. Welcome to StudySpace.', 'success');
    setTimeout(goNext, 500);
  } catch (err) {
    if (err.status === 0) {
      demoSession(username);
      toast('Preview mode: demo account created locally.', 'info', 5000);
      setTimeout(goNext, 700);
    } else {
      fail('#signup-error', err.message || 'Could not create the account. Try a different username.');
    }
  } finally {
    busy(btn, false);
  }
});

/* ------------------------------------------------------------------ */
/* Demo & recovery                                                    */
/* ------------------------------------------------------------------ */

document.addEventListener('click', (e) => {
  if (e.target.closest('[data-demo-login]')) {
    demoSession('aarav.gupta');
    toast('Signed in with the demo account.', 'success');
    setTimeout(goNext, 500);
  }
  if (e.target.closest('[data-forgot]')) {
    e.preventDefault();
    toast('Password reset is not available in the static preview.', 'info');
  }
});

/* If a session already exists, offer to continue instead of re-authenticating. */
if (storage.access && !new URLSearchParams(location.search).get('force')) {
  const banner = document.createElement('div');
  banner.className = 'alert alert-info';
  banner.style.marginBottom = '18px';
  banner.innerHTML = `<svg><use href="#i-info"/></svg>
    <span>You are already signed in as <strong>${esc(storage.user?.username || 'Student')}</strong>.
    <a class="link" href="dashboard.html" style="margin-left:4px">Continue</a></span>`;
  $('.auth-form-wrap')?.prepend(banner);
}
