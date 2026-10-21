// StudySpace Frontend Application
// Uses api.js for all server communication

import { api, APIError } from './api.js';

const $ = id => document.getElementById(id);
const $$ = selector => document.querySelectorAll(selector);
let installPrompt = null;
let currentUser = null;
let isOnline = navigator.onLine;

// Escape HTML for safe rendering
function esc(v = "") {
  return String(v).replace(/[&<>"']/g, c => ({
    "&": "&", "<": "<", ">": ">", '"': "\"", "'": "'"
  }[c]));
}

// Symbol and class helpers
function sym(s) { return ({Physics: "\u2211", Maths: "\u03c0", Chemistry: "\u2697"})[s] || "\u2726"; }
function cls(s) { return ({Physics: "", Maths: "maths", Chemistry: "chemistry"})[s] || ""; }

// Loading states
function showLoading(el, message = "Loading...") {
  el.innerHTML = `<div class="loading">${esc(message)}</div>`;
}

function showError(el, message) {
  el.innerHTML = `<div class="error">${esc(message)}</div>`;
}

function showEmpty(el, message = "No items found.") {
  el.innerHTML = `<div class="empty">${esc(message)}</div>`;
}

// Update stats in header
async function updateStats() {
  if (!api.isAuthenticated()) {
    $("courseCount").textContent = "0";
    $("doneCount").textContent = "0";
    $("noteCount").textContent = "0";
    return;
  }
  try {
    const [coursesRes, progressRes, notesRes] = await Promise.all([
      api.courses.list({ page_size: 1 }),
      api.progress.list({ page_size: 1 }),
      api.notes.list({ page_size: 1 })
    ]);
    $("courseCount").textContent = coursesRes.count || 0;
    $("doneCount").textContent = (progressRes.results || []).filter(p => p.completed).length;
    $("noteCount").textContent = notesRes.count || 0;
  } catch (e) {
    console.warn("Failed to update stats:", e);
  }
}

// Load and render courses
async function loadCourses() {
  const grid = $("courseGrid");
  showLoading(grid);

  try {
    if (!api.isAuthenticated()) {
      showEmpty(grid, "Sign in to see your courses.");
      return;
    }

    const data = await api.courses.list({ ordering: "-created_at" });
    const courses = data.results || data;

    if (!courses.length) {
      showEmpty(grid, "No courses available yet.");
      return;
    }

    // Fetch lessons for each course
    const coursesWithLessons = await Promise.all(courses.map(async c => {
      try {
        const lessonsData = await api.courses.lessons(c.id);
        return { ...c, lessons: lessonsData.results || lessonsData };
      } catch {
        return { ...c, lessons: [] };
      }
    }));

    renderCourses(coursesWithLessons);
  } catch (e) {
    console.error("Failed to load courses:", e);
    showError(grid, e instanceof APIError ? e.message : "Failed to load courses");
  }
}

function renderCourses(courses) {
  const q = $("search").value.trim().toLowerCase();
  const shown = courses.filter(c =>
    `${c.title} ${c.description || ""} ${c.subject}`.toLowerCase().includes(q)
  );

  $("courseGrid").innerHTML = shown.length
    ? shown.map(c => `
      <article class="course-card">
        <div class="course-banner ${cls(c.subject)}">
          <span class="course-symbol">${sym(c.subject)}</span>
        </div>
        <div class="course-card-body">
          <span class="tag">${esc(c.subject || "Course")}</span>
          <h3>${esc(c.title)}</h3>
          <p>${esc(c.description || "Explore lessons and practice at your own pace.")}</p>
          <div class="lesson-list">
            ${(c.lessons || []).map(l => `
              <div class="lesson">
                <div>
                  <strong>${esc(l.title)}</strong>
                  <small>${Number(l.duration_minutes || 0) || "\u2014"} min ${l.completed ? "\u00b7 \u2713 Completed" : ""}</small>
                </div>
                ${l.video_url
                  ? `<a href="${esc(l.video_url)}" target="_blank" rel="noopener noreferrer">Watch \u2197</a>`
                  : `<a href="#" data-complete="${l.id}" data-course="${c.id}">${l.completed ? "Done" : "Mark done"}</a>`
                }
              </div>
            `).join("") || "<p class=muted>Lessons will appear here when added in Django admin.</p>"}
          </div>
        </div>
      </article>
    `).join("")
    : `<div class="empty">No courses match your search.</div>`;

  // Re-attach click handlers for mark complete
  $$("#courseGrid [data-complete]").forEach(a => {
    a.onclick = async (e) => {
      e.preventDefault();
      const lessonId = Number(a.dataset.complete);
      const courseId = a.dataset.course;

      if (!api.isAuthenticated()) {
        alert("Please sign in to track progress.");
        return;
      }

      try {
        await api.progress.create({ lesson: lessonId, completed: true });
        a.textContent = "Done";
        a.onclick = null; // Prevent double-click
        updateStats();
      } catch (err) {
        console.error("Failed to mark complete:", err);
        alert(err instanceof APIError ? err.message : "Failed to update progress");
      }
    };
  });
}

// Load and render notes
async function loadNotes() {
  const list = $("notesList");
  showLoading(list);

  try {
    if (!api.isAuthenticated()) {
      showEmpty(list, "Sign in to view and save notes.");
      return;
    }

    const data = await api.notes.list({ ordering: "-updated_at" });
    const notes = data.results || data;
    renderNotes(notes);
  } catch (e) {
    console.error("Failed to load notes:", e);
    showError(list, e instanceof APIError ? e.message : "Failed to load notes");
  }
}

function renderNotes(notes) {
  $("notesList").innerHTML = notes.length
    ? notes.map(n => `
      <article class="note-item">
        <strong>${esc(n.title)}</strong>
        <p>${esc(n.body)}</p>
        <small class="note-meta">Updated ${new Date(n.updated_at).toLocaleDateString()}</small>
      </article>
    `).join("")
    : "<p class=muted>No notes saved yet.</p>";
  $("noteCount").textContent = notes.length;
}

// Handle note form submission
async function handleNoteSubmit(e) {
  e.preventDefault();
  const btn = $("noteForm").querySelector("button[type=submit]");
  const title = $("noteTitle").value.trim() || "My note";
  const body = $("noteBody").value.trim();

  if (!body) return;

  if (!api.isAuthenticated()) {
    alert("Please sign in to save notes.");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Saving...";

  try {
    await api.notes.create({ title, body });
    $("noteTitle").value = "";
    $("noteBody").value = "";
    loadNotes();
  } catch (err) {
    console.error("Failed to save note:", err);
    alert(err instanceof APIError ? err.message : "Failed to save note");
  } finally {
    btn.disabled = false;
    btn.textContent = "Save note";
  }
}

// Auth UI handlers
function updateAuthUI() {
  const isAuthed = api.isAuthenticated();
  currentUser = api.getUser();

  // Show/hide auth-dependent sections
  $$(".auth-required").forEach(el => el.hidden = !isAuthed);
  $$(".auth-hidden").forEach(el => el.hidden = isAuthed);

  if (isAuthed && currentUser) {
    const userDisplay = $("userDisplay");
    if (userDisplay) userDisplay.textContent = currentUser.username || currentUser.email;
  }
}

async function handleSignup(e) {
  e.preventDefault();
  const form = e.target;
  const btn = form.querySelector("button[type=submit]");
  const data = {
    username: form.username.value.trim(),
    email: form.email.value.trim(),
    password: form.password.value,
    password2: form.password2.value
  };

  btn.disabled = true;
  btn.textContent = "Creating account...";

  try {
    await api.signup(data);
    updateAuthUI();
    loadCourses();
    loadNotes();
    form.reset();
    // Close modal if exists
    const modal = document.querySelector(".auth-modal");
    if (modal) modal.remove();
  } catch (err) {
    console.error("Signup failed:", err);
    alert(err instanceof APIError ? err.message : "Signup failed");
  } finally {
    btn.disabled = false;
    btn.textContent = "Create account";
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const form = e.target;
  const btn = form.querySelector("button[type=submit]");
  const data = {
    username: form.username.value.trim(),
    password: form.password.value
  };

  btn.disabled = true;
  btn.textContent = "Signing in...";

  try {
    await api.login(data);
    updateAuthUI();
    loadCourses();
    loadNotes();
    form.reset();
    // Close modal if exists
    const modal = document.querySelector(".auth-modal");
    if (modal) modal.remove();
  } catch (err) {
    console.error("Login failed:", err);
    alert(err instanceof APIError ? err.message : "Login failed");
  } finally {
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
}

async function handleLogout() {
  try {
    await api.logout();
  } catch (e) {
    console.warn("Logout error:", e);
  }
  updateAuthUI();
  loadCourses();
  loadNotes();
}

// PWA install prompt
window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault();
  installPrompt = e;
  $("installBtn").hidden = false;
});

$("installBtn").addEventListener("click", async () => {
  if (!installPrompt) return;
  await installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  $("installBtn").hidden = true;
});

// Service worker
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("./sw.js").catch(() => {})
  );
}

// Auth state change listener
window.addEventListener("auth:logout", () => {
  updateAuthUI();
  loadCourses();
  loadNotes();
});

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  updateAuthUI();
  loadCourses();
  loadNotes();

  // Search handler
  $("search").addEventListener("input", () => {
    loadCourses();
  });

  // Note form
  $("noteForm").addEventListener("submit", handleNoteSubmit);

  // Auth forms - delegated to handle dynamically added forms
  document.addEventListener("submit", e => {
    if (e.target.id === "signupForm") handleSignup(e);
    if (e.target.id === "loginForm") handleLogin(e);
  });

  // Logout button (if exists)
  const logoutBtn = document.querySelector("[data-logout]");
  if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);

  // Online/offline detection
  window.addEventListener("online", () => {
    isOnline = true;
    $("#offlineIndicator").hidden = true;
    loadDashboard(); // Refresh data when coming back online
  });
  window.addEventListener("offline", () => {
    isOnline = false;
    $("#offlineIndicator").hidden = false;
  });

  // Service worker update notification
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (!navigator.serviceWorker.controller) return;
      // New SW took control - reload to get fresh assets
      window.location.reload();
    });
  }
});

// Export for testing
if (typeof module !== "undefined" && module.exports) {
  module.exports = { esc, sym, cls };
}
