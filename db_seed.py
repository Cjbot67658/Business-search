# db_seed.py
"""
Seed script for categories and demo stories/episodes.
This script does NOT upload real files. Replace demo file_ids with actual file_id strings from your private channel posts.
"""
from db import categories, stories, episodes
import uuid

def seed_categories():
    cats = ["Drama", "Mystery", "Sci-Fi", "Kids", "Self-Help"]
    for c in cats:
        categories.update_one({"name": c}, {"$setOnInsert": {"name": c}}, upsert=True)
    print("Seeded categories.")

def seed_demo_story():
    vision_id = "demo-" + uuid.uuid4().hex[:8]
    stories.update_one({"vision_id": vision_id}, {"$set": {
        "vision_id": vision_id,
        "title": "Demo Story — The Little Clockmaker",
        "description": "A short demo story to verify integration.",
        "categories": ["Kids"],
        "photo_file_id": "",  # optional: add a photo file_id from your private channel
        "created_at": __import__("datetime").datetime.utcnow()
    }}, upsert=True)

    # Seed 3 demo episodes with placeholder file_id (replace with real file_id after uploading to private channel)
    for i in range(1, 4):
        episodes.update_one({"story_id": vision_id, "episode_number": i}, {"$set": {
            "story_id": vision_id,
            "episode_number": i,
            "title": f"Episode {i}",
            "description": f"Demo episode {i}",
            "file_type": "document",
            "file_id": "REPLACE_WITH_REAL_FILE_ID",
            "created_at": __import__("datetime").datetime.utcnow()
        }}, upsert=True)
    print("Seeded demo story:", vision_id)

if __name__ == "__main__":
    seed_categories()
    seed_demo_story()
    print("Done.")
