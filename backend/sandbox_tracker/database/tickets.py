"""Ticket persistence owned by the sandbox tracker."""

from datetime import datetime, timezone
from uuid import UUID

from pymongo import ReturnDocument

class TicketStore:
    def __init__(self, collection):
        self.collection = collection

    def get(self, run_id: UUID):
        return self.collection.find_one({"_id": str(run_id)}, {"_id": False})

    def create(self, run_id: UUID, fields: dict):
        return self.collection.find_one_and_update(
            {"_id": str(run_id)},
            {"$setOnInsert": {
                **fields,
                "id": f"TKT-{run_id.hex}",
                "run_id": str(run_id),
                "status": "open",
                "created_at": datetime.now(timezone.utc),
            }},
            projection={"_id": False},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    def close(self, run_id: UUID):
        closed = self.collection.find_one_and_update(
            {"_id": str(run_id), "status": "open"},
            {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc)}},
            projection={"_id": False},
            return_document=ReturnDocument.AFTER,
        )
        return closed if closed is not None else self.get(run_id)
