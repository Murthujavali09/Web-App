# BranchPilot â€” Feature Guide

This document describes what the application does, who uses each part, and how the main modules fit together.

---

## Overview

**BranchPilot** helps retail organizations run day-to-day store operations:

1. Employees **clock in/out** using **face recognition**
2. Stores track **phone/device inventory** and daily snapshots
3. Stores submit **end-of-day (EOD)** reports with cash, card, and denomination breakdowns
4. Managers oversee **multiple stores**, **employees**, **billings**, and **alerts**
5. Company owners (**tenants**) sign up via **Stripe**, manage **managers/admins**, and view consolidated reports

Data is isolated per **tenant** (company). Stores, employees, inventory, and reports belong to one tenant.

---

## Authentication and roles

### Login (`login.html`)

Single login page for:

- **Store** accounts (per physical location)
- **Manager** accounts (assigned stores)
- **Admin** accounts (region-scoped oversight)
- **Super Admin** (tenant owner for that company)

JWT tokens are stored in the browser after login. API routes under `/api/*` require a valid token except public routes (health, signup, some tenant endpoints).

### Store login restrictions

When a manager creates a store, the store can be **locked to the creatorâ€™s IP address** (`allowed_ip`). Only clients on that network can log in as that storeâ€”useful for fixed in-store terminals.

### Super admin login (tenant owner)

The login page uses **username + password** and calls `/api/managers/super-admin/login`. The account must exist in the **`managers` table** with `is_super_admin = true`.

For local development, run once:

```powershell
flask --app backend.app:create_app seed-dev
```

That reads `SUPER_ADMIN_USERNAME` and `SUPER_ADMIN_PASSWORD` from `.env` and creates the database record. **Those env vars alone do not log you in** until `seed-dev` has been run.

In production, super admins are normally created when a company completes Stripe signup (webhook creates the tenant and manager).

---

## Tenant signup and subscriptions

### Sign up (`signup.html`, `signup-success.html`)

New companies register as **tenants** with:

- Company name, email, password
- Subscription **plan** (basic / standard / premium) via **Stripe Checkout**

After payment, Stripe webhooks activate the tenant. Email notifications (welcome, credentials) use **SMTP** when configured.

### Super Admin dashboard (`super-admin.html`)

Tenant owner capabilities:

- View company overview and storage usage
- **Manage managers** (`all-managers.html`, `add-manager.html`)
- **Manage admins** (`all-admins.html`, `add-admin.html`)
- **Subscription** management (Stripe billing portal)
- Quick links to **cash report**, **card report**, **billings** across stores

### Admin dashboard (`admin.html`)

Regional admins (assigned **regions** in JSON on the manager record):

- Similar reporting access as super admin for their regions
- Manager list for their scope
- Cash/card/billing reports for assigned areas

### Pricing (`pricing.html`)

Marketing/plan comparison page for subscription tiers (used with Stripe price IDs).

---

## Store operations

### Store dashboard (`dashboard.html`)

After store login, staff see quick actions:

| Action | Page | Description |
|--------|------|-------------|
| Time Clock | `timeclock.html` | Clock in/out with webcam face match |
| Inventory | `inventory.html` | Adjust stock counts by SKU/device |
| End of Day | `eod.html` | Submit daily close-out report |

â€œComing soonâ€ placeholders on the dashboard are UI stubs only (not implemented yet).

---

## Time clock and face recognition

### Time clock (`timeclock.html`)

- Lists active employees for the store
- **Clock in**: captures face via browser (`face-api.js`), sends descriptor to API, matches against registered employees
- **Clock out**: same face verification flow
- Stores optional face images and **confidence** scores on each entry

### Employee face registration

When managers add employees (`add-employee.html`), they can register face descriptors. The backend (`backend/services/face_service.py`) compares 128-dimensional descriptors using Euclidean distance (threshold ~0.6).

### Store hours

Each store has:

- **Opening time** â€” employees may clock in starting **30 minutes before** open
- **Closing time** â€” used for late/auto clock-out logic

Configured when creating/editing a store on the manager dashboard.

### Auto clock-out (`/api/auto-clockout`)

If an employee forgets to clock out, a scheduled job (or manual API call) can run **15 minutes after closing time** to:

- Set `clock_out` on open entries
- Calculate `hours_worked`
- Optionally create **alerts** for managers

Call this endpoint periodically in production (cron, Vercel cron, etc.).

### Employee history (manager view)

| Page | Purpose |
|------|---------|
| `store-employees.html` | Employees for a selected store |
| `store-employees-today.html` | Who is clocked in today |
| `store-employees-history.html` | Historical time entries |
| `employee-activities.html` | Activity detail views |

---

## Inventory

### Store inventory (`inventory.html`)

- Track items by **SKU**, **name**, **quantity**
- **Device types**: `metro`, `discontinued`, `unlocked`
- Increase/decrease counts during the day

### Manager store inventory (`store-inventory.html`)

Managers open a store from `manager.html` to view/edit that storeâ€™s inventory (same data, manager context with `?store=` query param).

### Inventory history (`store-inventory-history.html`)

- Daily **snapshots** of all items for a store
- View past dates and compare stock levels
- `view-inventory-snapshot.html` for a single snapshot detail

Default inventory SKUs can be seeded when a store is created (`add_default_inventory_to_store` in models).

---

## End of day (EOD)

### Store EOD form (`eod.html`)

Stores submit a daily report including:

| Field group | Examples |
|-------------|----------|
| Sales | Cash, credit, card1, QPay, accessories, Magenta |
| Operations | Boxes count, **inventory sold**, notes |
| Cash drawer | Bill denominations ($100, $50, $20, $10, $5, $1) |
| Reconciliation | Over/short, totals |

### Manager EOD review

| Page | Purpose |
|------|---------|
| `store-eod-list.html` | List EOD reports by date for a store |
| `store-eod-detail.html` | Full detail for one report |
| `store-eod.html` | Alternate EOD entry/review flows |

Managers and admins use these with `?store=` (and optional `view_as`) to audit submissions.

---

## Manager dashboard

### Manager home (`manager.html`)

- **Store overview** cards for each assigned store
- **Add store** â€” name, credentials, total boxes, opening/closing times, IP lock
- **Edit store** â€” update timings, credentials, box counts
- Per-store shortcuts (from JS-rendered cards):
  - Inventory management
  - Inventory history
  - EOD list
  - Employee views

### Employees

| Page | Purpose |
|------|---------|
| `add-employee.html` | Create employee, hourly pay, role, face registration |
| `list-employees.html` | Search/list employees across stores |

### Billings (`billings-payments.html`)

Managers record and track **store billing payments** (amounts owed/paid per store per period). Tied to `StoreBilling` model and `/api/billings`.

### Alerts (`alerts.html`)

Managers see notifications such as:

- **Late clock-in** (after store open rules)
- **Auto clock-out** events

Mark alerts read via `/api/alerts`. Filter by store and read/unread status.

---

## Reports (Super Admin / Admin)

### Cash report (`cash-report.html`)

Aggregated **cash** totals from EOD submissions across stores (filters by date range and scope).

### Card report (`card-report.html`)

Aggregated **card/credit** payment totals from EOD data.

### Billings overview (`billings.html`)

Company-wide view of store billing records and payment status (super admin / admin).

---

## API overview

All JSON APIs are prefixed with `/api/`.

| Prefix | Module | Main capabilities |
|--------|--------|-------------------|
| `/api/tenants` | Signup, Stripe webhooks, tenant profile, email |
| `/api/stores` | Store CRUD, store/manager login |
| `/api/managers` | Manager CRUD, super-admin login |
| `/api/admins` | Admin user management |
| `/api/employees` | Employee CRUD, face data |
| `/api/timeclock` | Clock in/out, entries, hours |
| `/api/face` | Face registration and verification |
| `/api/inventory` | Stock levels |
| `/api/inventory/history` | Snapshots |
| `/api/eod` | EOD submit and retrieve |
| `/api/billings` | Store billing records |
| `/api/alerts` | Manager alerts |
| `/api/auto-clockout` | Batch auto clock-out |

**Health:** `GET /api/health` â†’ `{ "status": "ok" }`

Rate limiting applies to login endpoints (5 requests per minute per IP).

---

## Data model (summary)

| Entity | Description |
|--------|-------------|
| **Tenant** | Company account, plan, Stripe IDs, storage quota |
| **Manager** | Store supervisor; may be super-admin or admin for tenant |
| **Store** | Location with login, box count, hours, optional IP lock |
| **Employee** | Staff with pay rate, face descriptors, store assignment |
| **TimeClock** | Clock in/out records with hours and face metadata |
| **Inventory** | SKU-level stock per store |
| **InventoryHistory** | Daily snapshot JSON per store |
| **EOD** | End-of-day financial report per store/date |
| **StoreBilling** | Billing/payment tracking per store/month |
| **Alert** | Manager notifications |

---

## Optional integrations

### Stripe

Required for paid signup:

- `STRIPE_SECRET_KEY`
- `STRIPE_PRICE_ID_BASIC`, `STRIPE_PRICE_ID_STANDARD`, `STRIPE_PRICE_ID_PREMIUM`
- `STRIPE_WEBHOOK_SECRET` (or `STRIPE_WEBHOOK_SECRET_DEV` locally)
- `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`

### Email (SMTP)

For welcome and notification emails:

- `SMTP_USER`, `SMTP_PASSWORD`
- `SMTP_HOST`, `SMTP_PORT`, `FROM_EMAIL`

### Security

- `SECRET_KEY` â€” **required in production** for JWT
- Never commit `.env` (listed in `.gitignore`)

---

## Page index

| File | Audience | Function |
|------|----------|----------|
| `login.html` | All | Login |
| `signup.html` | Public | New tenant registration |
| `signup-success.html` | Public | Post-checkout success |
| `pricing.html` | Public | Plan info |
| `dashboard.html` | Store | Store home |
| `timeclock.html` | Store | Clock in/out |
| `inventory.html` | Store | Daily inventory |
| `eod.html` | Store | End of day form |
| `manager.html` | Manager | Store list & management |
| `add-employee.html` | Manager | Add staff |
| `list-employees.html` | Manager | Employee list |
| `billings-payments.html` | Manager | Store billings |
| `alerts.html` | Manager | Notifications |
| `store-*.html` | Manager | Per-store inventory, EOD, employees |
| `super-admin.html` | Tenant owner | Company admin |
| `admin.html` | Regional admin | Scoped admin |
| `all-managers.html` | Super/Admin | Manager list |
| `all-admins.html` | Super Admin | Admin list |
| `add-manager.html` | Super Admin | Create manager |
| `add-admin.html` | Super Admin | Create admin |
| `cash-report.html` | Super/Admin | Cash aggregates |
| `card-report.html` | Super/Admin | Card aggregates |
| `billings.html` | Super/Admin | Billing overview |
| `employee-activities.html` | Manager | Employee activity |
| `view-inventory-snapshot.html` | Manager | Snapshot detail |

---

## Planned / placeholder UI

The store dashboard â€œComing soonâ€ section mentions **Inventory Dash** and **Store Targets**â€”these are not implemented yet; they are visual placeholders only.
