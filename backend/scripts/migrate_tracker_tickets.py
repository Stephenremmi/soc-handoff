"""Copy tickets from the original tracker to MongoDB, preserving audit references."""

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
from uuid import UUID

from pymongo.errors import DuplicateKeyError

from sandbox_tracker.config import TrackerSettings
from sandbox_tracker.database.client import tracker_client


def copy_tickets(source, collection):
    rows = source.execute("SELECT id, run_id, title, alert_id, evidence, status FROM tickets")
    copied = 0
    existing = 0
    for row in rows:
        ticket = dict(row)
        ticket["run_id"] = str(UUID(ticket["run_id"]))
        ticket["_id"] = ticket["run_id"]
        ticket["id"] = f"TKT-{ticket['id']:04d}"
        if ticket["status"] not in {"open", "closed"}:
            raise ValueError(f"Invalid status for {ticket['id']}: {ticket['status']}")
        try:
            collection.insert_one(ticket)
        except DuplicateKeyError:
            current = collection.find_one({"_id": ticket["_id"]})
            identity_fields = ("id", "run_id", "title", "alert_id", "evidence")
            if current is None or any(current[field] != ticket[field] for field in identity_fields):
                raise RuntimeError(f"Ticket conflict for run {ticket['_id']}. Existing records were kept.") from None
            existing += 1
        else:
            copied += 1
    return copied, existing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_file", type=Path)
    args = parser.parse_args()
    if not args.sqlite_file.is_file():
        parser.error("The original SQLite file was not found.")

    settings = TrackerSettings.from_environment()
    uri = args.sqlite_file.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as source, tracker_client(settings) as mongo:
        source.row_factory = sqlite3.Row
        copied, existing = copy_tickets(source, mongo[settings.mongodb_database].tickets)
    print(f"Imported {copied} tickets; {existing} already present.")


if __name__ == "__main__":
    main()
