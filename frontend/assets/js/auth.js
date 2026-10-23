/**
 * Account entry: sign in, create an account, and the email-code password reset.
 *
 * Every request matches the Django API contract exactly. When the API is not
 * running (the static preview) a clearly-labelled local demo session is used
 * instead, so the page is still demonstrable without pretending to be live.
 */

import { $, esc, auth, storage, request } from './core.js';
import { mountSprite, toast } from './ui.js';

mountSprite();

const DEMO_USER = 'aarav.gupta';

/* ------------------------------------------------------------------ */
/* Views                                                              */
/* ------------------------------------------------------------------ */

const VIEWS = ['signin', 'signup', 'forgot-request', 'forgot-reset', 'forgot-done'];

const COPY = {
  signin: {
    title: 'Welcome back',
    sub: 'Sign in to continue your preparation.',
    tab: true
  },
  signup: {
    title: 'Create your account',
    sub: 'Free to start. No card and no trial timer.',
    tab: true
  },
  'forgot-request': {
    title: 'Reset your password',
    sub: 'We will email a six-digit code to your account address.',
    tab: false
  },
  'forgot-reset': {
    title: 'Choose a new password',
    sub: 'The code is single use and expires ten minutes after it was sent.',
    tab: false
  },
  'forgot-done': {
    title: 'Password changed',
    sub: 'Your other sessions have been signed out.',
    tab: false
  }
};

let view = 'signin';

function show(next, { focus = true } = {}) {
  view = next;
  const copy = COPY[next];

  for (const name of VIEWS) {
    const node = viewNode(name);
    if (node) node.hidden = name !== next;
  }

  const tabs = $('#auth-tabs');
  if (tabs) tabs.hidden = !copy.tab;

  tapTab(next === 'signup' ? 'signup' : 'signin', next === 'signup');

  $('#auth-title').textContent = copy.title;
  $('#auth-sub').textContent = copy.sub;
  document.title = `${copy.title} — StudySpace`;

  if (focus) {
    const first = viewNode(next)?.querySelector('input, button');
    first?.focus({ preventScroll: true });
  }
}

const viewNode = (name) => ({
  signin: $('#form-signin'),
  signup: $('#form-signup'),
  'forgot-request': $('#forgot-request'),
  'forgot-reset': $('#forgot-reset'),
  'forgot-done': $('#forgot-done')
}[name]);

function tapTab(which, active) {
  const signin = $('#tab-signin');
  const signup = $('#tab-signup');
  if (!signin || !signup) return;
  signin.setAttribute('aria-selected', String(which === 'signin' && active));
  signup.setAttribute('aria-selected', String(which === 'signup' && active));
}

$('#tab-signin').addEventListener('click', () => show('signin'));
$('#tab-signup').addEventListener('click', () => show('signup'));

document.addEventListener('click', (e) => {
  const switchTo = e.target.closest('[data-switch]');
  if (switchTo) show(switchTo.dataset.switch === 'signup' ? 'signup' : 'signin');

  if (e.target.closest('[data-forgot]')) show('forgot-request');
  if (e.target.closest('[data-back-signin]')) {
    resetForgotFlow();
    show('signin');
  }
});

/* Deep links: #register opens the sign-up tab. */
if (location.hash === '#register') show('signup', { focus: false });

/* ------------------------------------------------------------------ */
/* Password visibility                                                */
/* ------------------------------------------------------------------ */

document.addEventListener('click', (e) => {
  const button = e.target.closest('[data-toggle-pass]');
  if (!button) return;
  const input = document.getElementById(button.dataset.togglePass);
  if (!input) return;

  const showPassword = input.type === 'password';
  input.type = showPassword ? 'text' : 'password';
  button.setAttribute('aria-label', showPassword ? 'Hide password' : 'Show password');
  const icon = button.querySelector('use');
  if (icon) icon.setAttribute('href', showPassword ? '#i-eye-off' : '#i-eye');
  input.focus({ preventScroll: true });
});

/* ------------------------------------------------------------------ */
/* Field errors                                                       */
/* ------------------------------------------------------------------ */

function fieldError(inputId, message) {
  const input = document.getElementById(inputId);
  const node = document.getElementById(`${inputId}-error`);
  if (input) {
    input.setAttribute('aria-invalid', 'true');
    if (node) input.setAttribute('aria-describedby', node.id);
  }
  if (node) {
    node.textContent = message;
    node.hidden = false;
  }
}

function clearFieldError(inputId) {
  const input = document.getElementById(inputId);
  const node = document.getElementById(`${inputId}-error`);
  if (input) {
    input.removeAttribute('aria-invalid');
    input.removeAttribute('aria-describedby');
  }
  if (node) {
    node.hidden = true;
    node.textContent = '';
  }
}

function clearForm(form) {
  form.querySelectorAll('input').forEach((input) => clearFieldError(input.id));
  const alert = form.querySelector('.form-alert');
  if (alert) {
    alert.hidden = true;
    alert.textContent = '';
  }
}

function formAlert(form, message) {
  const alert = form.querySelector('.form-alert');
  if (!alert) return;
  alert.textContent = message;
  alert.hidden = false;
}

/** Focus the first invalid field so keyboard and screen-reader users land there. */
function focusFirstError(form) {
  const invalid = form.querySelector('[aria-invalid="true"]');
  invalid?.focus({ preventScroll: false });
}

function busy(button, isBusy, label) {
  button.disabled = isBusy;
  button.setAttribute('aria-busy', String(isBusy));
  if (isBusy) {
    button.dataset.label = button.textContent;
    button.textContent = label || 'Please wait…';
  } else if (button.dataset.label) {
    button.textContent = button.dataset.label;
    delete button.dataset.label;
  }
}

/** Map a DRF validation error payload onto our fields. */
function applyServerErrors(form, err, mapping) {
  const data = err?.data;

  if (err?.status === 429) {
    formAlert(form, 'Too many attempts. Wait a minute, then try again.');
    return true;
  }

  if (!data || typeof data !== 'object') {
    formAlert(form, err?.message || 'Something went wrong. Please try again.');
    return true;
  }

  let handled = false;
  for (const [field, value] of Object.entries(data)) {
    const message = Array.isArray(value) ? value[0] : String(value);
    const inputId = mapping[field];
    if (inputId) {
      fieldError(inputId, message);
      handled = true;
    }
  }

  const general = data.detail || data.non_field_errors?.[0];
  if (general) {
    formAlert(form, general);
    handled = true;
  }

  if (!handled) formAlert(form, err.message || 'Please check the form and try again.');
  focusFirstError(form);
  return true;
}

/* ------------------------------------------------------------------ */
/* Redirect after success                                             */
/* ------------------------------------------------------------------ */

function goNext() {
  const next = new URLSearchParams(location.search).get('next');
  const safe = next && /^[\w.-]+\.html(\?[^<>"'\s]*)?$/.test(next);
  location.href = safe ? next : 'dashboard.html';
}

function demoSession(name) {
  storage.session = {
    access: 'demo-access-token',
    refresh: 'demo-refresh-token',
    user: { username: name, email: `${name}@example.com`, demo: true }
  };
}

/* ------------------------------------------------------------------ */
/* Sign in                                                            */
/* ------------------------------------------------------------------ */

$('#form-signin').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  clearForm(form);

  const identifier = $('#signin-identifier').value.trim();
  const password = $('#signin-password').value;
  let invalid = false;

  if (!identifier) {
    fieldError('signin-identifier', 'Enter your username or email.');
    invalid = true;
  }
  if (!password) {
    fieldError('signin-password', 'Enter your password.');
    invalid = true;
  }
  if (invalid) return focusFirstError(form);

  const button = $('#login-submit');
  busy(button, true, 'Signing in…');

  try {
    const user = await auth.login({ username: identifier, password });
    toast(`Welcome back, ${user?.username || identifier}.`, 'success');
    setTimeout(goNext, 350);
  } catch (err) {
    if (err.status === 0) {
      demoSession(identifier);
      toast('Preview mode: signed in with a local demo session.', 'info', 5000);
      setTimeout(goNext, 700);
    } else if (err.status === 401 || err.status === 400) {
      formAlert(form, 'That username or password did not match an account.');
      fieldError('signin-password', 'Check your password and try again.');
      focusFirstError(form);
    } else {
      applyServerErrors(form, err, {});
    }
  } finally {
    busy(button, false);
  }
});

/* ------------------------------------------------------------------ */
/* Sign up                                                            */
/* ------------------------------------------------------------------ */

function passwordScore(value) {
  let score = 0;
  if (value.length >= 8) score += 1;
  if (value.length >= 12) score += 1;
  if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score += 1;
  if (/\d/.test(value) && /[^A-Za-z0-9]/.test(value)) score += 1;
  return score;
}

$('#signup-password').addEventListener('input', (e) => {
  const value = e.target.value;
  const node = $('#signup-strength');
  if (!node) return;

  if (!value) {
    node.textContent = 'Use at least 8 characters.';
    node.dataset.strength = '';
    return;
  }

  const score = passwordScore(value);
  const labels = ['Too short', 'Weak', 'Fair', 'Good', 'Strong'];
  node.textContent = `${labels[score]} · ${value.length} characters`;
  node.dataset.strength = String(score);
});

$('#form-signup').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  clearForm(form);

  const username = $('#signup-username').value.trim();
  const email = $('#signup-email').value.trim();
  const password = $('#signup-password').value;
  const confirm = $('#signup-confirm').value;
  const terms = $('#signup-terms').checked;

  let invalid = false;

  if (!/^[\w.@+-]{3,30}$/.test(username)) {
    fieldError('signup-username', 'Use 3–30 characters: letters, digits or @ . + - _');
    invalid = true;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    fieldError('signup-email', 'Enter a valid email address.');
    invalid = true;
  }
  if (password.length < 8) {
    fieldError('signup-password', 'Use at least 8 characters.');
    invalid = true;
  }
  if (password !== confirm) {
    fieldError('signup-confirm', 'The two passwords do not match.');
    invalid = true;
  }
  if (!terms) {
    fieldError('signup-terms', 'Accept the terms to create an account.');
    invalid = true;
  }
  if (invalid) return focusFirstError(form);

  const button = $('#signup-submit');
  busy(button, true, 'Creating account…');

  try {
    await auth.register({ username, email, password, passwordConfirm: confirm });
    toast('Account created. Welcome to StudySpace.', 'success');
    setTimeout(goNext, 400);
  } catch (err) {
    if (err.status === 0) {
      demoSession(username);
      toast('Preview mode: demo account created locally.', 'info', 5000);
      setTimeout(goNext, 700);
    } else {
      applyServerErrors(form, err, {
        username: 'signup-username',
        email: 'signup-email',
        password: 'signup-password',
        password_confirm: 'signup-confirm'
      });
    }
  } finally {
    busy(button, false);
  }
});

/* ------------------------------------------------------------------ */
/* Password reset                                                     */
/* ------------------------------------------------------------------ */

let resetTarget = '';

function resetForgotFlow() {
  resetTarget = '';
  const requestForm = $('#forgot-request');
  const resetForm = $('#forgot-reset');
  requestForm?.reset();
  resetForm?.reset();
  clearForm(requestForm);
  clearForm(resetForm);
  $('#reset-email').textContent = 'your email';
}

$('#forgot-request').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  clearForm(form);

  const email = $('#forgot-email').value.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    fieldError('forgot-email', 'Enter the email on your account.');
    return focusFirstError(form);
  }

  const button = $('#forgot-send');
  busy(button, true, 'Sending…');

  try {
    await request('/auth/forgot-password/', { method: 'POST', body: { email } });
    resetTarget = email;
    $('#reset-email').textContent = email;
    show('forgot-reset');
    toast('If that email has an account, a code is on its way.', 'success', 5000);
  } catch (err) {
    if (err.status === 0) {
      // No API in the preview: explain instead of pretending a mail was sent.
      formAlert(form, 'The API is not reachable from this preview, so a reset code cannot be sent. Start the Django server to use password reset.');
    } else {
      applyServerErrors(form, err, { email: 'forgot-email' });
    }
  } finally {
    busy(button, false);
  }
});

$('#forgot-reset').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  clearForm(form);

  const code = $('#reset-code').value.trim();
  const password = $('#reset-password').value;
  const confirm = $('#reset-confirm').value;

  let invalid = false;
  if (!/^\d{6}$/.test(code)) {
    fieldError('reset-code', 'Enter the six-digit code from the email.');
    invalid = true;
  }
  if (password.length < 8) {
    fieldError('reset-password', 'Use at least 8 characters.');
    invalid = true;
  }
  if (password !== confirm) {
    fieldError('reset-confirm', 'The two passwords do not match.');
    invalid = true;
  }
  if (invalid) return focusFirstError(form);

  const button = $('#forgot-reset-btn');
  busy(button, true, 'Resetting…');

  try {
    await request('/auth/verify-otp/', {
      method: 'POST',
      body: {
        email: resetTarget,
        otp: code,
        new_password: password,
        new_password_confirm: confirm
      }
    });
    storage.clear();
    show('forgot-done');
  } catch (err) {
    if (err.status === 0) {
      formAlert(form, 'The API is not reachable from this preview, so the code cannot be checked.');
    } else {
      applyServerErrors(form, err, {
        otp: 'reset-code',
        new_password: 'reset-password',
        new_password_confirm: 'reset-confirm',
        email: 'reset-code'
      });
    }
  } finally {
    busy(button, false);
  }
});

document.addEventListener('click', async (e) => {
  if (!e.target.closest('[data-resend]')) return;
  if (!resetTarget) return;
  try {
    await request('/auth/resend-otp/', { method: 'POST', body: { email: resetTarget } });
    toast('A new code is on its way.', 'success');
  } catch (err) {
    toast(err.status === 429 ? 'Too many requests. Wait a minute.' : 'Could not resend the code.', 'error');
  }
});

/* ------------------------------------------------------------------ */
/* Demo & existing session                                            */
/* ------------------------------------------------------------------ */

document.addEventListener('click', (e) => {
  if (!e.target.closest('[data-demo-login]')) return;
  demoSession(DEMO_USER);
  toast('Signed in with the demo account.', 'success');
  setTimeout(goNext, 500);
});

function renderSessionBanner() {
  const host = $('#session-banner');
  if (!host || !storage.access) return;

  const name = storage.user?.username || 'Student';
  host.hidden = false;
  host.innerHTML = `
    <span>Signed in as <strong>${esc(name)}</strong>.</span>
    <span class="auth-session-actions">
      <a class="link" href="dashboard.html">Continue</a>
      <button class="link-button" type="button" data-sign-out>Sign out</button>
    </span>`;
}

document.addEventListener('click', async (e) => {
  if (!e.target.closest('[data-sign-out]')) return;
  await auth.logout().catch(() => {});
  renderSessionBanner();
  const host = $('#session-banner');
  if (host) host.hidden = true;
  toast('Signed out.', 'info');
});

renderSessionBanner();
