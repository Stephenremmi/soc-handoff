# SOC Handoff architecture

## Current baseline and ownership

The Statement One demo starts from synthetic MFA alert SOC-1042. A named analyst approves a deterministic follow-up; SOC Handoff checks policy and records its decision before a separate tracker writes a ticket. The owner confirmed Atlas ticket creation and the first successful GitHub Actions run. The private repository and HTML demo already exist. **There is no React/Vite frontend in this checkout.**

Current layout (supporting files omitted):

```text
repo/
|-- backend/
|   |-- app.py, tracker.py       # Uvicorn compatibility entry points
|   |-- requirements.txt
|   |-- setup_demo.py           # seed or watch audit changes
|   |-- soc_handoff/
|   |   |-- main.py, config.py, schemas.py, demo.py
|   |   |-- errors.py, exception_handlers.py
|   |   |-- auth/, middleware/, routers/, services/
|   |   |-- database/, integrations/
|   |   `-- web/index.html      # existing HTML/JavaScript demo
|   |-- sandbox_tracker/
|   |   |-- main.py, config.py, schemas.py
|   |   `-- auth/, routers/, database/
|   |-- scripts/migrate_tracker_tickets.py
|   `-- tests/test_config.py, test_tracker_client.py, smoke_test.py
|-- .github/workflows/ci.yml
|-- .env.example               # .env remains local/ignored at root
`-- AGENTS.md, README.md, GITHUB_SETUP.md, docs/
```

Phase 1 backend migration is implemented. Package paths in the table below are relative to `backend/`; all frontend/session additions remain **Planned**.

| Boundary | Current responsibility | Target responsibility |
| --- | --- | --- |
| Each service's `main.py` | Assemble routers, resources, lifecycle | Preserve composition; SOC Handoff also wires sessions and built frontend serving |
| Each service's `config.py` | Explicit repo-root `.env`, process environment precedence, dotenv-disabled support; hide secrets in repr | Backend-only session/origin settings |
| `soc_handoff/auth/` | HTTP Basic credentials and current active Atlas identity; custom mutation header | Server-side session lifecycle, current identity lookup, CSRF/origin enforcement |
| `soc_handoff/middleware/`, `exception_handlers.py` | Request IDs and HTTP error translation | Preserve cross-cutting behavior |
| Each service's `routers/`, `schemas.py` | Validate contracts and translate HTTP | Thin routes; add auth and actor-scoped recent-run contracts |
| `soc_handoff/services/workflow.py` | Propose, approve, execute, stop, rollback, ticket lookup | Own transitions and audit ordering |
| `soc_handoff/services/policy.py` | Pure evaluation of supplied records | Keep independent of HTTP and MongoDB I/O |
| Each service's `database/` | Own client lifecycle, persistence; app also owns seed/validation | Preserve separate databases/credentials; app owns session storage and recent-run queries |
| `soc_handoff/integrations/tracker.py` | Authenticated HTTP and confirmation validation | Sole outbound ticket adapter |
| `sandbox_tracker/` | Bearer-authenticated ticket create/read/close | Remain small; no duplicated analyst policy/workflow layer |
| `soc_handoff/web/index.html` | Current controls, audit rendering, saved-run URL | Keep through backend migration; replace serving only after React parity |
| **Planned** `frontend/src/` | Does not exist | Sign-in form, evidence, recent runs, action controls, audit timeline; one API client |

SOC Handoff owns `audit_identities`, `audit_policies`, `findings`, and `audit_runs` in its database. The tracker owns `tickets` in its own database. Each process owns a synchronous PyMongo client; SOC Handoff also owns a synchronous HTTPX client. Blocking I/O routes are synchronous. Both clients are opened/closed with service lifespan, and MongoDB is pinged at startup. Health endpoints are liveness checks, not ongoing dependency readiness checks.

## Current approval-to-ticket flow

1. HTTP Basic checks the configured username/password. Each protected request resolves that analyst from Atlas and rejects an inactive identity. A run lookup filters by both run ID and actor. Mutating run routes also require `X-SOC-Action: interactive`; no broad CORS configuration is present.
2. `POST /api/runs` reads the seeded finding and saves its evidence snapshot in a new `proposed` run with a **Proposed** event.
3. `POST /api/runs/{id}/approve` reads current policy and finding. Pure policy checks the analyst role, action/destination, enabled policy, and finding verification markers. A passing approval stores actor, timestamp, and policy version inside that specific run, with **Approved**. A denial appends **Approval blocked**.
4. `POST /api/runs/{id}/execute` reads the actor-owned run, current policy, and linked finding. It checks explicit approval by this analyst and the current policy version in addition to the checks above. A denial appends **Blocked** without calling the tracker. An already `created` run returns its saved result without another dispatch.
5. A revision-checked MongoDB write sets `creating` and appends **Allowed** atomically. Only after that write returns does the integration call `POST /tickets` with the run ID and the server's tracker bearer token.
6. The tracker upserts by run ID (`tickets._id`) using `$setOnInsert`; new ticket IDs are `TKT-<run UUID hex>`. Repeated creates retain the same ticket and do not reopen a closed ticket. SOC Handoff validates ticket shape, run ID, and open status, then stores `created`, `ticket_id`, and **Ticket created**.
7. Missing/malformed/mismatched confirmations or HTTP failures yield **Result unconfirmed**, leaving `creating`. Retry uses the same run ID and repeats policy checks. Never infer success solely from a browser response or an HTTP 200 without a valid ticket confirmation.
8. `POST /api/runs/{id}/rollback` checks current rollback permission, persists `closing` and **Rollback authorized**, then closes `/tickets/by-run/{id}/close`. A confirmation must identify the same run, same ticket, and closed status. The run becomes `closed` with **Ticket closed**; uncertainty records **Rollback unconfirmed** and leaves `closing` for retry.

```mermaid
sequenceDiagram
    participant Browser
    participant App as SOC Handoff
    participant AppDB as App MongoDB
    participant Tracker
    participant TicketDB as Tracker MongoDB
    Browser->>App: Approve a specific run (authenticated write)
    App->>AppDB: Read actor-owned run, policy, verified finding
    App->>AppDB: Save approval identity/version and Approved
    Browser->>App: Execute run (authenticated write)
    App->>AppDB: Recheck identity, approval, current policy/finding
    alt Denied or missing approval
        App->>AppDB: Append Blocked
        App-->>Browser: Run and reason; zero ticket writes
    else Allowed
        App->>AppDB: Persist Allowed + creating
        App->>Tracker: POST /tickets, run ID, bearer token
        Tracker->>TicketDB: Idempotent upsert by run ID
        Tracker-->>App: Ticket confirmation
        App->>AppDB: Save Ticket created, or Result unconfirmed
        App-->>Browser: Authoritative run and audit
    end
```

| State | Next actions |
| --- | --- |
| `proposed` | Approve or stop; early execute records denial |
| `approved` | Execute or stop |
| `creating` | Retry creation with same run ID and current policy checks; inspect tracker |
| `created` | Return saved creation result; rollback |
| `closing` | Retry closure |
| `closed`, `canceled` | Terminal; retain audit |

`MongoStore.record` changes state and appends an event in one optimistic revision-checked write; conflicting updates return a conflict. There is no distributed transaction across the databases or HTTP boundary. If tracker storage succeeds but the app's confirmation write fails, the app may remain `creating` without the final event. A successful tracker operation is not necessarily a confirmed audit result. `GET /api/runs/{id}/ticket` can inspect the external outcome but does not reconcile run state.

## Planned browser authentication and integration

This section is a design, not existing endpoints or configuration. For the single-analyst MVP, retain the configured `SOC_DEMO_USER` / `SOC_DEMO_PASSWORD` credential check and active Atlas identity, replacing browser HTTP Basic with an opaque server-side session. This avoids adding an identity provider for the local demo while supporting explicit expiry and sign-out.

- **Planned contracts:** `POST /api/auth/sign-in`, `GET /api/auth/session`, and `POST /api/auth/sign-out`. Sign-in validates credentials and active identity, rotates any prior session, and returns identity/expiry plus a CSRF token; never return the password or tracker token.
- Store a hash of a high-entropy random session ID in an app-owned MongoDB session collection with actor, creation time, absolute expiry, and CSRF binding. Use a 30-minute absolute lifetime with no silent extension. Enforce expiry on every request; a TTL index is cleanup, not authorization. Recheck the active analyst on protected requests.
- Set a host-only HttpOnly, `SameSite=Lax`, `Path=/` session cookie. Use `Secure` under HTTPS; loopback HTTP development explicitly disables Secure. Browser JavaScript never stores the session ID or credentials in local/session storage. Use one hostname consistently (`127.0.0.1`) for the local flow.
- Require exact allowed `Origin` on browser writes, including sign-in (prevent login CSRF); reject missing/untrusted browser origins. For authenticated writes, including sign-out, also require a session-bound CSRF token in a custom header and retain `X-SOC-Action: interactive` through the transition. Return the CSRF token via the session endpoint after reload and hold it in memory. SameSite and the existing fixed header alone are not the full planned protection. Define a separate explicit contract if non-browser clients are later required.
- Expired/revoked sessions return 401. Clear local identity/CSRF state, show sign-in, retain only the run ID in the URL, then fetch the run again after sign-in. Sign-out revokes the server record and expires the cookie with matching attributes. Do not replay an interrupted write automatically. A 403 may mean inactive identity, ownership, or CSRF failure; show the reason and refresh authoritative state where appropriate.

**Planned development:** React/Vite/TypeScript lives under `frontend/`. Its single `src/api/client.ts` uses relative `/api` URLs, sends cookies (`credentials: same-origin`), attaches write headers, and handles error responses consistently. Vite proxies `/api` unchanged to `http://127.0.0.1:8000` so the browser sees one origin (normally `http://127.0.0.1:5173`). Allow that exact development Origin and the built demo Origin `http://127.0.0.1:8000`; ensure proxy configuration preserves the browser Origin and forwards Set-Cookie. No browser-to-tracker proxy and no broad credentialed CORS are needed. DB URIs and `TRACKER_TOKEN` never enter `VITE_*`, frontend bundles, or browser storage.

**Planned built demo:** `npm run build` produces `frontend/dist`; SOC Handoff serves assets and the SPA entry from that resolved repository-relative path. Keep `/api`, `/docs`, and `/openapi.json` ahead of SPA handling. Unknown `/api` paths and missing assets must remain errors, not HTML fallback responses. Serve the sign-in shell without analyst authentication; protect data APIs. Use no-store for identity/session/run responses and the shell; hashed assets may be cached. After backend-only migration, preserve the existing Basic-protected HTML page until the session/React cutover is ready.

**Planned run recovery:** preserve `?run=<id>` for saved links, fetch `GET /api/runs/{id}` after session restoration, and render the returned ticket ID and audit. Add an actor-filtered, bounded/paginated `GET /api/runs` query for recent runs in the route/service/persistence boundaries. Obtain evidence and verification metadata through a deliberate backend contract; the current response has a snapshot string but no verification metadata, and the current page's evidence card is hard-coded. React must not invent verified status or infer run success from button state.

## Folder migration and planned frontend

Target tree: `backend/` is implemented; every `frontend/` entry and the session/recent-run additions remain **Planned**:

```text
repo/
|-- AGENTS.md, README.md, GITHUB_SETUP.md
|-- docs/ARCHITECTURE.md
|-- .env                       # local only, ignored
|-- .env.example, .gitignore
|-- .github/workflows/ci.yml    # remains at root
|-- backend/
|   |-- app.py, tracker.py      # keep compatibility module names here
|   |-- requirements.txt
|   |-- setup_demo.py
|   |-- soc_handoff/
|   |   |-- main.py, config.py, schemas.py, demo.py
|   |   |-- errors.py, exception_handlers.py
|   |   |-- auth/              # analyst/session/CSRF responsibilities
|   |   |-- middleware/, routers/, services/
|   |   |-- database/, integrations/
|   |   `-- web/index.html     # retained during migration/parity gate
|   |-- sandbox_tracker/
|   |   |-- main.py, config.py, schemas.py
|   |   `-- auth/, routers/, database/
|   |-- scripts/migrate_tracker_tickets.py
|   `-- tests/test_tracker_client.py, smoke_test.py
`-- frontend/
    |-- package.json, package-lock.json
    |-- index.html, vite.config.ts, tsconfig*.json
    |-- src/
    |   |-- main.tsx, App.tsx
    |   |-- api/client.ts      # single HTTP entry point
    |   `-- components/        # sign-in, evidence, recent runs, controls, audit
    `-- dist/                  # generated, ignored
```

| Phase 1 move or retention | Implemented behavior / verification expectation |
| --- | --- |
| Moved `soc_handoff/`, `sandbox_tracker/` intact to `backend/` | Preserve package-relative imports and package names; do not introduce a `backend.soc_handoff` namespace or cross-service persistence imports |
| Moved `app.py`, `tracker.py` to `backend/` | Run Uvicorn from `backend/`: `app:app` and `tracker:app` still resolve; direct package entry points are `soc_handoff.main:app` and `sandbox_tracker.main:app` there |
| Moved `requirements.txt` to `backend/` | Install from root with `python -m pip install -r backend/requirements.txt`; CI pip cache dependency path is updated |
| Moved `setup_demo.py`, `scripts/` to `backend/` | From `backend/`: `python setup_demo.py`, `python setup_demo.py watch`, `python -m scripts.migrate_tracker_tickets <absolute-sqlite-path>`; preserve seed idempotency and imported IDs |
| Moved `tests/` to `backend/tests/` | From `backend/`: unit discovery `-s tests` and `python tests/smoke_test.py`; review harness `ROOT`, subprocess cwd, seed/module paths, and imports. Its unchanged `parents[1]` now resolves to backend, matching seed/script and subprocess paths |
| Retained `.env`, `.env.example` at root | Both settings modules load `Path(__file__).resolve().parents[2] / ".env"` explicitly with `override=False`; process environment variables retain precedence and `PYTHON_DOTENV_DISABLED=1` skips loading. `.env` stays ignored |
| Retained `.venv/` at root, local only | Activate before changing into backend; do not move the virtual environment |
| Keep docs and `.github/workflows/ci.yml` at root | Documentation uses backend cwd; CI defaults run steps to `working-directory: backend` and pip cache uses root-relative `backend/requirements.txt` |
| Keep old web page inside its package during move | Verify its file-relative resolution still works before any React changes |
| Add `frontend/` only after backend checks pass | Add Node lockfile, select/pin Node version, ignore node_modules/dist, build from frontend working directory; adjust built-asset path separately |

Phase 1 moves are implemented; package names, relative imports, API routes, ports, database defaults, and approval/rollback workflow remain unchanged. CI retains checkout at repository root, caches from `backend/requirements.txt`, and runs Python steps in `backend/`. **Planned:** use `frontend/package-lock.json` for Node caching and run `npm ci` / `npm run build` in `frontend/`. Build the frontend before smoke checks that require built UI serving. Keep MongoDB disposable, dotenv disabled, and synthetic seeds; never configure Atlas credentials in CI.

### Phase 1 verification

- Before moving files, the existing 2 unit tests passed. After migration, all 5 unit tests passed, including configuration coverage using synthetic dotenv files only.
- The existing real-service smoke test passed from `backend/` against a fresh temporary local MongoDB database. It started `tracker:app` and `app:app` on test ports 18001/18000, served the existing HTML demo, and checked blocking, create/retry, rollback, audit events, concurrent tracker creates, repeat seeding, and legacy import. No workflow code or smoke assertions changed.
- Local verification used Python 3.14.2 and installed MongoDB 7.0.4. CI remains configured for Python 3.12 and MongoDB 7.0.32; hosted CI has not been rerun for these uncommitted changes. The temporary MongoDB process and database were removed afterward.
- The existing Atlas demo and change-stream `watch` mode were not exercised. Root `.env` was neither modified nor logged. Evidence binding, reconciliation, browser sessions, and React/Vite remain **Planned**.

## Target acceptance checks

| Done means | Acceptance evidence and present coverage |
| --- | --- |
| 1. Execution before approval is blocked and creates zero tickets | Smoke test asserts **Blocked**, tracker 404, and no matching tracker document. Preserve this under session auth |
| 2. Backend checks analyst, approval, current policy, verified evidence; persists **Allowed** before dispatch | Ordering and checks exist in workflow; smoke checks event order and approving actor. Add tests proving no outbound call before the durable Allowed write, changed policy/inactive actor denial, and evidence-version consistency |
| 3. Approved run creates one ticket; retry reuses ID; uncertain response stays unconfirmed | Smoke covers normal create/retry and concurrent tracker creates. Unit tests reject invalid confirmations. Add workflow-level timeout/lost-response/failed audit-write reconciliation checks with one external ticket and correct unconfirmed state |
| 4. Rollback closes the same ticket and retains creation/closure history | Smoke checks closed tracker state, stored ticket ID, and ordered audit events. Adapter tests reject wrong ticket/status. Extend to uncertain/retried closure |
| 5. React signs in, reopens a saved run after reload, and shows matching ticket ID/history | Not implemented. Existing HTML supports saved-run fetch; current smoke does not exercise browser reload. Add browser checks for sign-in, expiry, sign-out/revocation, CSRF rejection, recent runs, and reload recovery |
| 6. CI builds frontend and exercises both services on disposable MongoDB with synthetic data; Atlas supports local walkthrough | Current CI exercises both services only. Add frontend build and relevant browser checks after scaffolding, keeping Atlas local and out of CI |

Current unit discovery covers tracker confirmation and configuration resolution/precedence/isolation tests. The smoke test also covers login challenge, mutation header, tracker token, request IDs, schema validation, repeat seed, and legacy import. It does not establish full session, policy-change, evidence-change, outage, or browser behavior. An initial CI pass is a baseline, not evidence for unimplemented target requirements.

## Architectural risks and unsupported assumptions

- **Evidence/approval drift:** the workflow checks that the current finding has `verified_at` and `verified_by`, but sends the run's earlier evidence snapshot without a version/hash comparison. Verification markers are not independently validated identities. Define a stable finding version or content binding and require fresh approval when the approved evidence changes.
- **Authorization timing:** current identity/policy/finding reads are separate from the run write and tracker call. Changes during dispatch are not atomically excluded. Define the authorization snapshot and acceptable race window; do not claim an atomic cross-service policy guarantee.
- **Reconciliation:** there is no distributed transaction. A policy change can block retry of `creating` even if a ticket already exists. Stop cannot cancel a dispatched action; rollback requires a confirmed ticket ID. Define recovery for a confirmed external ticket whose app confirmation could not be persisted, without bypassing policy or making a duplicate.
- **Audit durability:** revision checks prevent lost concurrent run updates, but audit is embedded and application-appended, not tamper-proof storage. Database permissions remain part of trust, and unbounded retry history can grow toward MongoDB document limits. A returned `created` result on repeat execution adds no new retry event; do not promise every read/repeat click is separately audited.
- **Browser boundary:** Basic auth has browser credential caching and no explicit expiry/logout. Session contracts, revocation storage, CSRF/origin validation, recent-run API, verification metadata, and React behavior are all proposed work. Moving to a public sign-in shell must not expose protected data or secrets.
- **Migration/build paths:** changed cwd/import roots, smoke subprocess paths, and future SPA fallbacks can break a working MVP. Phase 1 removes implicit dotenv search and adds configuration coverage. Verify backend migration independently; do not let UI fallback hide API failures. Separate credentials are a deployment permission requirement; disposable CI databases do not prove Atlas user isolation.

## Implementation order

1. **Phase 1 implemented:** Python assets are moved as mapped, dotenv resolves root explicitly, package imports/entry points and smoke paths remain valid from backend cwd, and CI working directories/cache paths are updated. Verify unit and real-service smoke checks, old HTML page, seed/watch, and legacy import before adding frontend code. Use disposable MongoDB for automation; verify Atlas walkthrough separately.
2. **Planned:** address evidence binding and uncertain-result recovery, with focused workflow checks for policy/identity/evidence changes, durable Allowed ordering, and failed confirmations. Keep tracker changes minimal.
3. **Planned:** implement browser sessions, expiry/revocation, CSRF/origin checks, actor-scoped recent runs, and evidence metadata contracts. Test backend behavior before relying on React controls.
4. **Planned:** scaffold React/Vite/TypeScript with one API client and `/api` proxy; implement sign-in, evidence, recent runs, saved-run recovery, controls, and audit timeline.
5. **Planned:** wire built frontend serving and API-safe SPA routing. Extend CI with frontend build and relevant browser checks alongside disposable-MongoDB service tests. Prove all six acceptance checks, then repeat the synthetic local Atlas walkthrough. Keep the repository and any deployment private.
