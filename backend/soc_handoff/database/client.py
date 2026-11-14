"""Construct the process-owned MongoDB client."""

from pymongo import MongoClient

from ..config import Settings


def atlas_client(settings: Settings):
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
