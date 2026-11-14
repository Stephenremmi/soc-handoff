"""Process configuration for SOC Handoff and its seed command."""

from dataclasses import dataclass, field
from os import environ
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ANALYST = "demo-analyst"


@dataclass(frozen=True)
class Settings:
    mongodb_uri: str = field(repr=False)
    mongodb_database: str = "soc_handoff"
    analyst: str = DEFAULT_ANALYST
    analyst_password: str | None = field(default=None, repr=False)
    tracker_url: str = "http://127.0.0.1:8001"
    tracker_token: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls):
        if environ.get("PYTHON_DOTENV_DISABLED", "").lower() not in {"1", "true", "t", "yes", "y"}:
            load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        uri = environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError("Set MONGODB_URI in your local .env file")
        return cls(
            mongodb_uri=uri,
            mongodb_database=environ.get("MONGODB_DATABASE", "soc_handoff"),
            analyst=environ.get("SOC_DEMO_USER", DEFAULT_ANALYST),
            analyst_password=environ.get("SOC_DEMO_PASSWORD"),
            tracker_url=environ.get("TRACKER_URL", "http://127.0.0.1:8001"),
            tracker_token=environ.get("TRACKER_TOKEN"),
        )
