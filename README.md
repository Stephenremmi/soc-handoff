# SOC Handoff — Agents You Can Audit

One synthetic SOC alert. One proposed action. One real ticket in a separate sandbox tracker. MongoDB Atlas stores the analyst identity, policy, finding, run state, and audit events. An analyst must approve each specific run, and the app records the policy decision in Atlas before calling the tracker.

See [Architecture](docs/ARCHITECTURE.md) for module boundaries, [AGENTS.md](AGENTS.md) for Codex guidance, and [GitHub setup](GITHUB_SETUP.md) for the first private push.

## Run locally against the event's Atlas Sandbox

Use Python 3.10 or later. The CI workflow uses Python 3.12. On Windows in Git Bash, open this folder and run:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` for a fresh setup. If upgrading from the flat MVP, bring over your existing `.env`. Set these values locally:

- `MONGODB_URI` — The connection string you already used to ping the hackathon Atlas cluster.
- `MONGODB_DATABASE` — Defaults to `soc_handoff`.
- `SOC_DEMO_PASSWORD` — A new password for the local demo browser login. The username defaults to `demo-analyst`.
- `TRACKER_TOKEN` — A separate random value shared by the two local processes for HTTP authentication.
- `TRACKER_MONGODB_URI` — An Atlas Drivers URI for a separate tracker database user, for example `soc_handoff_tracker_app`. In Atlas, grant this user access to `soc_handoff_tracker` only. In **Specific Privileges**, choose `readWrite` for that database if available, or use a custom role with find, insert, update and create collection privileges scoped to it. Use this URI only for the tracker.
- `TRACKER_MONGODB_DATABASE` — Defaults to `soc_handoff_tracker`. The tracker creates the `tickets` collection on the first ticket write.

To generate values, run `python -c "import secrets; print(secrets.token_urlsafe(32))"` twice. Use the directory containing `.env` as the working directory for both processes.

For a fresh Atlas database, run `python setup_demo.py` once. It seeds the synthetic finding in `findings` under its own ID and initializes the `audit_identities`, `audit_policies`, and `audit_runs` collections with Atlas schema validation. The Atlas user needs rights to create those collections and insert demo documents. Running setup on existing demo collections also needs the `collMod` privilege. The seed leaves existing findings and demo policy values intact.

Run these in separate terminals from the same project folder. Activate the virtual environment in both terminals.

```text
python -m uvicorn tracker:app --host 127.0.0.1 --port 8001
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open [the local demo](http://127.0.0.1:8000) and use the demo username and password. Both processes bind to loopback. The tracker is a small, separately authenticated HTTP service with its own MongoDB database and credentials. The Atlas cluster can host both databases. The same run ID always produces the same tracker ticket, including after an interrupted attempt.

The browser presents the local HTTP Basic login prompt. [App liveness](http://127.0.0.1:8000/api/health) and [tracker liveness](http://127.0.0.1:8001/api/health) each return `{"status":"ok"}` after startup. Use [FastAPI docs](http://127.0.0.1:8000/docs) to inspect the API.

## 60-second walkthrough

1. Select **Propose follow-up**, then **Run policy check & execute** before approving. The app writes **Blocked** to Atlas. **Check tracker** confirms the tracker has no ticket for the run.
2. Select **Approve this action**, then **Run policy check & execute**. Show the Atlas policy version, the approving identity, the **Allowed** event, and the resulting ticket ID. **Check tracker** confirms its open status.
3. Select **Roll back ticket**, then **Check tracker** again. The tracker confirms its closed status, and Atlas retains the ticket creation and close events. To demonstrate stopping, start a fresh run and select **Stop run** before dispatch.

Run `python setup_demo.py watch` in a third terminal to see Atlas change stream notifications as demo events are recorded. Atlas stores the full event history within each run document. The local settings and credentials are excluded from Git.

This is a local, single-analyst demo using a deterministic proposal from synthetic evidence. The existing private Sites deployment is a separate prototype.

## Upgrade an existing local demo

Extract this version to a new project folder and copy your existing `.env` locally. If you are upgrading from the SQLite version, add the two `TRACKER_MONGODB_*` settings above. The previous MongoDB version already uses these settings. Use a fresh virtual environment in the new folder and reuse the existing seeded Atlas database for identities, findings, policies, and audit runs.

To keep any existing ticket references usable for the audit demo, stop both old services and import the old ticket file before starting the new services:

```bash
python -m scripts.migrate_tracker_tickets "/path/to/old/project/tracker.sqlite3"
```

The import reads the old file without modifying it and preserves ticket IDs, statuses and run IDs. It can be repeated without overwriting tickets already stored in MongoDB. For a fresh demo with no existing tickets, start the services and propose a new run.

## Run tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

GitHub Actions uses two databases in a disposable MongoDB instance and runs the full ticket workflow against both HTTP services. See [GitHub setup](GITHUB_SETUP.md) for the first push.
