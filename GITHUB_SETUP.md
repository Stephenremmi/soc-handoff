# Private GitHub workflow

The private `soc-handoff` repository already exists, and the owner confirmed that the first **SOC Handoff CI** run passed. Atlas ticket creation was also confirmed locally. This guide covers ongoing review and the planned migration; it does not require repository creation, `git init`, a new remote, or another initial push.

## Inspect and review the existing checkout

From the repository root:

```bash
git status --short
git remote -v
git branch --show-current
git check-ignore -v .env .venv/ tracker.sqlite3
git diff -- AGENTS.md README.md docs/ARCHITECTURE.md GITHUB_SETUP.md
```

Keep `.env`, local virtual environments, SQLite files, Atlas credentials, and tokens out of Git. `.env.example` contains placeholders and belongs in the repo. Keep the repo and deployments private until the owner authorizes an audience change. Avoid posting credential-bearing command output in issues or PRs.

Leave Phase 1 implementation and the preserved documentation edits **uncommitted** for owner review. No frontend, session, evidence-binding, or reconciliation work is included. For subsequent authorized implementation, use a feature branch and a pull request against the existing private remote; review the actual diff and staged file list before committing. No deployment workflow currently exists.

## Current local and CI verification

Follow [README](README.md#current-local-startup) for environment setup and the existing Atlas walkthrough. Current supported startup commands, in separate activated terminals from `backend/`, are:

```text
python -m uvicorn tracker:app --host 127.0.0.1 --port 8001
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open [the demo](http://127.0.0.1:8000), sign in with the configured HTTP Basic credentials, execute before approval to demonstrate **Blocked** and no ticket, then approve/execute and verify the ticket ID. Reload the saved-run URL, roll back, and confirm closure of the same ticket with creation and closure audit events retained.

Current unit checks (start from the root with the virtual environment active):

```bash
python -m pip install -r backend/requirements.txt
cd backend
python -m unittest discover -s tests -p 'test_*.py'
```

For real-service verification use the [disposable MongoDB commands](README.md#current-verification), not the live Atlas environment. Unit discovery does not run the smoke test.

In GitHub, inspect **Actions > SOC Handoff CI** on the relevant branch/commit. `.github/workflows/ci.yml` runs on pushes, pull requests, and manual dispatch. Its current job:

1. Starts disposable MongoDB 7.0.32 on port 27017.
2. Uses Python 3.12 and runs `python -m pip install -r requirements.txt` from `backend/` (the file is `backend/requirements.txt` at root).
3. Runs tracker confirmation and configuration unit tests, seeds synthetic records, and runs `python tests/smoke_test.py` from `backend/`.
4. The smoke harness starts both HTTP services on 18000/18001 with generated password/token values, separate `soc_handoff_ci` and `soc_handoff_tracker_ci` databases, and dotenv disabled.

CI uses no Atlas secrets and performs no deployment or frontend build. The initial green run predates the target React/session features; confirm the status of the exact commit under review rather than treating that first pass as coverage of future changes.

## Phase 1 migration and planned frontend CI

Phase 1 is implemented: Python assets and tests are under `backend/`, both services explicitly load root `.env`, Python CI run steps default to `backend/`, and pip caching uses `backend/requirements.txt`. Follow the [migration map](docs/ARCHITECTURE.md#folder-migration-and-planned-frontend). The frontend and its CI build remain **Planned**.

| Area | Current behavior / planned follow-up |
| --- | --- |
| Root workflow | Keep `.github/workflows/ci.yml` in place; checkout remains at root |
| Python dependencies | Implemented: install from backend cwd; pip cache dependency path is root-relative `backend/requirements.txt` |
| Backend commands | Implemented: default Python run-step working directory is `backend/`; seed, unit discovery, and smoke retain relative command names |
| Smoke harness | Verify imports, computed ROOT, subprocess cwd, both Uvicorn targets, seed and legacy migration paths after moving tests |
| Frontend | **Planned:** select/pin Node version; cache from `frontend/package-lock.json`; run `npm ci` and `npm run build` with `working-directory: frontend` |
| Built-demo verification | **Planned:** build frontend before tests requiring `frontend/dist`; check SPA routing does not intercept API errors |
| Test data and secrets | Retain disposable MongoDB, synthetic data, and `PYTHON_DOTENV_DISABLED=1`; no Atlas credentials or tracker token in Vite/browser config |
| Completion | **Planned:** add browser checks for sessions, protected writes, recent runs and saved-run reload; retain both-service creation/retry/rollback checks |

The existing Atlas sandbox stays the local walkthrough environment. Separate least-privilege runtime credentials and an explicitly chosen deployment target are future deployment work, not CI requirements.

## Contributor handoff

Open the repository root in Codex and read [AGENTS.md](AGENTS.md). A useful implementation prompt is:

> Read AGENTS.md, README.md, and docs/ARCHITECTURE.md. Review the completed backend folder migration and verify both services against disposable MongoDB before adding frontend code. Evidence binding, reconciliation, sessions, and React remain Planned until separately implemented. Preserve Allowed-before-dispatch, actor-bound approval, one ticket per run, and the audit history. Report actual checks and unsupported assumptions.

Review pull requests against the six [target acceptance checks](docs/ARCHITECTURE.md#target-acceptance-checks). Distinguish verified current behavior from planned session/React behavior and coverage gaps. Keep architectural decisions in services, MongoDB access in persistence, and tracker HTTP in integrations.
