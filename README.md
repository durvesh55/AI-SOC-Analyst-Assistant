# AI SOC Analyst Assistant

A full-stack **SOC incident-management and investigation platform** for security analysts.
Analysts triage simulated alerts, open investigation cases, write notes and findings, see
**suggested** MITRE ATT&CK mappings, keep an audit trail and export PDF investigation reports.

> **Scope:** this is an *educational* project. It is **not** a production SIEM and **not** an autonomous
> threat-detection system. All alerts are simulated, and the "AI" in the name is an assistant-style
> workflow: MITRE suggestions come from transparent keyword/category **rules**, not machine learning.

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, REST, JWT auth, RBAC |
| Frontend | React 18 (JavaScript), HTML, CSS (Vite dev server) |
| Database | MongoDB (via `pymongo`) |
| Other | Git, ReportLab (PDF), FastAPI Swagger/OpenAPI |

---

## Quick start (Windows)

You need: **Python 3.11+**, **Node.js 18+**, **MongoDB** running locally, **Git**.

```powershell
# 0) MongoDB  (pick ONE)
net start MongoDB                      # if installed as a Windows service (run terminal as Administrator)
# or, in a spare terminal:
mongod --dbpath C:\data\db             # the folder must already exist

# 1) Backend  (terminal 1)
cd backend
python -m venv venv
venv\Scripts\activate                  # macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env                 # then edit JWT_SECRET (see "Configuration")
python -m app.seed                     # dev accounts + 20 simulated alerts + 2 cases
python -m uvicorn app.main:app --port 8001 --reload

# 2) Frontend  (terminal 2)
cd frontend
npm install
npm run dev
```

| What | URL |
|---|---|
| **Landing page + app (open this)** | http://localhost:5173 (the app itself lives at `/dashboard` after login) |
| API | http://localhost:8001 |
| Swagger / OpenAPI docs | http://localhost:8001/docs |
| Health check | http://localhost:8001/api/health |

> **Why port 8001?** Port 8000 is commonly taken by other software (on the development machine it was
> Splunk). If you change the port, set `VITE_PROXY_TARGET` in `frontend/.env` to match.

### Development accounts (created ONLY by `python -m app.seed`)

| Role | Username | Password (default from `.env.example`) |
|---|---|---|
| Admin | `admin` | `Admin@12345` |
| Analyst | `analyst1` | `Analyst@12345` |
| Analyst | `analyst2` | `Analyst@12345` |

These exist for **local development only**. Change `SEED_*_PASSWORD` in `.env` before seeding, and never seed a
shared/production database. `python -m app.seed --reset` wipes this app's collections (in the `MONGO_DB`
database only) and reseeds.

---

## Features

**Authentication & authorization** – registration (always creates an *Analyst*), login by username or email,
bcrypt password hashing, JWT access tokens with expiry, real logout (token revocation), per-user lockout after
10 failed logins in 15 min, Admin/Analyst roles enforced **on the backend**.

**Alerts** – create / view / edit / search; filter by severity, status, category, assignee and date range;
severities *Critical/High/Medium/Low*; statuses *New / Under Investigation / Resolved / False Positive*; assign
to analysts; every change is kept in the alert's history.

**Cases** – open a case from one or more alerts (unique `CASE-000001` IDs); assign analysts; *Open / In Progress /
Closed*; investigation notes; findings and conclusion; a timeline of everything that happened; close (with an
outcome that is applied to the linked alerts) and **reopen (Admin only)**.

**MITRE ATT&CK** – 21 rules map alert category + keywords to technique ID, name and tactic, with a plain-language
*reason* and *matched terms*. Always labelled **"Suggested – must be validated by an analyst"**.

**Audit log** – login/logout/failed login, alert create/update/status/assign, case create/assign/status/notes/
close/reopen, report generation, admin user actions. **Append-only**: no API can modify or delete entries.

**Dashboard** – everything is computed from MongoDB on every request: totals, alerts by severity/status, open &
resolved cases, false positives, 14-day alert trend, analyst workload, recent activity.

**PDF reports** – case ID, alert info, severity, assignee, notes, MITRE mapping, timeline, findings & conclusion.

**Landing page** – a public, animated front page at `/` (live simulated alert feed, animated counters, workflow walkthrough, FAQ and a working **ATT&CK suggester** that calls the real backend without login via `POST /api/public/mitre-suggest`, rate-limited and database-free).

**UI pages** – Landing, Login, Registration, Dashboard, Alerts, Alert details, Cases, Case investigation, Audit logs,
Admin user management, Profile/settings. Responsive (works at phone width).

### Who can do what

| Action | Analyst | Admin |
|---|---|---|
| View all alerts, cases, dashboard | ✅ | ✅ |
| Create alerts | ✅ | ✅ |
| Edit an alert | only if unassigned or assigned to them | any |
| Assign alert/case | only **to themselves** (claim/release) | to anyone |
| Create a case from alerts | alerts unassigned or theirs | any |
| Add notes / edit / close a case | only cases assigned to them | any |
| **Reopen** a closed case | ❌ | ✅ |
| View audit log | **own entries only** | everything |
| Manage users / roles / disable accounts | ❌ | ✅ |
| Modify audit records | ❌ nobody | ❌ nobody |

---

## Project structure

```
AI SOC ASSISTANT/
├── README.md                 ← you are here
├── LEARNING_GUIDE.md         ← beginner-friendly walkthrough of the code
├── DEPLOYMENT.md             ← put it online (MongoDB Atlas + Render, free tier)
├── render.yaml               ← Render Blueprint (API + static web)
├── backend/
│   ├── .env.example          ← copy to .env (never commit .env)
│   ├── requirements.txt      ← runtime deps          requirements-dev.txt ← + test deps
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py           ← FastAPI app, CORS, security headers, error handlers
│   │   ├── config.py         ← settings from environment variables
│   │   ├── database.py       ← Mongo connection, $jsonSchema validators, indexes
│   │   ├── security.py       ← bcrypt + JWT helpers
│   │   ├── deps.py           ← get_current_user / require_admin dependencies
│   │   ├── schemas.py        ← Pydantic request models (input validation)
│   │   ├── utils.py          ← ObjectId parsing, JSON serialisation, ID counters
│   │   ├── seed.py           ← development data (never run on production)
│   │   ├── create_admin.py   ← create the first Admin safely (production bootstrap)
│   │   ├── routers/          ← auth, users, alerts, cases, audit, dashboard, public (HTTP endpoints)
│   │   └── services/         ← mitre.py (rules), audit.py, pdf.py, lookup.py, common.py
│   └── tests/                ← pytest suite (86 tests)
├── frontend/
│   ├── package.json, vite.config.js, index.html, .env.example
│   └── src/
│       ├── main.jsx, App.jsx (routes), styles.css
│       ├── api/client.js     ← fetch wrapper (adds JWT, handles errors/expiry)
│       ├── context/          ← AuthContext, ToastContext
│       ├── components/       ← Layout, ProtectedRoute, AlertForm, ui.jsx (Badge, Modal, Card, ...)
│       └── pages/            ← one file per screen (Landing.jsx + landing.css = public front page)
└── e2e/                      ← browser end-to-end test (Puppeteer)
```

## Configuration

`backend/.env` (copy from `.env.example`):

| Variable | Meaning |
|---|---|
| `MONGO_URI`, `MONGO_DB` | MongoDB location and database name (default `ai_soc_assistant`) |
| `JWT_SECRET` | **Must be changed.** `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime (default 60) |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `ENVIRONMENT` | `development` (default) or `production`. In production the server **refuses to start** with a weak/default `JWT_SECRET` |
| `REGISTRATION_INVITE_CODE` | Optional. If set, self-registration requires this code (the register form shows the field automatically) |
| `SEED_ADMIN_PASSWORD`, `SEED_ANALYST_PASSWORD` | Passwords used by `python -m app.seed` only |

`.env` is git-ignored. Only `.env.example` (placeholders) is committed.

## Backend architecture

```
HTTP request ─► CORS + security-headers middleware
            ─► router function (routers/*.py)
                 ├─ Depends(get_current_user)  → verify JWT, check revocation, load user (role from DB)
                 ├─ Pydantic model             → validate/sanitise the request body (422 on bad input)
                 ├─ authorization check        → role + ownership (403 if not allowed)
                 ├─ MongoDB operations         → pymongo
                 └─ audit.log_event(...)       → append-only audit record
            ─► JSON response (ObjectId/datetime serialised; password hashes never returned)
```

Why each supporting library (beyond FastAPI/React/MongoDB):

| Library | Why |
|---|---|
| `uvicorn` | ASGI server that runs FastAPI |
| `pymongo` | Official MongoDB driver (synchronous – simplest to read and learn; FastAPI runs sync endpoints in a thread pool) |
| `pydantic` + `pydantic-settings` + `email-validator` | Request validation (types, lengths, enums, emails) and typed settings from `.env` |
| `bcrypt` | Slow, salted password hashing (used directly; `passlib` is unmaintained and breaks with new bcrypt) |
| `PyJWT` | Creating/verifying JSON Web Tokens |
| `python-multipart` | Lets FastAPI read the OAuth2 *form* login used by Swagger's "Authorize" button |
| `reportlab` | Pure-Python PDF generation |
| `pytest`, `httpx`, `mongomock` *(dev)* | Test runner, FastAPI TestClient transport, in-memory MongoDB for tests |
| `react-router-dom` *(frontend)* | Client-side page routing |
| `vite` + `@vitejs/plugin-react` *(frontend dev)* | Fast dev server / bundler; proxies `/api` to the backend |
| `puppeteer-core` *(e2e)* | Drives a real browser for the end-to-end test |

## Database schema (MongoDB, database `ai_soc_assistant`)

All timestamps are UTC. `$jsonSchema` validators (required fields + enums) and indexes are created at startup by
`database.init_db()`.

**`users`** – `_id`, `username` (unique, lowercase), `email` (unique, lowercase), `full_name`, `password_hash`
(bcrypt), `role` (`Admin|Analyst`), `is_active`, `created_at`, `updated_at`, `last_login`

**`alerts`** – `_id`, `alert_id` (unique, `ALT-000001`), `title`, `description`, `severity`, `status`, `category`,
`source_ip`, `destination_ip`, `hostname`, `affected_user`, `indicators[]`, `event_time`,
`assigned_to` → users._id, `case_id` → cases._id, `mitre_suggestions[]`, `history[]` (embedded
`{at, by_id, by_username, action, detail}`), `created_by` → users._id, `created_at`, `updated_at`
*Indexes:* `alert_id` unique; `(severity,status)`; `assigned_to`; `created_at` desc.

**`cases`** – `_id`, `case_id` (unique, `CASE-000001`), `title`, `status` (`Open|In Progress|Closed`), `severity`,
`alert_object_ids[]` → alerts._id and `alert_ids[]` (display IDs), `assigned_to`, `notes[]` (embedded
`{id, author_id, author_username, text, created_at}`), `findings`, `conclusion`, `outcome`, `mitre_suggestions[]`,
`timeline[]`, `created_by`, `created_at`, `updated_at`, `closed_at`, `closed_by`
*Indexes:* `case_id` unique; `(status, assigned_to)`.

**`audit_logs`** – `_id`, `timestamp`, `action`, `actor_id`, `actor_username`, `resource_type`, `resource_id`,
`details{}` (credential-like keys are stripped), `ip`
*Indexes:* `timestamp` desc; `actor_id`; `action`.

Supporting collections: **`counters`** (atomic sequence numbers for `ALT-`/`CASE-` IDs) and **`revoked_tokens`**
(`jti`, `expires_at`; a TTL index removes entries automatically after the token would have expired anyway).

*Design note:* history, notes and timeline are **embedded** in their parent documents because they are small,
always read together with the parent, and need atomic `$push` updates.

## API reference

Interactive documentation with request/response schemas: **http://localhost:8001/docs** (use *Authorize* with a
username/email + password). Summary (all under `/api`, JSON, `Authorization: Bearer <token>` unless noted):

| Method & path | Purpose | Access |
|---|---|---|
| `POST /auth/register` | Create an Analyst account | public |
| `POST /auth/login` | `{identifier, password}` → JWT + user | public |
| `POST /auth/token` | OAuth2 form login (Swagger) | public |
| `POST /auth/logout` | Revoke current token | any user |
| `GET /auth/me` · `PATCH /auth/me` | Read / update own profile | any user |
| `POST /auth/change-password` | Change password (revokes token) | any user |
| `GET /users/assignable` | Active users for assignment dropdowns | any user |
| `GET /users` · `POST /users` · `PATCH /users/{id}` | List / create / change role & active flag | **Admin** |
| `POST /alerts` · `GET /alerts` · `GET /alerts/{id}` | Create / search & filter / details | any user |
| `PATCH /alerts/{id}` · `POST /alerts/{id}/assign` | Update fields+status / assign | owner or Admin |
| `POST /cases` | Create case from `alert_ids` | any user (ownership rules) |
| `GET /cases` · `GET /cases/{id}` | List & filter / full case | any user |
| `PATCH /cases/{id}` | title, severity, status, findings, conclusion | assignee or Admin |
| `POST /cases/{id}/assign` · `/notes` · `/close` | Assign / add note / close | assignee or Admin |
| `POST /cases/{id}/reopen` | Reopen closed case | **Admin** |
| `GET /cases/{id}/report` | PDF report (`application/pdf`) | any user |
| `GET /audit-logs` · `GET /audit-logs/actions` | Read-only audit trail | own (Analyst) / all (Admin) |
| `GET /dashboard` | Live statistics | any user |
| `GET /mitre/techniques` | Techniques the rule engine can suggest | any user |
| `POST /public/mitre-suggest` | Rule-based ATT&CK suggestions for the landing-page demo (20 req/min/IP, no DB access) | public |
| `GET /meta` · `GET /health` | UI enumerations (incl. `registration_invite_required`) / DB health | public |

List endpoints return `{items, total, page, page_size}` and accept `page` / `page_size`. Errors are
`{"detail": "..."}` (validation errors: `[{loc, msg}]`, never echoing submitted values).

## Testing

```powershell
# Backend: 86 tests, ~5 s, use an in-memory MongoDB (nothing real is touched)
cd backend
venv\Scripts\python -m pytest -q
```

Covers authentication (hashing, login, expiry, tampering, revocation, lockout), authorization/RBAC and ownership,
alert and case workflows, invalid input, unauthorized access, audit logging (including "no passwords in logs" and
"no write route"), MITRE mapping, PDF generation, dashboard statistics, CORS and error masking.

```powershell
# Browser end-to-end (needs MongoDB + backend + frontend running and a fresh seed)
cd backend ; python -m app.seed --reset ; cd ..
cd e2e ; npm install ; npm test
```

40 checks drive a real Chromium browser (Edge by default; set `BROWSER_PATH` for Chrome): login, filters, alert →
case → notes → PDF → close → reopen, the public landing page (live feed, counters, ATT&CK demo), audit log, admin user management, analyst restrictions, registration and a
phone-width layout check.

## Security notes

Password hashing (bcrypt, per-password salt) · JWT with `exp` and `jti`, server-side revocation on logout/password
change · role always read from the database, never trusted from the token · deactivated users lose access
immediately · RBAC and ownership enforced in the backend · strict Pydantic validation, regex-escaped search input
(no NoSQL/regex injection), `ObjectId` parsing that returns 404 not 500 · explicit CORS allow-list · security
headers (`nosniff`, `X-Frame-Options`, `no-store` on API) · generic error messages, no stack traces to clients ·
login errors identical for unknown user/wrong password · secrets only in `.env` (git-ignored) · audit details drop
credential-like keys · PDF text is XML-escaped.

## Deploying online

See **[DEPLOYMENT.md](DEPLOYMENT.md)** - MongoDB Atlas + Render (free tier), `render.yaml` Blueprint, first-admin bootstrap with `python -m app.create_admin`, invite-only registration and a production checklist. The configuration and production safety code are tested locally; a real cloud deployment has **not** been performed from this repo.

## Known limitations

* Educational scope: simulated alerts only; no log ingestion, no real detection engine.
* MITRE mappings are keyword/category rules (21 techniques) – they can miss real behaviour and produce
  false suggestions. Always analyst-validated.
* JWT is kept in `localStorage` (simple, but exposed to XSS); no refresh tokens or HTTPS handling (run behind a
  TLS reverse proxy in any real deployment).
* Login lockout is per identifier, not per IP; no email verification or password-reset flow.
* The in-memory test database (`mongomock`) cannot enforce `$jsonSchema` validators or TTL expiry. These were
  checked manually against a real MongoDB 8.x instance (seeding and the browser test ran with validators active),
  but they are not covered by automated tests.
* Dashboard trend is computed in Python from recent alerts (fine at educational scale, not for millions of rows).
* Browser end-to-end test only ran in Microsoft Edge (Chromium); Firefox/Safari were not tested.
* The login lockout and the public demo rate-limiter are in-memory per process (reset on restart, not shared across instances).
* `render.yaml`, `vercel.json` and `_redirects` are untested against the real hosting services; Docker is not used (not available on the dev machine).
* No pagination on the assignable-users list; no alert deletion (by design, for audit integrity).

## Future improvements

Refresh tokens + httpOnly cookies, password reset by email, MFA, per-IP rate limiting, alert ingestion API/webhook,
STIX/ATT&CK data import for a larger technique catalogue, file attachments/evidence on cases, comment threads,
SLA timers, Docker Compose for one-command startup, GitHub Actions CI (pytest + build), frontend unit tests.

## Design decisions (ambiguities resolved)

* Registration always creates an Analyst; Admins are created by seed or by another Admin.
* All signed-in users can **read** all alerts and cases (shared SOC visibility); **changes** follow ownership.
* "Resolved cases" on the dashboard = cases with status *Closed*.
* Closing a case sets all linked alerts to the chosen outcome (*Resolved* or *False Positive*); reopening returns them
  to *Under Investigation*.
* Analysts see only their own audit entries; Admins see all.
* The public landing page is at `/`; the authenticated app starts at `/dashboard`.
* Backend default port is **8001** (8000 is often occupied).
