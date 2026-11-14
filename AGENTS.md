# SOC Handoff

## Goal

Deliver the Agents in Context Toronto Statement One demo. An analyst approves one synthetic SOC follow-up, SOC Handoff checks Atlas policy and records its decision, and a separate FastAPI tracker creates or closes the ticket. A reviewer can reconstruct the run and the approving identity from the audit.

Read [README.md](README.md) for local setup, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for service and state boundaries, and [GITHUB_SETUP.md](GITHUB_SETUP.md) for the private repository workflow.

## Where to work

| Concern | Entry point |
| --- | --- |
| App composition and startup | `soc_handoff/main.py`, `sandbox_tracker/main.py` |
| Environment variables | Each service's `config.py` and root `.env.example` |
| Analyst and service authentication | `soc_handoff/auth/`, `sandbox_tracker/auth/` |
| Cross-cutting HTTP behavior | `soc_handoff/middleware/`, `soc_handoff/exception_handlers.py` |
| Endpoints and public contracts | Each service's `routers/` and `schemas.py` |
| Workflow transitions and policy | `soc_handoff/services/` |
| MongoDB queries, validation, and seeding | Each service's `database/` and root `setup_demo.py` |
| Outbound tracker HTTP | `soc_handoff/integrations/tracker.py` |
| Demo UI | `soc_handoff/web/index.html` |

## Invariants

- Match approval to the run, analyst, and policy version. Recheck current policy and verified evidence before dispatch.
- Persist **Allowed** before the tracker call. Record a successful operation after the tracker confirms it. A denied attempt creates zero tickets.
- Keep one ticket per run. Preserve the audit entries for retries and failures. Rollback closes the same ticket.
- The application and tracker own separate MongoDB databases and credentials. Keep tracker writes behind the tracker HTTP boundary.
- Route handlers translate HTTP. Put decisions in the workflow or policy. Keep policy functions independent of HTTP and MongoDB I/O.
- Use synthetic data, keep local secrets out of Git, and keep the repo and deployments private until the owner authorizes an audience change.

## How to verify a change

1. State the behavior you are changing and its acceptance check. Start from the owning module above.
2. Install dependencies with `python -m pip install -r requirements.txt`.
3. Run `python -m unittest discover -s tests -p 'test_*.py'`.
4. For changes to routes, auth, MongoDB or execution, run the real-service smoke test as configured in `.github/workflows/ci.yml`. It uses a disposable MongoDB instance. Keep CI away from the live Atlas sandbox.
5. Report what passed and any unverified environment. The supported local entry points are `app:app` on port 8000 and `tracker:app` on port 8001.
