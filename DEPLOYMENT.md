# Deploying AI SOC Analyst Assistant (free tier)

This guide puts the app online using free services:

| Part | Service | Notes |
|---|---|---|
| Database | **MongoDB Atlas** (M0 free cluster) | hosted MongoDB |
| Backend API | **Render** web service (Python) | free plan sleeps when idle |
| Frontend | **Render** static site (or Vercel / Netlify) | free, HTTPS included |

> **Status of this guide:** the configuration files in this repo (`render.yaml`, `vercel.json`, `public/_redirects`)
> and the production-safety code (strict startup checks, invite code, admin bootstrap) are tested locally, but
> **an actual cloud deployment has not been performed from this repo**. Expect to adjust small details
> (service names, URLs) the first time.

The free backend **sleeps after ~15 minutes idle**; the first request afterwards can take 30-60 s. That is fine for a
portfolio, but say so on your demo page.

---

## 0. Before you start

* Push the repo to GitHub (done: `durvesh55/AI-SOC-Analyst-Assistant`).
* **Use simulated data only** in a public deployment.
* Decide an **invite code** for registration (any long random string). Without one, anyone with the link can create an
  Analyst account and read all alerts/cases.

## 1. MongoDB Atlas

1. Create a free account at https://www.mongodb.com/atlas and a **free M0 cluster**.
2. **Database Access** -> add a database user with a strong password (save it).
3. **Network Access** -> allow access. Render's free plan has no fixed IP, so you must allow `0.0.0.0/0`.
   That is acceptable **only because** the database user has a strong password and TLS is enforced; tighten it if you
   later move to a plan with static IPs.
4. **Connect -> Drivers** -> copy the connection string, e.g.
   `mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
   (URL-encode special characters in the password).

## 2. Deploy both parts on Render (Blueprint)

1. https://render.com -> **New -> Blueprint** -> connect the GitHub repo. Render reads `render.yaml` and proposes two
   services: `soc-assistant-api` and `soc-assistant-web`.
2. Fill the prompted variables:

   | Service | Variable | Value |
   |---|---|---|
   | api | `MONGO_URI` | the Atlas connection string |
   | api | `CORS_ORIGINS` | the web URL, e.g. `https://soc-assistant-web.onrender.com` (no trailing slash) |
   | api | `REGISTRATION_INVITE_CODE` | your invite code (or leave empty for open registration) |
   | web | `VITE_API_BASE` | `https://soc-assistant-api.onrender.com/api` |

   `JWT_SECRET` is generated automatically, and `ENVIRONMENT=production` is already set - in production the server
   **refuses to start** with a weak secret.
3. Deploy. If the final URLs differ from what you typed, update `CORS_ORIGINS` and `VITE_API_BASE`, then redeploy
   the **web** service (Vite bakes `VITE_API_BASE` in at build time).

Health check: `https://<api>/api/health` should return `{"status":"ok","database":"up"}`.
API docs: `https://<api>/docs`.

### Alternatives for the frontend
* **Vercel / Netlify:** import the repo, set root directory `frontend`, build command `npm run build`, output
  `dist`, env var `VITE_API_BASE`. `vercel.json` and `public/_redirects` already provide the single-page-app fallback
  so that refreshing `/alerts` works.

## 3. Create your first Admin (do NOT run the dev seed)

Run this once from your own computer, pointing at Atlas:

```powershell
cd backend
venv\Scripts\activate
$env:MONGO_URI = "mongodb+srv://USER:PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
$env:MONGO_DB  = "ai_soc_assistant"
$env:ADMIN_PASSWORD = "a-strong-password-1"     # or omit to be prompted
python -m app.create_admin --username yourname --email you@example.com --name "Your Name"
```

Then log in through the site. Create analysts from **User Management**, or share the invite code so people can register.
Optionally load demo data into a **separate** demo database (`MONGO_DB=ai_soc_demo`) with `python -m app.seed`.

## 4. Production checklist

- [ ] `ENVIRONMENT=production` and a generated/long `JWT_SECRET` (the app enforces this)
- [ ] `CORS_ORIGINS` is exactly your frontend origin (no `*`)
- [ ] `REGISTRATION_INVITE_CODE` set (or you accept open sign-up)
- [ ] No seeded dev accounts (`admin / Admin@12345`) exist in the production database
- [ ] Atlas user has a strong, unique password; password not committed anywhere
- [ ] Only simulated/non-sensitive data
- [ ] HTTPS everywhere (Render/Vercel/Netlify provide it)

## 5. Known limits of this setup

* Free-tier cold starts (see above).
* Login lockout and the public ATT&CK demo limiter are **in-memory per process**; they reset on restart and are not
  shared between multiple instances.
* JWTs live in browser `localStorage`; for a high-risk deployment move to httpOnly cookies (see README roadmap).
* No backups are configured (Atlas free tier has none); do not store anything you cannot recreate.
