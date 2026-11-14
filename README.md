# SOC Handoff - Agents You Can Audit

One synthetic SOC alert, one analyst-approved action, and one ticket in a separate sandbox tracker. SOC Handoff owns analyst identity, policy, findings, run state, and audit events in MongoDB Atlas. The tracker owns tickets in its own Atlas database and accepts authenticated HTTP requests from SOC Handoff.

The checkout is a working FastAPI MVP with an existing HTML/JavaScript demo. **React/Vite has not been built in this repo.** The owner confirmed Atlas ticket creation and the first successful GitHub Actions run; the private GitHub repository already exists. These baseline confirmations do not establish every target acceptance check.

See [architecture and target plan](docs/ARCHITECTURE.md), [contributor guidance](AGENTS.md), and [private GitHub workflow](GITHUB_SETUP.md).

## Current local startup

Use Python 3.10 or later (CI uses 3.12). From the repository root, in Windows Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r backend/requirements.txt
```

PowerShell activation is `.\.venv\Scripts\Activate.ps1`. Copy `.env.example` to `.env` only for a fresh setup; preserve an existing local `.env`. Configure:

| Setting | Local value / purpose |
| --- | --- |
| `MONGODB_URI` | Atlas URI for the SOC Handoff database user |
| `MONGODB_DATABASE` | Defaults to `soc_handoff` |
| `SOC_DEMO_USER` | Defaults to `demo-analyst` |
| `SOC_DEMO_PASSWORD` | Local analyst login password |
| `TRACKER_URL` | Defaults to `http://127.0.0.1:8001` |
| `TRACKER_TOKEN` | Random service bearer token shared by both local processes |
| `TRACKER_MONGODB_URI` | Atlas URI for a separate user restricted to the tracker database |
| `TRACKER_MONGODB_DATABASE` | Defaults to `soc_handoff_tracker` |

Generate password/token values separately with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Grant the tracker user `readWrite` only on its database (or equivalent scoped privileges). The Atlas cluster may host both databases; each service uses its own credentials and connection.

Both settings modules explicitly resolve the repo-root `.env` from their own file paths, regardless of the working directory. Existing process environment variables take precedence; `PYTHON_DOTENV_DISABLED=1` skips the file entirely. The seed/watch and migration scripts use these same settings. Keep `.env` at the root and ignored; never print its values. Run backend commands from `backend/`:

```bash
cd backend
python setup_demo.py
```

Setup seeds the synthetic finding, identity, and policy and installs validation for `audit_identities`, `audit_policies`, and `audit_runs`. It preserves existing seed values. Initial setup requires collection creation/insertion privileges; updating validators on existing collections also requires `collMod`. The tracker creates `tickets` on its first write.

Activate the root virtual environment in two terminals, run `cd backend` in each, and start both services:

```text
python -m uvicorn tracker:app --host 127.0.0.1 --port 8001
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open [the demo](http://127.0.0.1:8000) and answer the browser's HTTP Basic prompt. Current auth has no application-managed session expiry or reliable sign-out. Both services bind to loopback. [App health](http://127.0.0.1:8000/api/health) and [tracker health](http://127.0.0.1:8001/api/health) return `{"status":"ok"}`; these are liveness checks, with MongoDB pinged at startup. [FastAPI docs](http://127.0.0.1:8000/docs) expose the current API.

## Walkthrough against the existing Atlas demo

1. Choose **Propose follow-up**, then **Run policy check & execute** before approval. The audit records **Blocked**. **Check tracker** reports no ticket for that run.
2. Choose **Approve this action**, then execute. Show the approving identity, policy version, **Allowed**, confirmed ticket ID, and open tracker status. Retry execution to reuse the ticket ID.
3. Reload the URL containing `?run=<id>` to reopen the saved run and audit. This already works in the HTML demo; there is no recent-runs list yet.
4. Choose **Roll back ticket**, then check the tracker to confirm the same ticket is closed. Creation and closure events remain in the run. A fresh run can instead be stopped before dispatch.

Optional: `python setup_demo.py watch` in a third terminal prints Atlas change stream notifications. Audit events are embedded in each run document. Keep this local walkthrough on the existing Atlas sandbox, using synthetic data.

If importing tickets from the older SQLite tracker, stop the old services and run:

```bash
python -m scripts.migrate_tracker_tickets "/path/to/old/project/tracker.sqlite3"
```

This reads the file without changing it and preserves ticket IDs, run IDs, and statuses. Repeating the import keeps matching existing records and rejects identity conflicts. Fresh demos need no import.

## Current verification

Run from `backend/` with the root virtual environment active:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

These unit tests cover tracker confirmation validation and root dotenv resolution, environment precedence, and dotenv-disabled isolation. The separate real-service smoke test needs a **disposable** MongoDB on port 27017. With that instance available, mirror CI from `backend/` (Git Bash):

```bash
export MONGODB_URI='mongodb://127.0.0.1:27017/?directConnection=true'
export MONGODB_DATABASE=soc_handoff_ci
export SOC_DEMO_USER=ci-analyst
export PYTHON_DOTENV_DISABLED=1
python setup_demo.py
python tests/smoke_test.py
```

Use a separate terminal/environment from the Atlas walkthrough. The smoke harness generates password/token values, uses `soc_handoff_tracker_ci`, and starts both services on ports 18000/18001. CI runs these steps against MongoDB 7.0.32 with synthetic data and no Atlas secrets. It currently has no frontend build or deployment step. See the architecture for coverage gaps.

## Planned structure and local integration

Phase 1 has moved Python assets under `backend/`, keeping `soc_handoff` and `sandbox_tracker` distinct. Root `.env`, `.env.example`, `.gitignore`, `.github/`, and project documentation stay in place. The [migration map and target tree](docs/ARCHITECTURE.md#folder-migration-and-planned-frontend) account for imports, test paths, commands, and CI. Evidence binding, reconciliation, browser sessions, and React/Vite remain **Planned**. Verify both services before creating frontend code.

**Planned frontend commands**, from a separate root terminal after scaffolding:

```bash
cd frontend
npm ci
npm run dev
# Build the demo bundle
npm run build
```

**Planned:** Vite proxies `/api` unchanged to `http://127.0.0.1:8000`; the browser uses one relative-URL API client and never contacts the tracker directly. FastAPI serves `frontend/dist` for the built demo, including SPA routes while preserving API routes and JSON errors. React owns the sign-in form, evidence, recent runs, controls, and audit display. FastAPI remains authoritative.

**Planned sign-in:** exchange the single analyst's configured username/password for an opaque server-side session with a 30-minute absolute expiry. Use an HttpOnly, SameSite=Lax cookie (Secure under HTTPS), CSRF token plus origin checks for writes, and explicit server-side sign-out/revocation. Expiry returns 401; sign-in resumes the saved run by fetching it again. Credentials, tracker token, and MongoDB URIs stay server-side. See [the session design](docs/ARCHITECTURE.md#planned-browser-authentication-and-integration) for proxy and cookie details.

Completion requires the six [target acceptance checks](docs/ARCHITECTURE.md#target-acceptance-checks), including React reload recovery and a frontend build plus both-service CI. Frontend commands and session endpoints remain unimplemented; Phase 1 changes only backend layout, configuration resolution, CI paths, and related verification/documentation.
