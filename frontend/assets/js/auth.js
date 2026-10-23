/**
 * Account entry: sign in, create an account, and the email-code password reset.
 *
 * Every request matches the Django API contract exactly. When the API is not
 * running (the static preview) a clearly-labelled local demo session is used
 * instead, so the page is still demonstrable without pretending to be live.
 */

import { $, esc, auth, storage, request, isUnreachable } from './core.js';
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

  const account = $('#account-panel');
  if (account) account.hidden = true;

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
    const wait = err.message && /available in/i.test(err.message) ? err.message : '';
    formAlert(form, `Too many attempts. ${wait || 'Please wait a little while, then try again.'}`.trim());
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
    renderAccount();
    toast(`Welcome back, ${user?.username || identifier}.`, 'success');
    setTimeout(goNext, 350);
  } catch (err) {
    if (isUnreachable(err)) {
      demoSession(identifier);
      renderAccount();
      toast('Preview mode: no API behind this page, so you are signed in with a local demo session.', 'info', 6000);
      setTimeout(goNext, 700);
    } else if (err.status === 400 || err.status === 401) {
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
    renderAccount();
    toast('Account created. Welcome to StudySpace.', 'success');
    setTimeout(goNext, 400);
  } catch (err) {
    if (isUnreachable(err)) {
      demoSession(username);
      renderAccount();
      toast('Preview mode: no API behind this page, so a local demo account was created.', 'info', 6000);
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
  resetResendCooldown();
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
    startResendCooldown();
    toast('If that email has an account, a code is on its way.', 'success', 5000);
  } catch (err) {
    if (isUnreachable(err)) {
      // No API in the preview: explain instead of pretending a mail was sent.
      formAlert(form, 'No API is answering this page, so a reset code cannot be sent. Start the Django server and open the site through tools/serve.py to use password reset.');
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
    if (isUnreachable(err)) {
      formAlert(form, 'No API is answering this page, so the code cannot be checked.');
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

/* ------------------------------------------------------------------ */
/* Resend cooldown                                                     */
/* ------------------------------------------------------------------ */

const RESEND_FALLBACK_SECONDS = 60;
let resendTimer = null;

function startResendCooldown(seconds = RESEND_FALLBACK_SECONDS) {
  const button = $('[data-resend]');
  const label = $('[data-resend-label]');
  if (!button || !label) return;

  let left = Math.max(1, Math.round(seconds));
  clearInterval(resendTimer);
  button.disabled = true;
  label.textContent = `Resend in ${left}s`;

  resendTimer = setInterval(() => {
    left -= 1;
    if (left <= 0) {
      clearInterval(resendTimer);
      resendTimer = null;
      button.disabled = false;
      label.textContent = 'Resend code';
      return;
    }
    label.textContent = `Resend in ${left}s`;
  }, 1000);
}

function resetResendCooldown() {
  clearInterval(resendTimer);
  resendTimer = null;
  const button = $('[data-resend]');
  const label = $('[data-resend-label]');
  if (button) button.disabled = false;
  if (label) label.textContent = 'Resend code';
}

/** Seconds quoted by DRF's throttled response, if it gave one. */
function throttleSeconds(message = '') {
  const match = /available in (\d+) second/i.exec(message);
  return match ? Number(match[1]) : RESEND_FALLBACK_SECONDS;
}

document.addEventListener('click', async (e) => {
  const button = e.target.closest('[data-resend]');
  if (!button || button.disabled || !resetTarget) return;

  try {
    await request('/auth/resend-otp/', { method: 'POST', body: { email: resetTarget } });
    toast('A new code is on its way.', 'success');
    startResendCooldown();
  } catch (err) {
    if (err.status === 429) {
      toast(err.message || 'Too many codes requested. Please wait before asking again.', 'error', 6000);
      startResendCooldown(throttleSeconds(err.message));
    } else if (isUnreachable(err)) {
      toast('No API is answering this page, so a new code cannot be sent.', 'error', 6000);
    } else {
      toast('Could not resend the code. Please try again later.', 'error');
    }
  }
});

/* ------------------------------------------------------------------ */
/* Demo & signed-in account panel                                     */
/* ------------------------------------------------------------------ */

function renderAccount() {
  const signedIn = Boolean(storage.access);
  const demo = Boolean(storage.user?.demo);
  const panel = $('#account-panel');
  const banner = $('#session-banner');
  const tabs = $('#auth-tabs');
  const passwordForm = $('#form-change-password');
  const passwordToggle = $('#toggle-password-form');

  if (!signedIn) {
    panel.hidden = true;
    if (banner) banner.hidden = true;
    passwordForm?.reset();
    passwordForm.hidden = true;
    passwordToggle.hidden = false;
    passwordToggle.setAttribute('aria-expanded', 'false');
    if (view === 'signin' || view === 'signup') {
      tabs.hidden = false;
      show(view, { focus: false });
    }
    return;
  }

  for (const name of VIEWS) {
    const node = viewNode(name);
    if (node) node.hidden = true;
  }
  tabs.hidden = true;
  panel.hidden = false;
  passwordForm.hidden = true;
  passwordToggle.hidden = demo;
  passwordToggle.setAttribute('aria-expanded', 'false');

  $('#auth-title').textContent = 'Your account';
  $('#auth-sub').textContent = demo
    ? 'Preview demo session — nothing is stored on a server.'
    : 'Signed in on this device.';
  $('#account-name').textContent = storage.user?.username || 'Student';
  $('#account-email').textContent = storage.user?.email || '—';
  $('#account-demo-note').hidden = !demo;
  document.title = 'Your account — StudySpace';

  if (banner) {
    banner.hidden = !demo;
    if (demo) {
      banner.innerHTML = '<span>Demo session: sign-in worked locally, not on the API.</span>';
    }
  }
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('[data-demo-login]')) return;
  demoSession(DEMO_USER);
  renderAccount();
  toast('Signed in with the demo account.', 'success');
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('#toggle-password-form')) return;
  const form = $('#form-change-password');
  const button = e.target.closest('#toggle-password-form');
  const open = form.hidden;
  form.hidden = !open;
  button.setAttribute('aria-expanded', String(open));
  if (open) $('#current-password').focus({ preventScroll: true });
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('[data-cancel-password]')) return;
  const form = $('#form-change-password');
  form.reset();
  clearForm(form);
  form.hidden = true;
  $('#toggle-password-form').setAttribute('aria-expanded', 'false');
  $('#toggle-password-form').focus({ preventScroll: true });
});

$('#form-change-password').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  clearForm(form);

  const current = $('#current-password').value;
  const next = $('#new-password').value;
  const confirm = $('#confirm-password').value;
  let invalid = false;

  if (!current) {
    fieldError('current-password', 'Enter your current password.');
    invalid = true;
  }
  if (next.length < 8) {
    fieldError('new-password', 'Use at least 8 characters.');
    invalid = true;
  }
  if (next !== confirm) {
    fieldError('confirm-password', 'The two passwords do not match.');
    invalid = true;
  }
  if (invalid) return focusFirstError(form);

  const button = $('#password-submit');
  busy(button, true, 'Updating…');

  try {
    await request('/auth/change-password/', {
      method: 'POST',
      body: {
        current_password: current,
        new_password: next,
        new_password_confirm: confirm
      }
    });
    // Changing the password blacklists every refresh token, including this
    // tab's, so sign in again with the new password to keep the session alive.
    const username = storage.user?.username || $('#account-name').textContent;
    await auth.login({ username, password: next }).catch(() => {});
    form.reset();
    form.hidden = true;
    $('#toggle-password-form').setAttribute('aria-expanded', 'false');
    renderAccount();
    toast('Password updated. Other devices were signed out.', 'success', 5000);
  } catch (err) {
    if (isUnreachable(err)) {
      formAlert(form, 'No API is answering this page, so the password cannot be changed.');
    } else {
      applyServerErrors(form, err, {
        current_password: 'current-password',
        new_password: 'new-password',
        new_password_confirm: 'confirm-password'
      });
    }
  } finally {
    busy(button, false);
  }
});

document.addEventListener('click', async (e) => {
  if (!e.target.closest('[data-sign-out]')) return;
  await auth.logout().catch(() => {});
  resetForgotFlow();
  renderAccount();
  toast('Signed out.', 'info');
});

renderAccount();
