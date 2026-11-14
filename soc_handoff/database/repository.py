"""MongoDB reads and atomic run/audit transitions."""

from pymongo import ReturnDocument

from ..errors import Conflict, NotFound
from ..services.policy import POLICY_ID


class MongoStore:
    def __init__(self, db):
        self.db = db

    def identity(self, username):
        return self.db.audit_identities.find_one({"_id": username})

    def policy(self):
        return self.db.audit_policies.find_one({"_id": POLICY_ID})

    def finding(self, finding_id):
        return self.db.findings.find_one({"_id": finding_id})

    def add_run(self, run):
        self.db.audit_runs.insert_one(run)

    def run(self, run_id, actor_id):
        run = self.db.audit_runs.find_one({"_id": str(run_id), "actor": actor_id})
        if not run:
            raise NotFound("Run not found")
        return run

    def record(self, run, changes, event):
        """Persist the transition and its audit event in one revision-checked write."""
        updated = self.db.audit_runs.find_one_and_update(
            {"_id": run["_id"], "revision": run["revision"]},
            {"$set": changes, "$inc": {"revision": 1}, "$push": {"events": event}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise Conflict("This run changed. Reload its status and try again.")
        return updated
