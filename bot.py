# bot.py
import asyncio
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN
import handlers
from db import db  # ensures indexes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("story_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Register handlers
@app.on_message(filters.private & filters.chat_type.private)
async def _on_message(client, message):
    await handlers.on_message(client, message)

@app.on_callback_query()
async def _on_callback(client, callback_query):
    await handlers.on_callback_query(client, callback_query)

@app.on_message(filters.command("start") & filters.private)
async def _start(client, message):
    await handlers.cmd_start(client, message)

@app.on_message(filters.command("search") & filters.private)
async def _search(client, message):
    await handlers.cmd_search(client, message)

# Utility: delete after X minutes tasks created as background tasks
async def deliver_episode(client, to_chat_id: int, episode_doc: dict, auto_delete: int = 0):
    """
    This wrapper is exposed by handlers module but implemented here so it has Client context.
    episode_doc must include 'file_id' and optional 'caption' and 'file_type' (document, audio, voice, etc.)
    """
    # called by handlers; we route to this module-level function at runtime
    pass

# We monkey-patch the deliver function into handlers for simplicity
# Implementation of deliver_episode uses Client context. We'll define here and attach to handlers.
async def _deliver_episode_impl(client, to_chat_id: int, ep: dict, auto_delete: int = 0):
    caption = ep.get("caption") or f"{ep.get('title','Episode')} — {ep.get('episode_number')}"
    file_id = ep.get("file_id")
    if not file_id:
        await client.send_message(to_chat_id, "Episode missing file.")
        return
    # Detect type (document or audio) from ep metadata
    ftype = ep.get("file_type", "document")
    sent = None
    if ftype == "audio":
        sent = await client.send_audio(to_chat_id, file_id, caption=caption)
    else:
        # default document
        sent = await client.send_document(to_chat_id, file_id, caption=caption)
    # Schedule deletion if requested
    if auto_delete and auto_delete > 0:
        async def _deleter(chat_id, msg_id, delay):
            await asyncio.sleep(delay * 60)
            try:
                await client.delete_messages(chat_id, msg_id)
            except Exception:
                pass
        asyncio.create_task(_deleter(to_chat_id, sent.message_id, auto_delete))
    return sent

# Attach
handlers.deliver_episode = _deliver_episode_impl

if __name__ == "__main__":
    print("Starting bot...")
    app.run()
