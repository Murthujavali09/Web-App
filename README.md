# Pramaan (TimeTrack)

**Pramaan** is a multi-tenant retail operations platform for store teams and managers. It combines **time clocking with face recognition**, **inventory tracking**, **end-of-day (EOD) cash reporting**, **billing**, and **manager alerts** in a single Flask application.

The frontend is plain HTML, CSS, and JavaScript. The backend is a **Flask REST API**. There is **no separate frontend dev server**—one process serves both the API and the web pages.

---

## Quick start (local development)

### Prerequisites

- **Python 3.11** (see `runtime.txt`)
- **PostgreSQL** (recommended) or SQLite (default if `DATABASE_URL` is not set)
- A modern browser with camera access (for face clock-in)

### 1. Clone and install dependencies

```powershell
cd timetrack
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS/Linux:

```bash
cd timetrack
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the example file and edit values:

```powershell
copy .env.example .env
```

See [.env.example](.env.example) for all supported variables. Minimum for local dev:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | JWT/session signing (use a long random string in production) |
| `DATABASE_URL` | Optional. Omit to use SQLite file `timetrack.db` in project root |

### 3. Run the application (frontend + backend together)

From the **project root** (`timetrack/`), not inside `backend/`:

```powershell
# PowerShell
$env:FLASK_APP = "backend.app:create_app"
$env:FLASK_ENV = "development"
$env:FLASK_DEBUG = "true"
flask run --host 0.0.0.0 --port 5000
```

Alternative (same result):

```powershell
python backend/app.py
```

Open in your browser:

- **Login:** [http://localhost:5000/](http://localhost:5000/) or [http://localhost:5000/login.html](http://localhost:5000/login.html)
- **Health check:** [http://localhost:5000/api/health](http://localhost:5000/api/health)
- **Sign up (new tenant):** [http://localhost:5000/signup](http://localhost:5000/signup)

### 4. Seed development users (required for empty database)

SQLite creates tables automatically, but **does not create any login accounts**. The `SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD` values in `.env` are only applied when you run the seed command:

```powershell
flask --app backend.app:create_app seed-dev
```

This creates:

| Role | Username | Password (default) |
|------|----------|-------------------|
| Super Admin | From `SUPER_ADMIN_USERNAME` in `.env` | From `SUPER_ADMIN_PASSWORD` in `.env` |
| Demo Manager | `manager` | `manager123` |
| Demo Store Lawrence | `lawrence` | `lawrence123` |
| Demo Store Oakville | `oakville` | `oakville123` |

To reset the super admin password after changing `.env`:

```powershell
flask --app backend.app:create_app seed-dev --reset-super-admin
```

Optional legacy store-only seed (needs an existing tenant):

```powershell
flask --app backend.app:create_app seed-stores
```

---

## How frontend and backend work together

```
Browser  →  http://localhost:5000/dashboard.html   (HTML from frontend/pages/)
         →  http://localhost:5000/static/js/script.js
         →  http://localhost:5000/api/timeclock/...  (Flask blueprints)
```

| Path | Served by |
|------|-----------|
| `/`, `/login.html`, `/*.html` | `frontend/pages/` |
| `/static/css/*`, `/static/js/*` | `frontend/static/` |
| `/api/*` | Flask blueprints under `backend/routes/` |

You do **not** run `npm start` or a separate Vite/React server for this app.

---

## User roles

| Role | Typical login | Main pages |
|------|----------------|------------|
| **Store** | Store username/password | `dashboard.html`, `timeclock.html`, `inventory.html`, `eod.html` |
| **Manager** | Manager username/password | `manager.html`, employees, billings, alerts |
| **Admin** | Admin account (region-scoped) | `admin.html`, reports, managers list |
| **Super Admin** | Tenant owner / platform super admin | `super-admin.html`, subscription, all managers/admins |
| **Platform Super Admin** | `SUPER_ADMIN_USERNAME` env | Cross-tenant management (see config) |

Full feature breakdown: **[docs/FEATURES.md](docs/FEATURES.md)**

---

## Database

- **SQLite** (default): created automatically as `timetrack.db` when `DATABASE_URL` is unset.
- **PostgreSQL**: set `DATABASE_URL=postgresql://user:pass@host:5432/dbname`

Run migrations / schema updates via Flask CLI when needed:

```powershell
flask --app backend.app:create_app create-alerts-table
flask --app backend.app:create_app add-store-timings
flask --app backend.app:create_app add-inventory-sold-to-eod
```

Other commands are registered in `backend/app.py` (`flask --app backend.app:create_app --help`).

---

## Production deployment

The repo includes **Vercel** configuration (`vercel.json`, `api/index.py`). The same Flask app runs as a serverless entry point; set all environment variables in the Vercel dashboard.

For a traditional server:

```bash
gunicorn "backend.app:create_app()" --bind 0.0.0.0:8000
```

Use PostgreSQL, a strong `SECRET_KEY`, and configure Stripe/SMTP if you enable signup and email.

---

## Project structure

```
timetrack/
├── api/                 # Vercel serverless entry
├── backend/
│   ├── app.py           # Flask app factory + static file routes
│   ├── config.py        # Environment configuration
│   ├── models.py        # SQLAlchemy models
│   ├── routes/          # API blueprints
│   ├── migrations/      # One-off DB migration scripts
│   └── services/        # Face recognition helpers
├── frontend/
│   ├── pages/           # HTML pages
│   └── static/          # CSS and JS
├── docs/
│   └── FEATURES.md      # Detailed feature documentation
├── requirements.txt
└── .env.example
```

---

## Documentation

- **[docs/FEATURES.md](docs/FEATURES.md)** — Every module, page, and API area explained
- **[.env.example](.env.example)** — Environment variable reference

---

## License

Add your license here before publishing to GitHub.
