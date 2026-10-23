
from datetime import datetime, timezone

from pymongo import MongoClient

from app.config import settings

_client = None


def get_collection():
    """Connect to MongoDB and return the GPS history collection."""

    global _client

    try:
        if _client is None:
            _client = MongoClient(
                settings.mongodb_url,
                serverSelectionTimeoutMS=500,
            )

        _client.admin.command("ping")

        return _client[settings.mongodb_database]["vehicle_locations"]

    except Exception:
        return None


def save_location(vehicle_id: int, payload: dict) -> bool:
    """Save one GPS reading to MongoDB."""

    collection = get_collection()

    if collection is None:
        return False

    document = {
        **payload,
        "vehicle_id": vehicle_id,
        "recorded_at": datetime.now(timezone.utc),
    }

    collection.insert_one(document)

    return True


def get_history(vehicle_id: int, limit: int = 100) -> list:
    """Return recent GPS readings for a vehicle."""

    collection = get_collection()

    if collection is None:
        return []

    documents = list(
        collection.find(
            {"vehicle_id": vehicle_id},
            {"_id": 0},
        )
        .sort("recorded_at", -1)
        .limit(limit)
    )

    for document in documents:
        for key, value in list(document.items()):
            if isinstance(value, datetime):
                document[key] = value.isoformat()

    return documents
