"""Construct the tracker-owned MongoDB client."""

from pymongo import MongoClient

from ..config import TrackerSettings


def tracker_client(settings: TrackerSettings):
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
