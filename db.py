# db.py
import os
from urllib.parse import urlparse
from pymongo import MongoClient, ASCENDING, TEXT
from pymongo.errors import ConfigurationError
from datetime import datetime

# Read env here to avoid circular imports
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")  # optional fallback name
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(60 * 5)))

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required.")

client = MongoClient(DATABASE_URL)

def _resolve_db():
    """
    Returns a pymongo Database object.
    Tries, in order:
      1. client.get_default_database() — works if URI contains /dbname
      2. DATABASE_NAME env var
      3. parse path segment from DATABASE_URL (e.g. mongodb.net/mydb)
      4. raise helpful error
    """
    try:
        # Preferred: URI contains database name: mongodb+srv://.../mydb?...
        return client.get_default_database()
    except ConfigurationError:
        # No default DB in URI; try fallback env var
        if DATABASE_NAME:
            return client[DATABASE_NAME]

        # Try to parse path part of the URL
        parsed = urlparse(DATABASE_URL)
        if parsed.path and len(parsed.path) > 1:
            return client[parsed.path.lstrip("/")]

        # Nothing worked — raise clear runtime error
        raise RuntimeError(
            "No default database specified. Either include the database name in DATABASE_URL "
            "(e.g. mongodb.net/mydb) or set the DATABASE_NAME environment variable."
        )

db = _resolve_db()

# Collections
stories = db["stories"]
episodes = db["episodes"]
categories = db["categories"]
sessions = db["sessions"]
users = db["users"]

def ensure_indexes():
    # Text index for search
    stories.create_index([("title", TEXT), ("description", TEXT)],
                         name="text_title_description", default_language="english")
    # Unique categories
    categories.create_index([("name", ASCENDING)], unique=True)
    # Episodes fast lookup
    episodes.create_index([("story_id", ASCENDING), ("episode_number", ASCENDING)], unique=True)
    # TTL for sessions
    sessions.create_index([("created_at", ASCENDING)], expireAfterSeconds=SESSION_TTL_SECONDS)
    # Unique story id
    stories.create_index([("vision_id", ASCENDING)], unique=True)

# Ensure indexes on import
ensure_indexes()

# (Optional) helper shortcuts used elsewhere
def create_session(user_id: int, mode: str, stage: str, payload: dict = None):
    doc = {
        "user_id": user_id,
        "mode": mode,
        "stage": stage,
        "payload": payload or {},
        "created_at": datetime.utcnow()
    }
    sessions.insert_one(doc)
    return doc

def get_session(user_id: int):
    return sessions.find_one({"user_id": user_id})

def clear_session(user_id: int):
    sessions.delete_many({"user_id": user_id})
