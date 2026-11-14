"""Configuration for the tracker service and its migration command."""

from dataclasses import dataclass, field
from os import environ
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class TrackerSettings:
    mongodb_uri: str = field(repr=False)
    mongodb_database: str = "soc_handoff_tracker"
    token: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls):
        if environ.get("PYTHON_DOTENV_DISABLED", "").lower() not in {"1", "true", "t", "yes", "y"}:
            load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        uri = environ.get("TRACKER_MONGODB_URI")
        if not uri:
            raise RuntimeError("Set TRACKER_MONGODB_URI in your local .env file")
        return cls(
            mongodb_uri=uri,
            mongodb_database=environ.get("TRACKER_MONGODB_DATABASE", "soc_handoff_tracker"),
            token=environ.get("TRACKER_TOKEN"),
        )
