# db.py
# MongoDB helper functions and schema-level helpers
from pymongo import MongoClient, ReturnDocument, ASCENDING, TEXT
import os
import re
import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")  # must include db name
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required (include DB name in URL).")

client = MongoClient(DATABASE_URL)
db = client.get_default_database()

# Collections
categories = db.categories            # { _id: "fantasy", name: "Fantasy", count: 0 }
stories = db.stories                  # story docs (vision_id unique)
episodes = db.episodes                # episodes: either single ep or range (shortlink)
user_states = db.user_states          # ephemeral state per admin/user
admins = db.admins                    # admin list doc { _id: "admin_list", owner_id:int, admins:[] }
requests = db.requests                # forwarded user requests

# Ensure indexes on startup
def ensure_indexes():
    # stories: unique vision_id
    stories.create_index([("vision_id", ASCENDING)], unique=True)
    # text index for search (title + description)
    try:
        stories.create_index([("title", TEXT), ("description", TEXT)], name="text_title_description", default_language="english")
    except Exception:
        # ignore if index exists or earlier mongo versions differ
        pass
    # episodes lookup
    episodes.create_index([("story_vision_id", ASCENDING), ("ep_no", ASCENDING)], unique=True, sparse=True)
    # episodes range index for shortlinks
    episodes.create_index([("story_vision_id", ASCENDING), ("ep_no_start", ASCENDING), ("ep_no_end", ASCENDING)])

ensure_indexes()

# Helpers

def get_categories():
    """Return list of categories with counts."""
    return list(categories.find({}, {"name": 1, "count": 1}).sort("name", 1))

def get_category(slug):
    return categories.find_one({"_id": slug})

def upsert_category(slug, name=None):
    update = {"$setOnInsert": {"name": name or slug.capitalize()}}
    res = categories.find_one_and_update({"_id": slug}, update, upsert=True, return_document=ReturnDocument.AFTER)
    if "count" not in res:
        categories.update_one({"_id": slug}, {"$set": {"count": 0}})
        res = categories.find_one({"_id": slug})
    return res

def gen_vision_id(category_slug, prefix=None):
    """
    Atomically increment category.count and return vision id like fa01, lo01.
    prefix param can override default prefix logic.
    """
    if not prefix:
        # define mapping or fallback to first two letters
        prefix = category_slug[:2].lower()
    res = categories.find_one_and_update(
        {"_id": category_slug},
        {"$inc": {"count": 1}, "$setOnInsert": {"name": category_slug.capitalize()}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    num = res.get("count", 1)
    vision = f"{prefix}{num:02d}"
    return vision

def add_story(category_slug, title, photo_file_id, description, created_by):
    """
    Create story, generate vision id, post and return story doc.
    """
    # ensure category exists and increment count inside gen_vision_id
    vision = gen_vision_id(category_slug)
    doc = {
        "vision_id": vision,
        "category": category_slug,
        "title": title,
        "photo_file_id": photo_file_id,
        "description": description,
        "created_by": created_by,
        "created_at": datetime.datetime.utcnow()
    }
    stories.insert_one(doc)
    return doc

def get_story_by_vision(vision_id):
    return stories.find_one({"vision_id": vision_id})

def search_stories_text(query, limit=10):
    """
    Prefer text index search; fallback to regex search.
    """
    if not query:
        return []
    try:
        cursor = stories.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}, "vision_id": 1, "title": 1, "description": 1, "photo_file_id": 1}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        return list(cursor)
    except Exception:
        regex = {"$regex": re.escape(query), "$options": "i"}
        cursor = stories.find({"$or": [{"title": regex}, {"description": regex}]}, {"vision_id":1,"title":1,"description":1,"photo_file_id":1}).limit(limit)
        return list(cursor)

def add_episode(vision_id, ep_no=None, link=None, short=False, ep_no_start=None, ep_no_end=None):
    """
    Add single episode (ep_no) or a shortlink range (ep_no_start..ep_no_end).
    """
    doc = {
        "story_vision_id": vision_id,
        "link": link,
        "short": bool(short),
        "added_at": datetime.datetime.utcnow()
    }
    if ep_no is not None:
        doc["ep_no"] = int(ep_no)
    else:
        # range case
        doc["ep_no_start"] = int(ep_no_start)
        doc["ep_no_end"] = int(ep_no_end)
    episodes.insert_one(doc)
    return doc

def find_episode_single(vision_id, ep_no):
    return episodes.find_one({"story_vision_id": vision_id, "ep_no": int(ep_no)})

def find_shortlink_for_range(vision_id, start, end):
    # find a doc with ep_no_start <= start and ep_no_end >= end
    return episodes.find_one({
        "story_vision_id": vision_id,
        "short": True,
        "ep_no_start": {"$lte": int(start)},
        "ep_no_end": {"$gte": int(end)}
    })

# State helpers
def set_state(user_id, state_dict):
    state = {"_id": user_id}
    state.update(state_dict)
    user_states.replace_one({"_id": user_id}, state, upsert=True)
def get_state(user_id):
    return user_states.find_one({"_id": user_id}) or {}
def clear_state(user_id):
    user_states.delete_one({"_id": user_id})

# Admin list helpers
def get_admins_doc():
    return admins.find_one({"_id": "admin_list"}) or {"_id":"admin_list","owner_id": None, "admins": []}
def is_admin(user_id):
    doc = get_admins_doc()
    owner = doc.get("owner_id")
    if owner and owner == user_id:
        return True
    return user_id in doc.get("admins", [])

def add_admin(uid):
    admins.update_one({"_id":"admin_list"}, {"$addToSet":{"admins": uid}}, upsert=True)

def set_owner(uid):
    admins.update_one({"_id":"admin_list"}, {"$set":{"owner_id": uid}}, upsert=True)
