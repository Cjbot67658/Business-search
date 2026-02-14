import pymongo
from pymongo import ASCENDING, TEXT
from config import DATABASE_URL, SESSION_TTL_SECONDS
from datetime import datetime

client = pymongo.MongoClient(DATABASE_URL)
db = client.get_default_database()

# Collections
stories = db["stories"]        # story metadata (one document per story)
episodes = db["episodes"]      # each episode file (linked to story via story_id)
categories = db["categories"]  # categories collection
sessions = db["sessions"]      # user sessions (persistent state)
users = db["users"]            # optional user records / stats

def ensure_indexes():
    # Text index on stories title and description for search
    stories.create_index([("title", TEXT), ("description", TEXT)], name="text_title_description", default_language="english")

    # Index categories.name unique
    categories.create_index([("name", ASCENDING)], unique=True)

    # Index for fetching episodes quickly
    episodes.create_index([("story_id", ASCENDING), ("episode_number", ASCENDING)], unique=True)

    # TTL index on sessions so stale sessions are removed
    sessions.create_index([("created_at", ASCENDING)], expireAfterSeconds=SESSION_TTL_SECONDS)

    # Optional index for quick lookups
    stories.create_index([("vision_id", ASCENDING)], unique=True)

# Call to ensure indexes on import
ensure_indexes()

# Helper wrapper functions (synchronous). For production, wrap these in run_in_executor in async handlers.
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

def search_stories_text(query: str, limit: int = 7):
    # First try text search
    cursor = stories.find({"$text": {"$search": query}}, {"score": {"$meta": "textScore"}}).sort([("score", {"$meta": "textScore"})]).limit(limit)
    results = list(cursor)
    if results:
        return results
    # Fallback partial (case-insensitive) regex matching on title and description
    regex = {"$regex": query, "$options": "i"}
    cursor = stories.find({"$or": [{"title": regex}, {"description": regex}]}).limit(limit)
    return list(cursor)

def get_categories():
    return list(categories.find({}).sort("name", 1))

def get_stories_by_category(cat_name: str, limit: int = 50):
    return list(stories.find({"categories": cat_name}).limit(limit))

def get_story_by_vision(vision_id: str):
    return stories.find_one({"vision_id": vision_id})

def get_episodes_for_story(vision_id: str, min_ep: int = None, max_ep: int = None):
    q = {"story_id": vision_id}
    if min_ep is not None and max_ep is not None:
        q["episode_number"] = {"$gte": min_ep, "$lte": max_ep}
    elif min_ep is not None:
        q["episode_number"] = min_ep
    return list(episodes.find(q).sort("episode_number", 1))

def forward_to_admins(payload):
    # store an audit copy
    db["forwards"].insert_one({"payload": payload, "forwarded_at": datetime.utcnow()})
