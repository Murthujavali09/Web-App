# Pramaan / TimeTrack - ChatGPT Project Context

Use this document as a single handoff file for ChatGPT or another developer. It summarizes the repository structure, runtime, data model, user roles, frontend pages, backend API, setup steps, and important implementation details.

## 1. One-Line Summary

Pramaan, also called TimeTrack in some files, is a multi-tenant retail operations web app for store teams, managers, admins, and tenant owners. It combines store login, manager/admin dashboards, employee management, webcam face-recognition time clocking, inventory tracking, daily EOD cash/card reports, billing payments, alerts, tenant signup, Stripe subscriptions, and SMTP email notifications.

## 2. Tech Stack

- Backend: Python 3.11, Flask 3, Flask-SQLAlchemy, Flask-CORS, Flask-Limiter
- Database: SQLite by default, PostgreSQL when `DATABASE_URL` or `POSTGRESQL_URI` is set
- Auth: JWT using `PyJWT`, bcrypt password hashes
- Frontend: static HTML, CSS, vanilla JavaScript
- Face recognition: browser-side `face-api.js` via CDN for descriptors, backend matching with NumPy-style Euclidean distance
- Payments: Stripe subscriptions and billing portal
- Email: SMTP, commonly Gmail with app password
- Deployment: Vercel Python serverless via `api/index.py`, or traditional WSGI via Gunicorn

There is no Node/Vite/React frontend server. Flask serves both the API and static frontend files.

## 3. Repository Structure

```text
webapp/
  api/
    index.py                         # Vercel serverless WSGI entry
  backend/
    app.py                           # Flask app factory, blueprint registration, static routes, CLI commands
    auth.py                          # JWT helpers, auth decorator, password strength validation
    config.py                        # Environment loading, database config, Stripe init, upload dir
    database.py                      # SQLAlchemy db instance
    models.py                        # SQLAlchemy models plus service/helper functions
    seed_dev.py                      # Local development seed data
    migrations/                      # One-off migration scripts
    routes/                          # API blueprints
      admins.py
      alerts.py
      auto_clockout.py
      billings.py
      employees.py
      eod.py
      face.py
      inventory.py
      inventory_history.py
      managers.py
      stores.py
      tenants.py
      timeclock.py
    services/
      face_service.py                # Face descriptor comparison, image compression helpers
    utils/
      storage.py                     # Tenant storage paths/usage/limits
  frontend/
    pages/                           # Static HTML pages
    static/
      css/style.css
      js/script.js                   # Shared frontend app logic
      js/face-recognition.js         # Browser face-api.js camera/descriptors/API calls
      js/timeclock-handler.js        # Time clock page behavior
  docs/
    FEATURES.md                      # Existing feature guide
    CHATGPT_PROJECT_CONTEXT.md       # This handoff document
  .env.example                       # Environment variable reference
  requirements.txt
  runtime.txt
  vercel.json
  README.md
```

## 4. Runtime and Startup

Python runtime is defined in `runtime.txt` as Python 3.11.

Install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create environment:

```powershell
copy .env.example .env
```

Run locally from the project root:

```powershell
$env:FLASK_APP = "backend.app:create_app"
$env:FLASK_ENV = "development"
$env:FLASK_DEBUG = "true"
flask run --host 0.0.0.0 --port 5000
```

Alternative:

```powershell
python backend/app.py
```

Important local URLs:

- Login: `http://localhost:5000/` or `http://localhost:5000/login.html`
- Signup: `http://localhost:5000/signup`
- Health: `http://localhost:5000/api/health`

Seed local demo data after the database is empty:

```powershell
flask --app backend.app:create_app seed-dev
```

This creates a tenant, a super admin from `.env`, a demo manager, and demo stores.

## 5. Environment Variables

Minimum:

- `SECRET_KEY`: required for JWT signing; must be strong in production
- `DATABASE_URL` or `POSTGRESQL_URI`: optional; if omitted, app uses SQLite file `timetrack.db`
- `FLASK_ENV`, `FLASK_DEBUG`: local development flags
- `SUPER_ADMIN_USERNAME`, `SUPER_ADMIN_PASSWORD`: used only by `seed-dev` to create a DB account

Stripe:

- `STRIPE_SECRET_KEY`
- `STRIPE_PRICE_ID_BASIC`
- `STRIPE_PRICE_ID_STANDARD`
- `STRIPE_PRICE_ID_PREMIUM`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_WEBHOOK_SECRET_DEV`
- `STRIPE_SUCCESS_URL`
- `STRIPE_CANCEL_URL`
- `STRIPE_BILLING_PORTAL_RETURN_URL`

SMTP:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `FROM_EMAIL`

App:

- `APP_LOGIN_URL`

## 6. App Factory and Routing

`backend/app.py` creates the Flask app. It:

- Loads `Config`
- Enables CORS
- Initializes SQLAlchemy
- Imports models and runs `db.create_all()`
- Warns about database, SMTP, and Stripe webhook configuration
- Registers Flask-Limiter with no global default limits
- Registers all API blueprints under `/api/*`
- Adds JSON error handling for API routes
- Serves frontend pages from `frontend/pages`
- Serves static assets from `frontend/static`
- Registers CLI commands for seeding and migrations

Frontend static routing:

- `/` -> `frontend/pages/login.html`
- `/login`, `/login.html`, `/index.html` -> login page
- `/<page>.html` -> matching file in `frontend/pages`
- `/signup` -> `signup.html`
- `/signup-success` -> `signup-success.html`
- `/static/css/*` -> CSS
- `/static/js/*` -> JS

## 7. User Roles

Roles are stored in JWTs and checked through `backend/auth.py`.

- `store`: physical store/location terminal. Can access dashboard, inventory, EOD, time clock.
- `manager`: manages stores, employees, inventory, EOD review, billings, alerts.
- `admin`: regional admin. Manager-style/reporting access scoped by `regions`.
- `super-admin`: tenant owner. Can manage managers/admins, subscription, reports, storage.
- Platform super admin concept exists in config/dev seed, but operational login is a manager row with `is_super_admin = true`.

Login flow in `frontend/static/js/script.js` tries, in order:

1. `/api/managers/super-admin/login`
2. `/api/admins/login`
3. `/api/stores/manager/login`
4. `/api/stores/login`

Successful sessions are stored in browser `localStorage` under `Pramaan_Session`.

## 8. Authentication Details

`backend/auth.py`:

- `generate_token(user_data, expires_in_hours=24)` creates JWTs.
- `verify_token(token)` validates JWTs.
- `get_auth_token()` reads `Authorization: Bearer <token>` or `X-Auth-Token`.
- `require_auth(roles=None)` enforces login and optional role list.
- Authenticated routes receive `g.current_user` and `g.tenant_id`.
- `validate_password_strength()` requires 8 chars, uppercase, lowercase, number, and special character.

Most API endpoints require a valid token. Public endpoints include health, signup, login endpoints, and Stripe webhook.

## 9. Data Model

Main SQLAlchemy models in `backend/models.py`:

- `Tenant`: company account, email, password hash, plan, storage quota, Stripe customer/subscription IDs, status.
- `Manager`: tenant-scoped user. Can be regular manager, admin, or super-admin. Admin regions are JSON text.
- `Store`: tenant-scoped location, login credentials, manager username, allowed IP, opening/closing time.
- `Employee`: staff member, store assignment, role, phone, hourly pay, active flag, face descriptors/images.
- `Inventory`: tenant/store SKU item, name, quantity, device type.
- `InventoryHistory`: JSON snapshot of store inventory for a date.
- `TimeClock`: employee clock-in/out entries, store ID, hours, face image metadata, confidence scores.
- `Alert`: manager alerts such as late clock-in and auto clock-out.
- `EOD`: daily end-of-day financial report, sales/payment totals, denominations, notes, submitted-by.
- `StoreBilling`: monthly bill payment records by tenant/store/type.

Important constraints:

- Tenant isolation is central. Many unique constraints are composite with `tenant_id`.
- Stores are often referenced by store name/string (`store_id`) rather than numeric store ID.
- Some legacy helper code provides MongoDB-like collection wrappers over SQLAlchemy for backward compatibility.

## 10. Main Backend API

All API routes are prefixed by `/api`.

### Health

- `GET /api/health`

### Tenants

- `POST /api/tenants/signup`: create tenant, Stripe customer, checkout session.
- `POST /api/tenants/webhook/stripe`: Stripe webhook, activates tenants and creates super-admin manager.
- `POST /api/tenants/login`: email/password tenant login for super-admin.
- `GET /api/tenants/me`: current tenant.
- `PUT /api/tenants/plan`: placeholder plan upgrade endpoint.
- `GET /api/tenants/storage`: current tenant storage info.
- `GET /api/tenants/subscription`: subscription info.
- `POST /api/tenants/subscription/upgrade`: create Stripe checkout for upgrade.
- `POST /api/tenants/subscription/cancel`: cancel subscription at period end.
- `POST /api/tenants/subscription/reactivate`: reactivate subscription.
- `GET /api/tenants/subscription/billing-portal`: Stripe billing portal URL.
- `GET /api/tenants/config/debug`: Stripe/env debug info.
- `POST /api/tenants/storage/recalculate`: recalculate storage.

### Stores

- `GET /api/stores/`: list stores for tenant, optional `manager_username`.
- `POST /api/stores/`: manager creates store; sets allowed IP to creator IP.
- `POST /api/stores/login`: store login, IP restricted if `allowed_ip` is set.
- `PUT /api/stores/`: manager updates store.
- `DELETE /api/stores/`: manager deletes store.
- `POST /api/stores/manager/login`: manager/admin/super-admin login from manager table.

### Managers

- `GET /api/managers/`: list managers.
- `POST /api/managers/`: create manager.
- `PUT /api/managers/<username>`: update manager.
- `GET /api/managers/<username>`: get one manager.
- `POST /api/managers/super-admin/login`: super-admin login.

### Admins

- `GET /api/admins/`: list admins.
- `GET /api/admins/available-regions`: list region options.
- `POST /api/admins/`: create admin.
- `PUT /api/admins/<username>`: update admin.
- `GET /api/admins/<username>`: get admin.
- `POST /api/admins/login`: admin login.

### Employees

- `GET /api/employees/`: list employees, commonly filtered by `store_id`.
- `GET /api/employees/active-count`: active employee count.
- `POST /api/employees/`: add employee.
- `PUT /api/employees/<employee_id>`: update employee.
- `DELETE /api/employees/<employee_id>`: delete/deactivate employee.

### Face Recognition

- `POST /api/face/add-appearance`: add another descriptor/image for an employee.
- `POST /api/face/register`: register employee face.
- `POST /api/face/recognize`: match descriptor against employees.
- `GET /api/face/employees/<employee_id>`: get employee face info.

### Time Clock

- `POST /api/timeclock/clock-in`: legacy clock-in by employee ID.
- `POST /api/timeclock/clock-out`: legacy clock-out by entry ID.
- `POST /api/timeclock/clock-in-face`: face-recognition clock-in.
- `POST /api/timeclock/clock-out-face`: face-recognition clock-out.
- `GET /api/timeclock/today`: entries for current day and store.
- `GET /api/timeclock/history`: store history, optional `days`.
- `GET /api/timeclock/employee/<employee_id>/history`: employee history.

### Inventory

- `GET /api/inventory/`: list inventory, filter by `store_id`, `device_type`.
- `POST /api/inventory/`: add item.
- `PUT /api/inventory/`: update quantity/name/SKU/device type.
- `DELETE /api/inventory/`: remove item.

### Inventory History

- `GET /api/inventory/history/`: list snapshots.
- `POST /api/inventory/history/snapshot`: create snapshot for a store/date.

### EOD

- `GET /api/eod/`: list EOD reports.
- `POST /api/eod/`: create EOD report.
- `GET /api/eod/cash-report`: aggregate cash report.
- `GET /api/eod/card-report`: aggregate card report.

### Billings

- `GET /api/billings/`: list billing records.
- `POST /api/billings/pay`: record payment.
- `GET /api/billings/managers`: grouped billing data for managers.
- `GET /api/billings/manager/<manager_username>`: billing data for one manager.

### Alerts

- `GET /api/alerts/`: list alerts.
- `POST /api/alerts/<alert_id>/read`: mark read.
- `GET /api/alerts/unread-count`: unread count.

### Auto Clock-Out

- `POST /api/auto-clockout/auto-clockout`: run auto clock-out logic after store closing time.

## 11. Frontend Pages

Public:

- `login.html`: unified login for store, manager, admin, super-admin.
- `signup.html`: tenant signup and plan selection.
- `signup-success.html`: Stripe checkout success.
- `pricing.html`: pricing/plan display.

Store:

- `dashboard.html`: store home.
- `timeclock.html`: face-recognition clock-in/out.
- `inventory.html`: store inventory editing.
- `eod.html`: end-of-day report form.

Manager:

- `manager.html`: manager store dashboard and store management.
- `add-employee.html`: add employee and face registration.
- `list-employees.html`: employee list/search.
- `employee-activities.html`: employee activity detail.
- `billings-payments.html`: billing payment entry.
- `alerts.html`: manager alert list.
- `store-employees.html`: employees for selected store.
- `store-employees-today.html`: today clock status for selected store.
- `store-employees-history.html`: historical employee time entries.
- `store-inventory.html`: manager inventory view/edit for selected store.
- `store-inventory-history.html`: inventory snapshots.
- `view-inventory-snapshot.html`: snapshot detail.
- `store-eod.html`, `store-eod-list.html`, `store-eod-detail.html`: EOD manager review flows.

Admin/Super Admin:

- `super-admin.html`: tenant owner dashboard.
- `admin.html`: regional admin dashboard.
- `all-managers.html`: manager list.
- `add-manager.html`: create manager.
- `all-admins.html`: admin list.
- `add-admin.html`: create admin.
- `cash-report.html`: cash report.
- `card-report.html`: card/card-like report.
- `billings.html`: company-wide billing overview.

## 12. Frontend JavaScript

`frontend/static/js/script.js` is the central frontend script. It contains:

- Toast notification helpers.
- Confirmation dialog helpers.
- API helpers: `apiGet`, `apiPost`, `apiPut`, `apiDelete`.
- Session helpers using `localStorage`.
- Login flow.
- Inventory functions.
- Employee functions.
- EOD functions.
- Store/manager/admin page logic.
- Per-page behavior selected by current page path.

`frontend/static/js/face-recognition.js`:

- Loads face-api.js models from `https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model`.
- Opens camera via `navigator.mediaDevices.getUserMedia`.
- Captures video frames to canvas.
- Generates 128-dimensional face descriptors.
- Calls backend face/timeclock APIs.

`frontend/static/js/timeclock-handler.js`:

- Runs only on the timeclock page.
- Requires store session.
- Shows camera for clock-in or clock-out.
- Captures and recognizes face.
- Requires minimum frontend confidence of 30%.
- Calls face clock-in/out endpoints.
- Refreshes current clock status every 30 seconds.

## 13. Face Recognition Flow

1. Manager adds employee and registers face descriptors.
2. Browser loads face-api.js models.
3. Store employee opens `timeclock.html`.
4. Camera captures face.
5. Browser generates a descriptor and base64 JPEG.
6. Frontend calls `/api/face/recognize` or `/api/timeclock/clock-in-face`.
7. Backend compares descriptor to registered employees with Euclidean distance.
8. Backend threshold is approximately `0.6`, with a minimum confidence check around `0.3`.
9. On successful clock-in/out, backend stores time entry, compressed face image, confidence, and hours worked.
10. If a high-confidence new appearance differs enough, backend can append descriptor history, limited to recent descriptors.

## 14. Store Timing and Alerts

Stores can have `opening_time` and `closing_time` in `HH:MM`.

- Clock-in is allowed starting 30 minutes before opening.
- Clock-ins after opening can create `late_clock_in` alerts for managers.
- Auto clock-out can close open entries 15 minutes after closing time.
- Auto clock-out can create manager alerts.

Important: code uses UTC timestamps in many backend places, while store times are plain `HH:MM`. If adding timezone behavior, audit this carefully.

## 15. Inventory

Inventory is tenant and store scoped.

Fields:

- SKU
- name
- quantity
- device_type: `metro`, `discontinued`, `unlocked`

Default inventory items are defined in `get_default_inventory_items()` and can be added to stores. Snapshots are saved in `InventoryHistory` as JSON arrays.

## 16. EOD Reports

EOD includes:

- `report_date`
- notes
- cash amount
- credit amount
- card1 amount
- QPay amount
- boxes count
- accessories amount
- magenta amount
- inventory sold
- over/short
- total1
- bill denominations: 100, 50, 20, 10, 5, 1 counts and totals
- total bills
- submitted by

Cash and card reports aggregate EOD records across store/date ranges.

## 17. Billing

`StoreBilling` tracks monthly bill payments per store.

Types appear to be:

- electricity
- wifi
- gas

Helpers group billing data by store and current billing month (`YYYY-MM`).

## 18. Storage Tracking

Tenants have `max_storage_bytes` and `used_storage_bytes`. Face images and tenant files can update usage through `backend/utils/storage.py`.

Default storage appears to be 1 GB unless changed by plan logic.

## 19. Deployment

Vercel:

- `vercel.json` routes all requests to `api/index.py`.
- `api/index.py` imports `backend.app:create_app()`.
- Serverless startup attempts to create all tables but continues if DB is temporarily unavailable.
- Environment variables must be configured in Vercel.
- PostgreSQL is recommended for production.

Traditional server:

```bash
gunicorn "backend.app:create_app()" --bind 0.0.0.0:8000
```

## 20. CLI Commands

Registered in `backend/app.py`:

- `seed-dev`
- `seed-stores`
- `add-inventory <store_name>`
- `migrate`
- `add-inventory-sold-to-eod`
- `add-inventory-to-stores`
- `check-inventory`
- `create-billings-table`
- `add-billing-month`
- `add-manager-location`
- `add-admin-fields`
- `add-store-timings`
- `create-alerts-table`

Use:

```powershell
flask --app backend.app:create_app <command>
```

## 21. Important Implementation Notes and Risks

- The project is a static frontend plus Flask backend. Do not add a separate frontend dev server unless deliberately migrating the frontend.
- `SECRET_KEY` must be set. JWT signing depends on it.
- Login credentials in `.env` are not magic login accounts. `seed-dev` must create actual DB rows.
- Store login can be IP restricted through `allowed_ip`; this can cause login failures when testing from a different IP.
- Many records reference stores by name string rather than numeric ID. Store renames require careful cascading logic.
- Most timestamps use UTC. Store opening/closing times are stored as local-looking `HH:MM` strings without timezone.
- Face descriptors/images are stored in DB text fields; storage quota code tracks image sizes.
- The Stripe config/debug endpoint currently exists and is public. If this app is public, consider restricting or removing it.
- Some route modules have extensive error logging. In production, make sure logs do not expose secrets or sensitive user data.
- SQLite is acceptable for local dev only. Production should use PostgreSQL.
- The app has one large `script.js` file with many page-specific branches. Changes to shared helpers can affect many pages.

## 22. Good Prompts to Give ChatGPT With This Context

For debugging:

```text
Here is the project context for my Flask/static HTML app. Please help me debug [issue]. First identify the likely files involved, then suggest a minimal patch that matches the existing architecture.
```

For adding a feature:

```text
Using this project context, design and implement [feature]. Keep the Flask API plus static HTML/JS architecture. Include backend route/model changes, frontend page or JS changes, and any migration/seed steps.
```

For deployment:

```text
Using this project context, help me deploy this app to Vercel with PostgreSQL, Stripe, and SMTP. Give me exact environment variables and verification steps.
```

For code review:

```text
Using this project context, review the architecture for security, data isolation, and production readiness. Prioritize concrete bugs and risky implementation details.
```

