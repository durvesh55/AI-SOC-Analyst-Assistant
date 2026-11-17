# Learning Guide – how this project works

This guide explains the code in plain language so you can study it step by step. Open the files it mentions side by
side with this text. Nothing here needs prior FastAPI or React knowledge, but basic Python and JavaScript help.

**Suggested reading order:** 1 → 2 → 3 (how the pieces talk) → 4–5 (security) → 6 (database) → 7–9 (the workflows) →
10–11 (MITRE, audit) → 12 (PDF) → 13 (frontend) → 14 (tests) → "How to study" at the end.

---

## 1. The big picture

```
 Browser (React app, port 5173)
    │  fetch("/api/alerts", Authorization: Bearer <JWT>)
    ▼
 Vite dev server ── proxies /api/* ──►  FastAPI backend (port 8001)
                                          │  validates, checks the user may do this
                                          ▼
                                       MongoDB (users, alerts, cases, audit_logs)
```

* The **frontend** only draws screens and sends HTTP requests. It never touches the database.
* The **backend** is the only thing allowed to read/write MongoDB. It decides what each user may do.
* They communicate with **REST + JSON**: URLs are nouns (`/api/alerts`), HTTP verbs are actions
  (`GET` read, `POST` create, `PATCH` change).

Remember this rule: **the UI hides buttons for convenience, the backend enforces the rules for security.**
Anyone can call the API without the UI, so every permission is checked in Python.

## 2. How the frontend talks to the backend

Open `frontend/src/api/client.js`. It wraps the browser's `fetch`:

```js
const res = await fetch(`${BASE}${path}...`, { method, headers: { Authorization: `Bearer ${token}` }, body });
```

1. It reads the JWT from `localStorage` and adds the `Authorization` header to every call.
2. If the server answers `401` (token expired/revoked) it clears the token and fires an `auth:expired` event; the
   `AuthContext` listens and sends you back to the login page.
3. Error bodies like `{"detail": "..."}` are turned into a readable message that pages show in a red box.

`vite.config.js` forwards `/api/*` to `http://127.0.0.1:8001`, so the browser thinks everything is one website – no
cross-origin problems in development. (The backend still has a CORS allow-list for when they are hosted separately.)

A page such as `pages/Alerts.jsx` follows a simple pattern: keep filters in the URL (`useSearchParams`), call
`api.get("/alerts", filters)` in an effect, store the result in state, render a table. Clicking a row calls
`navigate("/alerts/<id>")`, which React Router (`App.jsx`) maps to `AlertDetail.jsx`.

## 3. FastAPI routing

`backend/app/main.py` builds the app and registers routers:

```python
app.include_router(auth.router)   # each router has prefix="/api/auth", "/api/alerts", ...
```

A route is a normal Python function with a decorator (`backend/app/routers/alerts.py`):

```python
@router.post("", status_code=201)
def create_alert(body: AlertCreate, request: Request,
                 user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
```

FastAPI reads the function's **parameters** and fills them in:

| Parameter | Where it comes from |
|---|---|
| `body: AlertCreate` | the JSON request body, **validated** by the Pydantic model in `schemas.py` |
| `alert_id: str` (in the URL `"/{alert_id}"`) | the path |
| `q: str \| None = Query(...)` | the query string `?q=ssh` |
| `Depends(get_current_user)` | runs that function first and passes in its result |

`Depends` is "dependency injection": `get_current_user` authenticates the request, `get_db` supplies the database.
Tests swap `get_db` for an in-memory database without touching any route code – see `tests/conftest.py`.

Free documentation: open `http://localhost:8001/docs` – FastAPI generates it from these same type hints.

## 4. JWT authentication

Files: `security.py`, `deps.py`, `routers/auth.py`.

**Registration** (`auth.register`): the request is validated (`RegisterRequest`: username pattern, email format,
password strength), the password is hashed with **bcrypt** (`security.hash_password`) and only the hash is stored.
bcrypt adds a random salt and is deliberately slow, so stolen hashes are hard to crack.

**Login** (`auth._authenticate`):
1. look the user up by email *or* username,
2. `verify_password` compares the typed password with the stored hash,
3. if anything is wrong, answer the **same** `401 Invalid credentials` (so attackers can't learn which usernames
   exist) and write a `LOGIN_FAILED` audit entry,
4. on success create a token and return `{access_token, user}`.

**What is a JWT?** A signed string `header.payload.signature`. The payload (`create_access_token`) contains
`sub` (user id), `exp` (expiry time) and `jti` (a unique token id). The server signs it with `JWT_SECRET`. Anyone can
*read* the payload, but nobody can change it without breaking the signature. (Never put secrets in it.)

**Every protected request** goes through `deps.get_current_user`:
1. read the token from the `Authorization: Bearer ...` header,
2. `jwt.decode` verifies signature **and** expiry (expired → 401 "Token expired"),
3. check the `jti` isn't in `revoked_tokens` (that is how **logout** works – JWTs can't be "deleted", so we remember
   revoked ones until they would expire anyway),
4. load the user from MongoDB and make sure `is_active` is true (so disabling a user works immediately).

## 5. RBAC (role-based access control)

Two roles: **Admin** and **Analyst**. There are two kinds of checks:

1. **Role checks** – `deps.require_admin` is a dependency that raises `403` unless `user["role"] == "Admin"`.
   Used on user management, reopening cases:
   ```python
   def reopen_case(..., admin: dict = Depends(require_admin), ...)
   ```
2. **Ownership checks** – e.g. `can_modify_case(user, case)` in `routers/cases.py`: admins may change anything,
   analysts only cases assigned to them. `resolve_assignee` (in `services/lookup.py`) lets analysts assign work only
   to themselves.

Important detail: the **role is read from the database**, not from the token. Even a validly signed token claiming
`"role": "Admin"` gets ignored (there is a test for exactly that: `test_role_in_token_cannot_be_forged`).

Audit visibility is also role-based: in `routers/audit.py` an Analyst's query is forced to
`{"actor_id": user["_id"]}` whatever filters the client sends.

## 6. MongoDB operations

MongoDB stores **documents** (like Python dicts) in **collections** (like tables). `database.py` sets up four main
collections with validators and indexes. Typical operations you will see (`pymongo`):

```python
db.alerts.insert_one(doc)                                   # create
db.alerts.find_one({"_id": oid})                            # read one
db.alerts.find(query).sort("created_at", -1).skip(n).limit(m)  # list with paging
db.alerts.update_one({"_id": oid}, {"$set": {...}, "$push": {"history": entry}})  # change + append
db.alerts.count_documents(query)                            # for pagination totals
db.alerts.aggregate([{"$group": {"_id": "$severity", "n": {"$sum": 1}}}])  # dashboard counts
```

* `_id` is an `ObjectId`. The API sends it as a string called `id` (`utils.serialize`), and `utils.to_object_id`
  turns strings back (a bad id gives a clean 404, not a crash).
* **Unique, sequential IDs** (`ALT-000001`): `utils.next_sequence` uses `find_one_and_update` with `$inc` on a
  `counters` document. This is *atomic*, so two simultaneous requests can never get the same number.
* **References**: `alerts.assigned_to` holds a user's `_id`. `routers/…` call `services/lookup.attach_users` to look up
  names for a whole page of results in **one** query rather than one per row.
* **Embedded arrays**: `history`, `notes`, `timeline` live inside their parent document and grow with `$push`.
* **Search** (`alerts.list_alerts`): builds a query dict from filters. User text goes through `re.escape` before it
  is used in `$regex`, so someone typing `.*` can't inject a regex.

## 7. Alert workflow

```
New ──(analyst opens a case)──► Under Investigation ──(case closed)──► Resolved  or  False Positive
                                         ▲                                   │
                                         └──────── (admin reopens case) ─────┘
```

`routers/alerts.py`:
* `create_alert` – validates, assigns `ALT-######`, runs the MITRE rules, writes the first `history` entry, and an
  `ALERT_CREATED` audit record.
* `update_alert` – compares incoming fields with stored ones, writes only real changes, records
  `"severity: 'High' -> 'Critical'"` in history, recomputes MITRE suggestions, logs `ALERT_UPDATED` and/or
  `ALERT_STATUS_CHANGED`.
* `assign_alert` – ownership + assignee rules from section 5.

## 8. Incident investigation workflow

`routers/cases.py`:

1. **Create** (`create_case`): analyst picks alerts → backend checks they exist and aren't already in a case → case
   gets `CASE-######`, the highest severity of its alerts, the merged MITRE suggestions → each alert is linked and set
   to *Under Investigation*.
2. **Work** – add notes (`add_note`), edit findings/conclusion/status (`update_case`). Each action appends to the
   case **timeline** and writes an audit entry. `require_writable` rejects people who don't own the case and any change
   to a closed case.
3. **Close** (`close_case`) – requires a conclusion and an outcome; closes the case and updates every linked alert.
4. **Reopen** (`reopen_case`) – Admin only, needs a reason, restores alerts to *Under Investigation*.
5. **Report** – `GET /api/cases/{id}/report` returns a PDF (section 12).

On screen this is `pages/CaseDetail.jsx`: buttons are shown only when `canWork` is true, but remember the backend
re-checks everything.

## 9. Input validation

`schemas.py` is the front door. Examples: `severity: Literal["Critical","High","Medium","Low"]`,
`title: str = Field(min_length=3, max_length=200)`, IP addresses are parsed with Python's `ipaddress`. Invalid input
returns **422** before any of your route code runs. The custom handler in `main.py` returns only *where* and *why* a
field failed – never the submitted value (which could be a password).

## 10. MITRE ATT&CK mapping

`services/mitre.py` holds a plain Python table:

```python
("T1110", "Brute Force", "Credential Access", ["Brute Force"],            # id, name, tactic, matching categories
 ["brute force", "failed login", "password spray", ...],                  # keywords
 "Repeated failed authentication attempts are the typical footprint of password guessing.")  # explanation
```

`suggest_techniques(alert)` lower-cases the title + description + hostname + indicators, counts how many keywords
match **as whole words** (so `iex` doesn't match "indexed") plus 1 if the alert category matches, and ranks the
techniques. Two or more signals → "Medium" confidence, otherwise "Low". Each result carries the `reason` string and
the `matched_terms`, and the fixed text *"Suggestion only … must be validated by an analyst"* – the UI
(`MitreList` in `components/ui.jsx`) and the PDF both show it. There is no machine learning; you can read every rule.

## 11. Audit logging

`services/audit.log_event(db, action, actor, ...)` is called from the routers right after a successful action. It only
**inserts**; the module has no update or delete function, and `routers/audit.py` exposes only `GET`. The tests
(`test_audit_records_cannot_be_modified_via_api`) confirm that POST/PUT/PATCH/DELETE on audit logs return 404/405 for
*every* role, including Admin. `_clean()` drops any `details` key that looks like a credential, so passwords and tokens
can't leak into logs.

## 12. PDF generation

`services/pdf.py` uses **ReportLab Platypus**: you build a list ("story") of `Paragraph`, `Table`, `Spacer` objects and
`doc.build(story)` lays them out across pages, with a footer on each page. User-provided text goes through
`xml.sax.saxutils.escape` so something like `<script>` is printed literally instead of being interpreted. The route
(`cases.case_report`) returns the bytes with `media_type="application/pdf"`. The React button calls
`api.download()`, which fetches with the auth header, turns the response into a `Blob` and clicks a temporary link –
a plain `<a href>` couldn't send the `Authorization` header.

## 13. Dashboard

`routers/dashboard.py` runs `$group` aggregations (counts by severity/status/case status), a per-user workload
aggregation, a zero-filled per-day trend, and the last audit entries. Nothing is hard-coded: create an alert and refresh,
the numbers move. `pages/Dashboard.jsx` draws bars with plain CSS and the trend with an inline SVG – no chart library.

## 14. Frontend structure

* `main.jsx` mounts `<App/>` inside the router and two **context providers**.
* `context/AuthContext.jsx` – holds `user`, `login()`, `logout()`; restores the session from the stored token on load.
* `components/ProtectedRoute.jsx` – redirects anonymous visitors to `/login`; `adminOnly` shows "Access denied".
* `components/Layout.jsx` – sidebar + top bar; `<Outlet/>` is where the current page renders.
* `components/ui.jsx` – reusable `Card`, `Modal`, `Badge`, `Pagination`, `Field`, `MitreList`, `Spinner`…
* `pages/*.jsx` – one screen each. All data comes from `api.*` calls; there are no fake buttons.

## 15. The public landing page

`frontend/src/pages/Landing.jsx` (+ `landing.css`, all scoped under `.landing`) is a normal React page with no login. It shows three useful patterns: `useReveal` (an `IntersectionObserver` that fades sections in as you scroll), `CountUp` (a `requestAnimationFrame` counter) and `LiveFeed` (a `setInterval` that pushes simulated alerts - note the interval is cleaned up in the effect's return). The **Try it** box calls `POST /api/public/mitre-suggest` (`backend/app/routers/public.py`), the only unauthenticated endpoint that does real work. Read how it stays safe: it never touches the database, caps input sizes with Pydantic and limits each IP to 20 requests per minute (`_rate_limit`).

## 16. Testing

`backend/tests/` uses **pytest** with FastAPI's `TestClient`. `conftest.py` creates a fresh in-memory MongoDB
(`mongomock`) per test and fixtures like `admin`, `analyst`, `make_alert` that log in and return auth headers. Read
`test_cases.py` first – it reads like a description of the workflow. `e2e/run.mjs` is a robot that clicks through the real UI.

---

## How to study this project

1. **Run it** (see README) and click through as `analyst1`, then as `admin`. Notice what changes.
2. Open `http://localhost:8001/docs`, click **Authorize**, log in and try endpoints by hand.
3. **Follow one request end to end**: in the browser create an alert → find `AlertForm.jsx` → `api.post("/alerts")` in
   `client.js` → `create_alert` in `routers/alerts.py` → `AlertCreate` in `schemas.py` → `suggest_techniques` →
   `insert_one` → `log_event`. Watch the document appear with `mongosh ai_soc_assistant` → `db.alerts.findOne()`.
4. **Break things on purpose**: try an expired token, a wrong role, a 5,000-character title, `.*` in the search box.
   Find which line produced each error.
5. **Read the tests as documentation**, then change a rule (e.g. make analysts unable to create alerts) and watch which
   tests fail.
6. **Small exercises**: add a new MITRE rule; add a `Low`-confidence filter; add a "source IP" column to the alerts table;
   add a new audit action; add an endpoint that exports alerts as CSV.
7. Use the README's "Known limitations" as a list of things to improve once you understand the basics.
