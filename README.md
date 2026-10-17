# StudySpace — PW-inspired learning PWA + Django API

A mobile-first learning platform starter with a purple/white PWA frontend and Django REST Framework backend. This is an independent project and is not affiliated with Physics Wallah (PW). Use only course/video URLs you are authorized to access.

## Features
- Responsive, installable PWA frontend
- Django REST API for courses, lessons, quizzes, notes and progress
- Django admin for managing course content
- JWT authentication endpoints
- SQLite locally; PostgreSQL-ready using `DATABASE_URL`

## Run the backend
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
Serve the `frontend/` directory over HTTP/HTTPS and set `API_BASE` in `frontend/app.js` to your deployed API base URL. GitHub Pages can host the frontend, not Django. For production, set `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `DATABASE_URL`, and `CORS_ALLOWED_ORIGINS` on the backend host.

## Android
Edit the project from an Android code editor or Termux. A hosted backend is needed for server-side accounts and syncing between devices.
