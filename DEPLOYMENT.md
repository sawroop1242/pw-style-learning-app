# StudySpace Deployment Guide

This document describes how to deploy the StudySpace Django API and frontend to a production environment.

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Client    │────▶│  Frontend    │────▶│   Django API     │
│  (Browser)  │     │  (Static)    │     │  (Gunicorn)      │
└─────────────┘     └──────────────┘     └────────┬─────────┘
                                                  │
                                          ┌───────┴───────┐
                                          │  PostgreSQL   │
                                          │  (Database)   │
                                          └───────────────┘
```

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- A reverse proxy (nginx, Caddy, or cloud load balancer)
- Domain name with TLS certificate (Let's Encrypt recommended)

## Environment Variables

Create a `.env` file in the `backend/` directory with the following variables. **Never commit real secrets to version control.**

```bash
# Django
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-50+-character-random-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (PostgreSQL required for production)
DATABASE_URL=postgres://user:password@host:5432/dbname

# CORS - Frontend origin(s)
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Security (production)
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=false

# Email (SMTP) - Required for password reset OTP
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=your-smtp-username
EMAIL_HOST_PASSWORD=your-smtp-password
DEFAULT_FROM_EMAIL=StudySpace <noreply@yourdomain.com>
SERVER_EMAIL=StudySpace <noreply@yourdomain.com>

# OTP Settings
OTP_EXPIRY_MINUTES=10
OTP_MAX_ATTEMPTS=5
```

### Variable Reference

| Variable | Required | Description |
|---|---|---|
| `ENVIRONMENT` | Yes | `production`, `staging`, `test`, or `development` |
| `DEBUG` | Yes | `true`/`false` - Must be `false` in production |
| `SECRET_KEY` | Yes | 50+ char random string for Django signing |
| `ALLOWED_HOSTS` | Yes | Comma-separated hostnames (no wildcards in prod) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `CORS_ALLOWED_ORIGINS` | Yes | Frontend origins for CORS |
| `CSRF_TRUSTED_ORIGINS` | Yes | Origins for CSRF protection |
| `SECURE_SSL_REDIRECT` | Prod only | Redirect HTTP→HTTPS |
| `SESSION_COOKIE_SECURE` | Prod only | HTTPS-only session cookies |
| `CSRF_COOKIE_SECURE` | Prod only | HTTPS-only CSRF cookies |
| `SECURE_HSTS_SECONDS` | Prod only | HSTS max-age (1 year = 31536000) |
| `EMAIL_*` | Prod only | SMTP settings for password reset |

## Backend Deployment

### 1. Prepare Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with production values
```

### 3. Database Migration

```bash
# Run migrations
python manage.py migrate

# Verify no pending migrations
python manage.py makemigrations --check --dry-run
```

### 4. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 5. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 6. Run with Gunicorn

```bash
# Development
gunicorn config.wsgi:application --bind 0.0.0.0:8000

# Production (with workers)
gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
```

### 7. Process Manager (systemd example)

Create `/etc/systemd/system/studyspace-api.service`:

```ini
[Unit]
Description=StudySpace Django API
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/studyspace/backend
EnvironmentFile=/var/www/studyspace/backend/.env
ExecStart=/var/www/studyspace/backend/venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 3 \
  --timeout 60 \
  --access-logfile /var/log/studyspace/access.log \
  --error-logfile /var/log/studyspace/error.log
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable studyspace-api
sudo systemctl start studyspace-api
```

## Frontend Deployment

### 1. Configure API Base URL

The frontend reads the API base from a `<meta name="api-base">` tag in `index.html`. For production, either:

**Option A: Serve with build-time injection**
```bash
# In your build script, replace the meta tag
sed -i 's|<meta name="api-base" content="/api">|<meta name="api-base" content="https://api.yourdomain.com/api">|' frontend/index.html
```

**Option B: Serve index.html dynamically**
Serve `index.html` through your backend with a template variable, or use a build tool that injects the value.

### 2. Serve Static Files

The frontend is pure static files (HTML, CSS, JS, SVG). Serve with any static host:

**nginx example:**
```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    root /var/www/studyspace/frontend;
    index index.html;
    
    # Security headers
    add_header X-Frame-Options "DENY";
    add_header X-Content-Type-Options "nosniff";
    add_header Referrer-Policy "same-origin";
    
    # Service worker
    location /sw.js {
        add_header Service-Worker-Allowed "/";
        add_header Cache-Control "no-cache";
    }
    
    # Manifest
    location /manifest.webmanifest {
        add_header Content-Type "application/manifest+json";
    }
    
    # Static assets - long cache
    location ~* \.(css|js|svg|ico|png|jpg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # Proxy API to Django
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check
    location /healthz/ {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }
}
```

### 3. Alternative: Static Hosting (Netlify, Vercel, GitHub Pages, Cloudflare Pages)

1. Connect your repository
2. Set build command: (none - files are already static)
3. Set output directory: `frontend`
4. Add environment variable for API base URL
5. Deploy

## Database Configuration

### PostgreSQL Setup

```sql
-- Create database and user
CREATE DATABASE studyspace;
CREATE USER studyspace_user WITH ENCRYPTED PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE studyspace TO studyspace_user;

-- Recommended settings for Django
ALTER USER studyspace_user SET timezone = 'UTC';
ALTER USER studyspace_user SET client_encoding = 'UTF8';
```

### Migration Procedure

```bash
# 1. Backup database
pg_dump studyspace > backup_$(date +%F).sql

# 2. Apply migrations
python manage.py migrate

# 3. Verify
python manage.py check
```

### Rollback Procedure

```bash
# 1. Identify target migration
python manage.py showmigrations

# 2. Migrate backward
python manage.py migrate app_name migration_name

# 3. Or restore from backup
psql studyspace < backup_2026-01-15.sql
```

## HTTPS & Security

### TLS Configuration

- Use Let's Encrypt with Certbot or your cloud provider's managed certificates
- Ensure `SECURE_SSL_REDIRECT=true` in production
- HSTS preload: submit to https://hstspreload.org/ after testing

### CORS/CSRF

- `CORS_ALLOWED_ORIGINS` = exact frontend origin(s), no wildcards
- `CSRF_TRUSTED_ORIGINS` = same as CORS origins
- Both must include scheme (`https://`)

### Security Headers (Django + nginx)

Django provides:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: same-origin`
- HSTS (when `SECURE_HSTS_SECONDS` set)

nginx adds:
- `Content-Security-Policy` (optional, configure based on your needs)

## Health Checks

### Liveness Probe

```bash
curl -f https://yourdomain.com/healthz/
# Returns: {"status": "ok"}
```

### Readiness Probe (includes DB)

```bash
curl -f https://yourdomain.com/api/health/
# Custom endpoint if needed, or use liveness
```

### Monitoring

- Monitor `/healthz/` every 30s
- Alert on 3 consecutive failures
- Log access to health endpoint separately

## Logging

### Django Logs

Configure in `settings.py` or via environment:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
        "file": {"class": "logging.handlers.RotatingFileHandler", "filename": "/var/log/studyspace/django.log", "maxBytes": 10485760, "backupCount": 5, "formatter": "json"},
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
}
```

### No Secrets in Logs

- Audit events use structured logging without PII
- Passwords, tokens, OTPs never logged
- Email addresses logged only in audit context

## Backups

### Database Backup (daily)

```bash
#!/bin/bash
# /etc/cron.daily/studyspace-backup
pg_dump -Fc studyspace > /var/backups/studyspace_$(date +%F).dump
find /var/backups -name "studyspace_*.dump" -mtime +30 -delete
```

### Media/Static Files

- Static files are reproducible from `collectstatic`
- User uploads (if any) - backup media directory

## Smoke Test Checklist

After deployment, verify:

| Check | Command | Expected |
|---|---|---|
| Health endpoint | `curl https://yourdomain.com/healthz/` | `{"status":"ok"}` |
| HTTPS redirect | `curl -I http://yourdomain.com` | 301/302 to HTTPS |
| HSTS header | `curl -I https://yourdomain.com` | `Strict-Transport-Security` |
| CORS headers | `curl -H "Origin: https://yourdomain.com" -I https://yourdomain.com/api/courses/` | `Access-Control-Allow-Origin` |
| Admin accessible | `curl -I https://yourdomain.com/admin/` | 200/302 (requires auth) |
| API auth required | `curl https://yourdomain.com/api/notes/` | 401 Unauthorized |
| Login works | Browser test | JWT tokens returned |
| Course list | Browser test | Courses displayed |
| Notes CRUD | Browser test | Create/read/update/delete |
| Quiz attempt | Browser test | Start/submit/result |
| Service worker | DevTools → Application | Registered, no errors |
| PWA installable | DevTools → Application → Manifest | No errors |
| Offline indicator | Disconnect network | "Offline" badge appears |
| Static assets cached | DevTools → Network → Disable cache | Assets load from SW |

## Release Procedure

### Pre-deployment

1. Run full test suite: `python manage.py test`
2. Check migrations: `python manage.py makemigrations --check --dry-run`
3. Verify dependencies: `pip audit` (or `pip list --outdated`)
4. Review changelog for breaking changes

### Deployment

1. Tag release: `git tag v1.2.3`
2. Push tag: `git push origin v1.2.3`
3. CI/CD builds and deploys (or manual steps above)
4. Run smoke tests
5. Monitor error rates for 10 minutes

### Rollback

1. Revert to previous tag: `git checkout v1.2.2`
2. Deploy previous version
3. Run database rollback if migrations applied
4. Verify health endpoint

## Troubleshooting

### Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| 502 Bad Gateway | Gunicorn not running | Check systemd status, logs |
| 403 CSRF | CSRF_TRUSTED_ORIGINS missing | Add frontend origin |
| CORS error | CORS_ALLOWED_ORIGINS mismatch | Match exact origin with scheme |
| Static 404 | collectstatic not run | Run `python manage.py collectstatic` |
| Migrations fail | DB lock or conflict | Check for long transactions, retry |
| Email not sent | SMTP config wrong | Test with `python -m smtplib` |

### Logs to Check

```bash
# API logs
journalctl -u studyspace-api -f

# nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Django logs
tail -f /var/log/studyspace/django.log
```

## Unverified Deployment Note

This deployment guide has been created based on the codebase structure and best practices. **It has not been tested against a live production environment** as no hosting credentials or target infrastructure were provided.

To verify:
1. Provision a test server (VM, VPS, or container)
2. Follow the steps above
3. Run the smoke test checklist
4. Update this document with actual results and any adjustments needed

---

## Quick Reference: Production Checklist

- [ ] PostgreSQL database created and accessible
- [ ] `.env` file with all production variables
- [ ] `SECRET_KEY` is 50+ random characters
- [ ] `DEBUG=false`, `ENVIRONMENT=production`
- [ ] `ALLOWED_HOSTS` contains exact production hostnames
- [ ] `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` match frontend
- [ ] TLS certificate installed and valid
- [ ] `SECURE_SSL_REDIRECT=true`, secure cookies enabled
- [ ] HSTS configured
- [ ] SMTP configured for password reset emails
- [ ] Migrations applied: `python manage.py migrate`
- [ ] Static files collected: `python manage.py collectstatic`
- [ ] Gunicorn running with 3+ workers
- [ ] nginx/Caddy reverse proxy configured
- [ ] Health endpoint responding
- [ ] Smoke tests passing
- [ ] Backups configured and tested
- [ ] Monitoring/alerting configured
- [ ] Documentation updated with actual deployment details