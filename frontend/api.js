// StudySpace API Client
// Centralized fetch wrapper with auth, error handling, and retry logic

const API_BASE = (() => {
  // Allow override via meta tag or global config
  const meta = document.querySelector('meta[name="api-base"]');
  if (meta && meta.content) return meta.content.replace(/\/$/, '');
  // Default: same-origin /api
  return '/api';
})();

const TOKEN_KEY = 'studyspace_access';
const REFRESH_KEY = 'studyspace_refresh';
const USER_KEY = 'studyspace_user';

class APIError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
  }
}

function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

function setTokens(access, refresh) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

function getUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

async function refreshAccessToken() {
  const refresh = getRefreshToken();
  if (!refresh) throw new APIError('No refresh token', 401);

  const res = await fetch(`${API_BASE}/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh })
  });

  if (!res.ok) {
    clearTokens();
    throw new APIError('Token refresh failed', res.status);
  }

  const data = await res.json();
  setTokens(data.access, data.refresh);
  return data.access;
}

async function request(path, options = {}) {
  const { retry = false, ...fetchOptions } = options;
  const url = `${API_BASE}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers || {})
  };

  const access = getAccessToken();
  if (access) headers['Authorization'] = `Bearer ${access}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const res = await fetch(url, {
      ...fetchOptions,
      headers,
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    // Handle token refresh on 401
    if (res.status === 401 && !fetchOptions._retried && access && getRefreshToken()) {
      try {
        await refreshAccessToken();
        return request(path, { ...options, _retried: true });
      } catch {
        clearTokens();
        window.dispatchEvent(new CustomEvent('auth:logout'));
        throw new APIError('Session expired. Please sign in again.', 401);
      }
    }

    const contentType = res.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const data = isJson ? await res.json() : await res.text();

    if (!res.ok) {
      const message = isJson && data.detail ? data.detail :
        isJson && data.non_field_errors ? data.non_field_errors[0] :
        `Request failed (${res.status})`;
      throw new APIError(message, res.status, data);
    }

    return data;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof APIError) throw err;
    if (err.name === 'AbortError') throw new APIError('Request timeout', 408);
    if (err instanceof TypeError) throw new APIError('Network error. Check your connection.', 0);
    throw err;
  }
}

const api = {
  // Auth
  async signup({ username, email, password, password2 }) {
    const data = await request('/auth/register/', {
      method: 'POST',
      body: JSON.stringify({ username, email, password, password2 })
    });
    if (data.access && data.refresh) {
      setTokens(data.access, data.refresh);
      setUser({ username: data.username, email: data.email, id: data.id });
    }
    return data;
  },

  async login({ username, password }) {
    const data = await request('/token/', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    if (data.access && data.refresh) {
      setTokens(data.access, data.refresh);
      // Fetch user profile
      const user = await this.me();
      setUser(user);
    }
    return data;
  },

  async logout() {
    const refresh = getRefreshToken();
    if (refresh) {
      await request('/auth/logout/', {
        method: 'POST',
        body: JSON.stringify({ refresh })
      }).catch(() => {}); // Best effort
    }
    clearTokens();
  },

  async me() {
    return request('/auth/me/');
  },

  async changePassword({ current_password, new_password, new_password2 }) {
    return request('/auth/change_password/', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password, new_password2 })
    });
  },

  async forgotPassword(email) {
    return request('/auth/forgot_password/', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  },

  async verifyOtp({ email, otp, new_password, new_password2 }) {
    return request('/auth/verify_otp/', {
      method: 'POST',
      body: JSON.stringify({ email, otp, new_password, new_password2 })
    });
  },

  async resendOtp(email) {
    return request('/auth/resend_otp/', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
  },

  // Courses
  courses: {
    list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return request(`/courses/${qs ? '?' + qs : ''}`);
    },
    detail(id) {
      return request(`/courses/${id}/`);
    },
    lessons(courseId, params = {}) {
      const qs = new URLSearchParams({ course: courseId, ...params }).toString();
      return request(`/lessons/${qs ? '?' + qs : ''}`);
    }
  },

  // Notes
  notes: {
    list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return request(`/notes/${qs ? '?' + qs : ''}`);
    },
    create(data) {
      return request('/notes/', { method: 'POST', body: JSON.stringify(data) });
    },
    detail(id) {
      return request(`/notes/${id}/`);
    },
    update(id, data) {
      return request(`/notes/${id}/`, { method: 'PATCH', body: JSON.stringify(data) });
    },
    delete(id) {
      return request(`/notes/${id}/`, { method: 'DELETE' });
    }
  },

  // Progress
  progress: {
    list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return request(`/progress/${qs ? '?' + qs : ''}`);
    },
    create(data) {
      return request('/progress/', { method: 'POST', body: JSON.stringify(data) });
    },
    detail(id) {
      return request(`/progress/${id}/`);
    },
    update(id, data) {
      return request(`/progress/${id}/`, { method: 'PATCH', body: JSON.stringify(data) });
    },
    delete(id) {
      return request(`/progress/${id}/`, { method: 'DELETE' });
    }
  },

  // Bookmarks
  bookmarks: {
    list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return request(`/bookmarks/${qs ? '?' + qs : ''}`);
    },
    create(data) {
      return request('/bookmarks/', { method: 'POST', body: JSON.stringify(data) });
    },
    detail(id) {
      return request(`/bookmarks/${id}/`);
    },
    update(id, data) {
      return request(`/bookmarks/${id}/`, { method: 'PATCH', body: JSON.stringify(data) });
    },
    delete(id) {
      return request(`/bookmarks/${id}/`, { method: 'DELETE' });
    }
  },

  // Revision Items
  revision: {
    list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return request(`/revision-items/${qs ? '?' + qs : ''}`);
    },
    create(data) {
      return request('/revision-items/', { method: 'POST', body: JSON.stringify(data) });
    },
    detail(id) {
      return request(`/revision-items/${id}/`);
    },
    update(id, data) {
      return request(`/revision-items/${id}/`, { method: 'PATCH', body: JSON.stringify(data) });
    },
    delete(id) {
      return request(`/revision-items/${id}/`, { method: 'DELETE' });
    }
  },

  // Study Tasks
  tasks: {
    list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return request(`/study-tasks/${qs ? '?' + qs : ''}`);
    },
    create(data) {
      return request('/study-tasks/', { method: 'POST', body: JSON.stringify(data) });
    },
    detail(id) {
      return request(`/study-tasks/${id}/`);
    },
    update(id, data) {
      return request(`/study-tasks/${id}/`, { method: 'PATCH', body: JSON.stringify(data) });
    },
    delete(id) {
      return request(`/study-tasks/${id}/`, { method: 'DELETE' });
    },
    complete(id) {
      return request(`/study-tasks/${id}/complete/`, { method: 'POST' });
    },
    reopen(id) {
      return request(`/study-tasks/${id}/reopen/`, { method: 'POST' });
    }
  },

  // Quizzes
  quizzes: {
    list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return request(`/quizzes/${qs ? '?' + qs : ''}`);
    },
    detail(id) {
      return request(`/quizzes/${id}/`);
    },
    start(quizId) {
      return request('/quizzes/start/', { method: 'POST', body: JSON.stringify({ quiz_id: quizId }) });
    }
  },

  // Quiz Attempts
  attempts: {
    list(params = {}) {
      const qs = new URLSearchParams(params).toString();
      return request(`/quiz-attempts/${qs ? '?' + qs : ''}`);
    },
    detail(id) {
      return request(`/quiz-attempts/${id}/`);
    },
    autosave(attemptId, data) {
      return request(`/quiz-attempts/${attemptId}/autosave/`, { method: 'POST', body: JSON.stringify(data) });
    },
    submit(attemptId, data) {
      return request(`/quiz-attempts/${attemptId}/submit/`, { method: 'POST', body: JSON.stringify(data) });
    },
    result(attemptId) {
      return request(`/quiz-attempts/${attemptId}/result/`);
    }
  },

  // Access Codes
  redeemAccessCode(code) {
    return request('/access-codes/redeem/', { method: 'POST', body: JSON.stringify({ code }) });
  },

  // Utils
  isAuthenticated() {
    return !!getAccessToken();
  },
  getAccessToken,
  getUser,
  APIError
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { api, APIError, API_BASE };
}