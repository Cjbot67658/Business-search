# bot.py
from pyrogram import Client, filters
import os
import handlers
import db

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH")

if not BOT_TOKEN or not API_ID or not API_HASH:
    raise RuntimeError("BOT_TOKEN, API_ID and API_HASH env vars are required.")

app = Client("shadowfilestorebot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Wire commands/handlers
@app.on_message(filters.private & filters.command("start"))
async def _start(c, m):
    await handlers.cmd_start(c, m)

# Generic message -> pass to handlers
@app.on_message(filters.private & (filters.text | filters.photo))
async def _on_message(c, m):
    await handlers.on_message(c, m)

# Callback queries
@app.on_callback_query()
async def _on_callback(c, cq):
    await handlers.on_callback_query(c, cq)

if __name__ == "__main__":
    print("Starting bot...")
    app.run()
