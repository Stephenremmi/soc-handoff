# SOC Handoff

## Goal and baseline

Deliver the Agents in Context Toronto Statement One demo: a named analyst approves one synthetic SOC follow-up, SOC Handoff records its policy decision, and a separate FastAPI tracker creates or closes the ticket. A reviewer must reconstruct the run and approving identity from the audit.

The working MVP has two Python services and `backend/soc_handoff/web/index.html`. React/Vite has **not** been built here. The owner confirmed Atlas ticket creation and the first successful GitHub Actions run. The private repository already exists. Read [README.md](README.md) for current commands, [architecture](docs/ARCHITECTURE.md) for behavior and the target plan, and [GitHub workflow](GITHUB_SETUP.md) for review and CI.

## Ownership

Phase 1 is implemented: Python assets live under `backend/`, preserving both packages and their boundaries. Paths in the ownership table are relative to `backend/` unless explicitly marked root. **Planned:** add `frontend/` for React/Vite/TypeScript after backend verification.

| Concern | Owner / entry point |
| --- | --- |
| Composition and lifecycle | `soc_handoff/main.py`, `sandbox_tracker/main.py` |
| Configuration | Each service's `config.py`; root `.env.example` |
| Analyst authentication / tracker bearer authentication | `soc_handoff/auth/`, `sandbox_tracker/auth/` |
| Cross-cutting HTTP behavior | `soc_handoff/middleware/`, `soc_handoff/exception_handlers.py` |
| HTTP contracts and translation | Each service's `routers/` and `schemas.py` |
| Workflow transitions and pure policy evaluation | `soc_handoff/services/workflow.py`, `soc_handoff/services/policy.py` |
| MongoDB clients, queries, validation, seed | Each service's `database/`; `setup_demo.py` |
| Outbound tracker HTTP | `soc_handoff/integrations/tracker.py` |
| Current browser demo | `soc_handoff/web/index.html` |
| Planned browser application | Repo-root `frontend/src/`: sign-in, evidence, recent runs, controls, audit timeline; one API client |

Keep handlers thin, policy independent of HTTP/MongoDB I/O, and each new module responsible for one concrete task. Keep the tracker small: authenticated ticket persistence needs no duplicate workflow or policy layer. FastAPI owns authentication, policy decisions, and run state; browser control visibility never authorizes an action.

## Invariants and target requirements

- Match approval to the run, analyst, and policy version. Recheck current active identity, policy, and verified evidence before dispatch. The current verification check does not bind the run's evidence snapshot to a finding version; address this gap before claiming evidence consistency.
- Persist **Allowed** and `creating` before tracker HTTP. Record success only after a matching confirmation. Execution before approval records **Blocked** and creates zero tickets.
- Keep one ticket per run. Retry with the same run ID; retain failure/retry audit events. An uncertain response remains unconfirmed. Rollback closes that same ticket and preserves creation and closure events.
- Each service owns its MongoDB connection, database, and credentials. SOC Handoff writes tickets only through tracker HTTP. DB credentials and the tracker token stay server-side, outside Vite configuration and browser storage.
- **Planned:** use a revocable, expiring server-side browser session, HttpOnly cookie, CSRF protection, and sign-out as described in the architecture. Current HTTP Basic does not provide these session semantics.
- Use synthetic data. Keep secrets out of Git and repositories and deployments private until the owner authorizes an audience change. CI uses disposable MongoDB, never the Atlas walkthrough database.

## Verification expectations

1. State the changed behavior and acceptance check; start at the owning module. For documentation-only work, review paths, commands, and claims without changing dependencies, tests, or CI.
2. For implementation work, install from root with `python -m pip install -r backend/requirements.txt`; then `cd backend` and run `python -m unittest discover -s tests -p 'test_*.py'`.
3. For routes, auth, persistence, execution, or folder migration, run the real-service smoke test using the disposable MongoDB configuration in `.github/workflows/ci.yml` (commands in README). Unit discovery alone does not run `tests/smoke_test.py`.
4. **Backend migration gate:** verify imports, both Uvicorn entry points, explicit root `.env` loading, seed/watch and legacy migration commands, tests, static page resolution, and CI working directories after any Python layout change and before adding frontend code.
5. **Planned completion gate:** prove all six acceptance checks in the architecture, including React reload recovery, session expiry/sign-out/write protection, failure reconciliation, and frontend build plus both-service CI. Add meaningful coverage for policy/evidence changes and uncertain responses; existing tests do not establish every target requirement.
6. Report checks actually run and unverified environments. From `backend/`, current local entry points remain `app:app` on 8000 and `tracker:app` on 8001. Label future commands **Planned** until implemented.
