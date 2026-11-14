"""Coordinate human approval, audit transitions, and sandbox ticket actions."""

from datetime import datetime, timezone
from uuid import uuid4

from ..errors import Conflict, TrackerUnavailable
from ..database.repository import MongoStore
from ..demo import FINDING_ID
from .policy import ACTION, DESTINATION, check_create, permits_rollback
from ..integrations.tracker import TrackerClient

AGENT = "SOC Handoff"


def audit_event(kind, actor, reason, **details):
    return {"kind": kind, "actor": actor["_id"], "at": datetime.now(timezone.utc), "reason": reason, **details}


class HandoffWorkflow:
    def __init__(self, store: MongoStore, tracker: TrackerClient):
        self.store = store
        self.tracker = tracker

    def propose(self, actor):
        finding = self.store.finding(FINDING_ID)
        if not finding:
            raise Conflict("Initialize the Atlas demo first")
        run = {
            "_id": str(uuid4()),
            "status": "proposed",
            "actor": actor["_id"],
            "revision": 0,
            "alert_id": finding["alert_id"],
            "finding_id": finding["_id"],
            "finding_title": finding["title"],
            "title": "Review activity after the successful sign-in",
            "evidence": finding["evidence"],
            "action": ACTION,
            "destination": DESTINATION,
            "events": [audit_event(
                "Proposed", actor, "SOC Handoff proposed a follow-up from the linked prior-shift evidence.",
                agent=AGENT,
            )],
        }
        self.store.add_run(run)
        return run

    def read(self, run_id, actor):
        return self.store.run(run_id, actor["_id"])

    def approve(self, run_id, actor):
        run = self.read(run_id, actor)
        if run["status"] != "proposed":
            raise Conflict("Only a proposed action can be approved.")
        policy = self.store.policy()
        version = policy["version"] if policy else None
        reason = check_create(run, actor, policy, self.store.finding(run["finding_id"]), require_approval=False)
        if reason:
            return self.store.record(run, {}, audit_event("Approval blocked", actor, reason, policy_version=version))
        event = audit_event(
            "Approved", actor, "Analyst approved creation of this specific sandbox ticket.", policy_version=version
        )
        return self.store.record(run, {
            "status": "approved",
            "approval": {"actor": actor["_id"], "policy_version": version, "at": event["at"]},
        }, event)

    def execute(self, run_id, actor):
        run = self.read(run_id, actor)
        if run["status"] == "created":
            return run
        if run["status"] not in {"proposed", "approved", "creating"}:
            raise Conflict("This run cannot create a ticket in its current state.")

        policy = self.store.policy()
        version = policy["version"] if policy else None
        reason = check_create(run, actor, policy, self.store.finding(run["finding_id"]), require_approval=True)
        if reason:
            return self.store.record(run, {}, audit_event("Blocked", actor, reason, policy_version=version))

        run = self.store.record(run, {"status": "creating"}, audit_event(
            "Allowed", actor, "Verified finding and explicit approval satisfied the policy before contacting the tracker.",
            agent=AGENT, policy_version=version, action=ACTION, destination=DESTINATION,
        ))
        try:
            ticket_id = self.tracker.create(run)
        except TrackerUnavailable:
            return self.store.record(run, {}, audit_event(
                "Result unconfirmed", actor,
                "Tracker did not confirm creation. Retry this run to reconcile without creating a duplicate.",
            ))
        return self.store.record(run, {"status": "created", "ticket_id": ticket_id}, audit_event(
            "Ticket created", actor, "The tracker confirmed the ticket write.", ticket_id=ticket_id, agent=AGENT,
        ))

    def stop(self, run_id, actor):
        run = self.read(run_id, actor)
        if run["status"] not in {"proposed", "approved"}:
            raise Conflict("The run already dispatched an action or was stopped.")
        return self.store.record(run, {"status": "canceled"}, audit_event(
            "Stopped", actor, "Analyst stopped this run before a tracker write.",
        ))

    def rollback(self, run_id, actor):
        run = self.read(run_id, actor)
        if run["status"] == "closed":
            return run
        if run["status"] not in {"created", "closing"}:
            raise Conflict("Only a created ticket can be rolled back.")

        policy = self.store.policy()
        version = policy["version"] if policy else None
        if not permits_rollback(run, actor, policy):
            return self.store.record(run, {}, audit_event(
                "Rollback blocked", actor, "The Atlas rollback policy does not permit this actor or destination.",
                policy_version=version,
            ))

        ticket_id = run["ticket_id"]
        run = self.store.record(run, {"status": "closing"}, audit_event(
            "Rollback authorized", actor, "Analyst approved the compensating close for this run's sandbox ticket.",
            ticket_id=ticket_id, policy_version=version,
        ))
        try:
            self.tracker.close(run_id, ticket_id)
        except TrackerUnavailable:
            return self.store.record(run, {}, audit_event(
                "Rollback unconfirmed", actor, "Tracker did not confirm closure. Retry rollback.",
            ))
        return self.store.record(run, {"status": "closed"}, audit_event(
            "Ticket closed", actor, "Tracker confirmed the compensating close.", ticket_id=ticket_id, agent=AGENT,
        ))

    def ticket(self, run_id, actor):
        self.read(run_id, actor)
        return self.tracker.read(run_id)
