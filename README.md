# StudySpace — PW-inspired learning PWA + Django API

A mobile-first learning platform starter with a purple/white PWA frontend and Django REST Framework backend. This is an independent project and is not affiliated with Physics Wallah (PW). Use only course/video URLs you are authorized to access.

## Features

- Responsive, installable PWA frontend with offline support
- Django REST API for courses, lessons, quizzes, notes, bookmarks, revision items, study tasks, and progress
- Test series with timed/untimed modes, CSV import, attempt autosave/resume
- JWT authentication with email OTP password reset
- Course access codes for paid content (Telegram provider contact)
- Django admin for managing course content
- SQLite locally; PostgreSQL-ready using `DATABASE_URL`
- Comprehensive test suite (96 tests passing)

## Quick Start (Development)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Open `/admin/` to manage content and `/api/` for API routes.

## Frontend

Serve the `frontend/` directory over HTTP/HTTPS. The API base URL is configured via `<meta name="api-base" content="/api">` in `index.html` - override at build time or serve dynamically.

For production deployment, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Project Structure

```
pw-style-learning-app/
├── backend/                 # Django project
│   ├── accounts/           # Authentication, profiles, audit
│   ├── courses/            # Courses, lessons, quizzes, notes, progress
│   ├── config/             # Django settings, URLs, health check
│   ├── manage.py
│   ├── requirements.txt
│   ├── Procfile
│   └── .env.example
├── frontend/                # PWA (vanilla JS, CSS, HTML)
│   ├── index.html
│   ├── app.js              # Main application
│   ├── api.js              # API client
│   ├── sw.js               # Service worker
│   ├── styles.css
│   ├── manifest.webmanifest
│   └── assets/
├── docs/                    # Documentation
│   ├── BUILD_STATUS.md     # Milestone progress
│   └── agent-prompts/      # Milestone specifications
├── DEPLOYMENT.md           # Production deployment guide
└── README.md
```

## Milestone Progress

See [docs/BUILD_STATUS.md](docs/BUILD_STATUS.md) for detailed milestone tracking.

| Milestone | Status | Description |
|---|---|---|
| M1 | ✅ | Project setup, Django config, health check |
| M2 | ✅ | Course catalog (Course, Folder, Lesson, PDF) |
| M3 | ✅ | Auth (JWT, registration, OTP reset, throttling) |
| M4 | ✅ | Quiz engine core (Quiz, Question, Choice, Attempt) |
| M5 | ✅ | Quiz engine complete (timer, autosave, scoring, CSV) |
| M6 | ✅ | Notes, progress, bookmarks, revision, study tasks |
| M7 | ✅ | Frontend API client, app shell, auth UI |
| M8 | ✅ | Complete learner journeys (7 core + course access) |
| M9 | ✅ | PWA offline, safe caching, manifest |
| M10 | ✅ | Quality, security, accessibility, performance |
| M11 | 📝 | Deployment guide (see DEPLOYMENT.md) |

## Testing

```bash
cd backend
ENVIRONMENT=test python manage.py test
# Runs 96 tests covering all milestones
```

## API Endpoints

All endpoints under `/api/` require JWT authentication unless noted.

| Area | Endpoints |
|---|---|
| Auth | `/token/`, `/token/refresh/`, `/auth/register/`, `/auth/logout/`, `/auth/me/`, `/auth/change_password/`, `/auth/forgot_password/`, `/auth/verify_otp/`, `/auth/resend_otp/` |
| Courses | `/courses/`, `/courses/{id}/`, `/lessons/`, `/lessons/{id}/` |
| Notes | `/notes/`, `/notes/{id}/` |
| Progress | `/progress/`, `/progress/{id}/` |
| Bookmarks | `/bookmarks/`, `/bookmarks/{id}/` |
| Revision | `/revision-items/`, `/revision-items/{id}/` |
| Study Tasks | `/study-tasks/`, `/study-tasks/{id}/`, `/study-tasks/{id}/complete/`, `/study-tasks/{id}/reopen/` |
| Quizzes | `/quizzes/`, `/quizzes/{id}/`, `/quizzes/start/` |
| Attempts | `/quiz-attempts/`, `/quiz-attempts/{id}/`, `/quiz-attempts/{id}/autosave/`, `/quiz-attempts/{id}/submit/`, `/quiz-attempts/{id}/result/` |
| Test Series | `/test-series/`, `/test-series/{id}/`, `/test-series/{id}/tests/`, `/test-series/{id}/start/` |
| Access Codes | `/access-codes/redeem/` |

## Configuration

Backend environment variables (see `.env.example`):

| Variable | Description |
|---|---|
| `ENVIRONMENT` | `development`, `test`, `staging`, `production` |
| `DEBUG` | `true`/`false` |
| `SECRET_KEY` | Django secret key (50+ chars in prod) |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `DATABASE_URL` | PostgreSQL connection string |
| `CORS_ALLOWED_ORIGINS` | Frontend origins for CORS |
| `CSRF_TRUSTED_ORIGINS` | Origins for CSRF |
| `SECURE_SSL_REDIRECT` | HTTPS redirect (prod) |
| `EMAIL_*` | SMTP settings for password reset |

## License

MIT License - see LICENSE file for details.

---

**Note:** This is a learning project. Not affiliated with Physics Wallah (PW) or any educational institution.
