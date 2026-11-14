"""Validate and seed the collections used by the local demo."""

from datetime import datetime, timezone

from ..demo import FINDING_ID
from ..services.policy import ACTION, DESTINATION, POLICY_ID

SCHEMAS = {
    "audit_identities": {
        "_id": {"bsonType": "string"},
        "role": {"enum": ["analyst", "viewer"]},
        "active": {"bsonType": "bool"},
    },
    "audit_policies": {
        "_id": {"bsonType": "string"},
        "version": {"bsonType": ["int", "long"]},
        "enabled": {"bsonType": "bool"},
        "role": {"enum": ["analyst"]},
        "action": {"enum": [ACTION]},
        "destination": {"enum": [DESTINATION]},
        "require_verified": {"enum": [True]},
        "require_approval": {"enum": [True]},
        "allow_rollback": {"bsonType": "bool"},
    },
    "audit_runs": {
        "_id": {"bsonType": "string"},
        "actor": {"bsonType": "string"},
        "status": {"enum": ["proposed", "approved", "creating", "created", "canceled", "closing", "closed"]},
        "finding_id": {"bsonType": "string"},
        "finding_title": {"bsonType": "string"},
        "title": {"bsonType": "string"},
        "action": {"enum": [ACTION]},
        "destination": {"enum": [DESTINATION]},
        "revision": {"bsonType": ["int", "long"]},
        "events": {"bsonType": "array", "items": {
            "bsonType": "object",
            "required": ["kind", "at", "actor", "reason"],
            "properties": {
                "kind": {"bsonType": "string"},
                "at": {"bsonType": "date"},
                "actor": {"bsonType": "string"},
                "reason": {"bsonType": "string"},
            },
        }},
    },
}


def now():
    return datetime.now(timezone.utc)


def seed(db, username):
    existing = db.list_collection_names()
    for name, fields in SCHEMAS.items():
        schema = {"bsonType": "object", "required": list(fields), "properties": fields}
        validator = {"$jsonSchema": schema}
        if name not in existing:
            db.create_collection(name, validator=validator)
        else:
            db.command("collMod", name, validator=validator)

    db.audit_identities.update_one({"_id": username}, {"$setOnInsert": {
        "role": "analyst", "active": True,
    }}, upsert=True)
    db.audit_policies.update_one({"_id": POLICY_ID}, {"$setOnInsert": {
        "version": 1, "enabled": True, "role": "analyst", "action": ACTION,
        "destination": DESTINATION, "require_verified": True, "require_approval": True, "allow_rollback": True,
    }}, upsert=True)
    db.findings.update_one({"_id": FINDING_ID}, {"$setOnInsert": {
        "title": "Successful sign-in from an unfamiliar network",
        "alert_id": "SOC-1042",
        "detail": "Identity logs recorded a successful sign-in from 203.0.113.24 after repeated MFA prompts.",
        "evidence": "Synthetic identity log IDP-9031",
        "verified_by": "Jamie Park (synthetic analyst)",
        "verified_at": now(),
    }}, upsert=True)
