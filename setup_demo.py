"""Initialize the isolated Atlas demo collections or observe their change stream."""
import sys

from soc_handoff.config import Settings
from soc_handoff.database.client import atlas_client
from soc_handoff.database.seed import seed

if __name__ == "__main__":
    settings = Settings.from_environment()
    with atlas_client(settings) as client:
        db = client[settings.mongodb_database]
        if sys.argv[1:] == ["watch"]:
            with db.audit_runs.watch(full_document="updateLookup") as stream:
                print("Watching Atlas audit writes. Leave this window open.", flush=True)
                for change in stream:
                    run = change.get("fullDocument")
                    if run and run.get("events"):
                        event = run["events"][-1]
                        print(f'{run["_id"]}  {event["kind"]}  {event["actor"]}  {event["reason"]}', flush=True)
        elif not sys.argv[1:]:
            seed(db, settings.analyst)
            print(f"Atlas initialized and synthetic evidence written to {db.name}.")
        else:
            raise SystemExit("Usage: python setup_demo.py [watch]")
