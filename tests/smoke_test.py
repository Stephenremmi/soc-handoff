"""End-to-end smoke test using a disposable local MongoDB and real HTTP services."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from uuid import uuid4

import httpx
from pymongo import MongoClient
from pymongo.errors import OperationFailure

ROOT = Path(__file__).resolve().parents[1]
MONGO_URI = "mongodb://127.0.0.1:27017/?directConnection=true"
MONGO_DB = "soc_handoff_ci"
TRACKER_MONGO_DB = "soc_handoff_tracker_ci"
APP_URL = "http://127.0.0.1:18000"
TRACKER_URL = "http://127.0.0.1:18001"


@contextmanager
def running_service(target, port, env, logs):
    with (logs / f"{target.split(':')[0]}.log").open("w+") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", target, "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(timeout=2, trust_env=False) as client:
                for _ in range(50):
                    if process.poll() is not None:
                        raise RuntimeError(f"{target} exited during startup")
                    try:
                        response = client.get(f"http://127.0.0.1:{port}/api/health")
                        if response.is_success:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.2)
                else:
                    raise RuntimeError(f"{target} did not start in time")
            yield
        except Exception:
            log.seek(0)
            print(log.read(), file=sys.stderr)
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


class SOCHandoffSmokeTest(unittest.TestCase):
    def test_ticket_policy_and_rollback(self):
        if os.environ.get("MONGODB_URI") != MONGO_URI or os.environ.get("MONGODB_DATABASE") != MONGO_DB:
            self.fail("Use the disposable MongoDB URI and database configured in the CI workflow.")

        username = os.environ.get("SOC_DEMO_USER", "ci-analyst")
        password = secrets.token_urlsafe(24)
        token = secrets.token_urlsafe(24)
        with TemporaryDirectory(prefix="soc-handoff-ci-") as temp:
            logs = Path(temp)
            env = {
                **os.environ,
                "SOC_DEMO_USER": username,
                "SOC_DEMO_PASSWORD": password,
                "TRACKER_TOKEN": token,
                "TRACKER_URL": TRACKER_URL,
                "TRACKER_MONGODB_URI": MONGO_URI,
                "TRACKER_MONGODB_DATABASE": TRACKER_MONGO_DB,
                "PYTHON_DOTENV_DISABLED": "1",
            }
            with MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000) as mongo:
                db = mongo[MONGO_DB]
                tickets = mongo[TRACKER_MONGO_DB].tickets
                before = db.findings.find_one({"_id": "audit-mvp-F-103"})
                self.assertIsNotNone(before, "Run the seed step first")
                subprocess.run([sys.executable, "setup_demo.py"], cwd=ROOT, env=env, check=True)
                self.assertEqual(before, db.findings.find_one({"_id": before["_id"]}))
                with self.assertRaises(OperationFailure) as invalid:
                    db.audit_runs.insert_one({"_id": f"invalid-{uuid4()}"})
                self.assertEqual(invalid.exception.code, 121)

                with (
                    running_service("tracker:app", 18001, env, logs),
                    running_service("app:app", 18000, env, logs),
                    httpx.Client(base_url=APP_URL, auth=(username, password), timeout=5, trust_env=False) as app,
                    httpx.Client(
                        base_url=TRACKER_URL,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5,
                        trust_env=False,
                    ) as tracker,
                ):
                    home = app.get("/").raise_for_status()
                    self.assertIn("SOC Handoff", home.text)
                    self.assertRegex(home.headers["X-Request-ID"], r"^[0-9a-f]{32}$")
                    self.assertNotEqual(home.headers["X-Request-ID"], app.get("/api/health").headers["X-Request-ID"])
                    self.assertEqual(app.get("/api/health").json(), {"status": "ok"})
                    challenged = app.get("/", auth=None)
                    self.assertEqual(challenged.status_code, 401)
                    self.assertEqual(challenged.headers["WWW-Authenticate"], "Basic")
                    self.assertIn("X-Request-ID", challenged.headers)
                    self.assertEqual(app.post("/api/runs").status_code, 403)
                    self.assertEqual(tracker.get("/tickets/by-run/" + str(uuid4()), auth=None,
                                                 headers={"Authorization": ""}).status_code, 401)
                    headers = {"X-SOC-Action": "interactive"}
                    run = app.post("/api/runs", headers=headers).raise_for_status().json()
                    run_id = run["_id"]
                    endpoint = f"/api/runs/{run_id}"
                    tracker_ticket = f"/tickets/by-run/{run_id}"

                    blocked = app.post(f"{endpoint}/execute", headers=headers).raise_for_status().json()
                    self.assertEqual(blocked["events"][-1]["kind"], "Blocked")
                    self.assertEqual(tracker.get(tracker_ticket).status_code, 404)
                    self.assertIsNone(tickets.find_one({"_id": run_id}))

                    approved = app.post(f"{endpoint}/approve", headers=headers).raise_for_status().json()
                    self.assertEqual(approved["approval"]["actor"], username)
                    created = app.post(f"{endpoint}/execute", headers=headers).raise_for_status().json()
                    ticket = tracker.get(tracker_ticket).raise_for_status().json()
                    self.assertEqual(ticket["id"], created["ticket_id"])
                    self.assertEqual(ticket["status"], "open")
                    retry = app.post(f"{endpoint}/execute", headers=headers).raise_for_status().json()
                    self.assertEqual(retry["ticket_id"], ticket["id"])
                    self.assertEqual(tickets.find_one({"_id": run_id})["id"], ticket["id"])
                    self.assertIsNone(db.tickets.find_one({"_id": run_id}))

                    app.post(f"{endpoint}/rollback", headers=headers).raise_for_status()
                    self.assertEqual(tracker.get(tracker_ticket).raise_for_status().json()["status"], "closed")
                    closed = tickets.find_one({"_id": run_id})
                    self.assertEqual(closed["status"], "closed")
                    tracker.post(f"{tracker_ticket}/close").raise_for_status()
                    self.assertEqual(tickets.find_one({"_id": run_id})["closed_at"], closed["closed_at"])
                    stored = db.audit_runs.find_one({"_id": run_id})
                    self.assertEqual(stored["status"], "closed")
                    self.assertEqual(stored["ticket_id"], ticket["id"])
                    self.assertEqual([event["kind"] for event in stored["events"]], [
                        "Proposed", "Blocked", "Approved", "Allowed", "Ticket created",
                        "Rollback authorized", "Ticket closed",
                    ])

                    retry_run_id = str(uuid4())
                    payload = {
                        "run_id": retry_run_id, "title": "Concurrent ticket retry",
                        "alert_id": "SOC-1042", "evidence": "Synthetic identity log",
                    }
                    with ThreadPoolExecutor(max_workers=4) as pool:
                        responses = list(pool.map(lambda _: tracker.post("/tickets", json=payload), range(8)))
                    created_ids = {response.raise_for_status().json()["id"] for response in responses}
                    self.assertEqual(len(created_ids), 1)
                    self.assertEqual(tickets.count_documents({"run_id": retry_run_id}), 1)

                    legacy_db = logs / "legacy.sqlite3"
                    legacy_run = str(uuid4())
                    with closing(sqlite3.connect(legacy_db)) as old, old:
                        old.execute("CREATE TABLE tickets (id, run_id, title, alert_id, evidence, status)")
                        old.execute("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)", (
                            12, legacy_run, "Legacy ticket", "SOC-1042", "Synthetic identity log", "open",
                        ))
                    for expected in ("Imported 1 tickets", "Imported 0 tickets"):
                        result = subprocess.run(
                            [sys.executable, "-m", "scripts.migrate_tracker_tickets", str(legacy_db)],
                            cwd=ROOT, env=env, check=True, capture_output=True, text=True,
                        )
                        self.assertIn(expected, result.stdout)
                    legacy_ticket = tracker.get(f"/tickets/by-run/{legacy_run}").raise_for_status().json()
                    self.assertEqual(legacy_ticket["id"], "TKT-0012")



if __name__ == "__main__":
    unittest.main(verbosity=2)
