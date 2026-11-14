"""Workflow errors independent of FastAPI."""


class NotFound(Exception):
    """The requested run or ticket is unavailable to this actor."""


class Conflict(Exception):
    """The run cannot make the requested transition."""


class TrackerUnavailable(Exception):
    """The tracker did not provide a usable response."""
