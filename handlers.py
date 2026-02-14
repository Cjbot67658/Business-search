# handlers.py
import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_ID, ADMIN_IDS, SEARCH_RESULT_LIMIT, AUTO_DELETE_MINUTES
import db as DB
from utils import parse_episode_input, short
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# --- UI helpers
def mk_keyboard(rows):
    return InlineKeyboardMarkup(rows)

def story_result_row(story):
    title = story.get("title", "Untitled")
    vid = story.get("vision_id")
    thumb = story.get("photo_file_id")
    desc = short(story.get("description", ""), 120)
    buttons = [
        [InlineKeyboardButton("View Episodes 🎧", callback_data=f"view:{vid}")],
        [InlineKeyboardButton("Listen (first ep) ▶️", callback_data=f"listen:{vid}:first")]
    ]
    return title, desc, thumb, mk_keyboard(buttons)

# --- Command handlers
async def cmd_start(client, message):
    txt = (
        "Welcome! Use /search or tap Search 🔎 to find stories.\n\n"
        "• /search — text search\n"
        "• Explore All 📂 — browse categories\n"
        "• Send any message and it'll be forwarded to admins"
    )
    kb = mk_keyboard([
        [InlineKeyboardButton("Search 🔎", callback_data="action:search"),
         InlineKeyboardButton("Explore All 📂", callback_data="action:explore")]
    ])
    await message.reply_text(txt, reply_markup=kb)

async def cmd_search(client, message):
    # Create session in DB and ask for query
    DB.clear_session(message.from_user.id)
    DB.create_session(message.from_user.id, mode="search", stage="waiting_for_query")
    await message.reply_text("Send me the search query (title or description). Example: *detective thriller*", parse_mode="markdown")

async def on_callback_query(client, callback_query):
    data = callback_query.data or ""
    user_id = callback_query.from_user.id
    if data.startswith("action:search"):
        DB.clear_session(user_id)
        DB.create_session(user_id, mode="search", stage="waiting_for_query")
        await callback_query.message.reply_text("Send your search keywords now.")
        await callback_query.answer()
        return

    if data.startswith("action:explore"):
        cats = DB.get_categories()
        if not cats:
            await callback_query.message.reply_text("No categories found.")
            await callback_query.answer()
            return
        rows = []
        for c in cats:
            rows.append([InlineKeyboardButton(c["name"], callback_data=f"cat:{c['name']}")])
        await callback_query.message.reply_text("Choose category:", reply_markup=mk_keyboard(rows))
        await callback_query.answer()
        return

    if data.startswith("cat:"):
        cat = data.split(":", 1)[1]
        stories = DB.get_stories_by_category(cat)
        if not stories:
            await callback_query.message.reply_text("No stories found in that category.")
            await callback_query.answer()
            return
        for s in stories[:10]:
            title, desc, thumb, kb = story_result_row(s)
            await callback_query.message.reply_photo(photo=s.get("photo_file_id"), caption=f"*{title}*\n\n{desc}", parse_mode="markdown", reply_markup=kb)
        await callback_query.answer()
        return

    if data.startswith("view:"):
        vision_id = data.split(":", 1)[1]
        story = DB.get_story_by_vision(vision_id)
        if not story:
            await callback_query.answer("Story not found", show_alert=True)
            return
        # Create episode selection session
        DB.clear_session(user_id)
        DB.create_session(user_id, mode="episode_input", stage="waiting_for_episode", payload={"vision_id": vision_id})
        await callback_query.message.reply_text(
            f"You selected *{story['title']}*.\nSend an episode number (e.g., `10`) or a range (`1-5`).",
            parse_mode="markdown"
        )
        await callback_query.answer()
        return

    if data.startswith("listen:"):
        _, vision_id, flag = data.split(":", 2)
        if flag == "first":
            eps = DB.get_episodes_for_story(vision_id, min_ep=1, max_ep=1)
            if not eps:
                await callback_query.answer("No episode found", show_alert=True)
                return
            ep = eps[0]
            await deliver_episode(client, callback_query.message.chat.id, ep, auto_delete=AUTO_DELETE_MINUTES)
            await callback_query.answer()
            return

    await callback_query.answer()

async def on_message(client, message):
    text = (message.text or message.caption or "").strip()
    user_id = message.from_user.id

    # If there is an active session for this user handle it first
    session = DB.get_session(user_id)
    if session:
        mode = session.get("mode")
        stage = session.get("stage")
        payload = session.get("payload", {})
        if mode == "search" and stage == "waiting_for_query":
            # Process search
            query = text
            DB.clear_session(user_id)
            results = DB.search_stories_text(query, limit=SEARCH_RESULT_LIMIT)
            if not results:
                await message.reply_text("No results. Try a different keyword.")
                return
            for s in results:
                title, desc, thumb, kb = story_result_row(s)
                await message.reply_photo(photo=s.get("photo_file_id"), caption=f"*{title}*\n\n{desc}", parse_mode="markdown", reply_markup=kb)
            return

        if mode == "episode_input" and stage == "waiting_for_episode":
            parse = parse_episode_input(text)
            DB.clear_session(user_id)
            if not parse:
                await message.reply_text("Couldn't parse your input. Send `10` or `1-5` format.")
                return
            start, end = parse
            eps = DB.get_episodes_for_story(payload["vision_id"], min_ep=start, max_ep=end)
            if not eps:
                await message.reply_text("No episodes found for that range.")
                return
            await message.reply_text(f"Found {len(eps)} episode(s). Delivering now...")
            for ep in eps:
                await deliver_episode(client, message.chat.id, ep, auto_delete=AUTO_DELETE_MINUTES)
            return

    # If message looks like a command that we don't handle, ignore for now
    if text.startswith("/"):
        if text.startswith("/start"):
            await cmd_start(client, message)
            return
        if text.startswith("/search"):
            await cmd_search(client, message)
            return

    # Unknown non-command messages -> forward to admins
    # Save a copy/audit and forward to configured admins
    payload = {
        "from_user": {"id": user_id, "name": message.from_user.mention},
        "text": text,
        "message_id": message.message_id,
        "date": message.date.isoformat()
    }
    # store audit
    DB.forward_to_admins(payload)
    # forward content to admins (do not expose channel)
    for admin in ADMIN_IDS:
        try:
            # forward the actual message to admins (preserves content), but not exposing our private storage
            # forwarding is from the user to admin - ok
            await client.forward_messages(admin, message.chat.id, message.message_id)
        except Exception as e:
            logger.exception("Failed to forward to admin %s: %s", admin, e)
    await message.reply_text("Thanks — your message was forwarded to our admins. We'll get back if needed.")
