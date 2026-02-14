# handlers.py
# All bot handlers (callbacks, message flows). Uses db.py helpers.
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import re
import db
import os

OWNER_ID = int(os.environ["OWNER_ID"])
DB_CHANNEL_ID = int(os.environ["DB_CHANNEL_ID"])  # channel where bot posts stories

def make_kb(button_rows):
    rows = []
    for row in button_rows:
        r = []
        for text, cb in row:
            r.append(InlineKeyboardButton(text, callback_data=cb))
        rows.append(r)
    return InlineKeyboardMarkup(rows)

# Top start menu
async def cmd_start(client, message):
    kb = [
        [("Explore All", "explore:open"), ("Search", "search:open")],
        [("Request & Comment", "request:open")]
    ]
    await message.reply_text("Welcome! Choose an option:", reply_markup=make_kb(kb))

# Callback router
async def on_callback_query(client, cbq):
    data = cbq.data or ""
    uid = cbq.from_user.id

    # Explore open -> list categories
    if data == "explore:open":
        cats = db.get_categories()
        kb = []
        for c in cats:
            name = c.get("name", c["_id"].capitalize())
            cnt = c.get("count", 0)
            kb.append([(f"{name} ({cnt})", f"explore:cat:{c['_id']}")])
        kb.append([("⟵ Back", "start:menu")])
        await cbq.message.edit_text("Choose a category:", reply_markup=make_kb(kb))
        await cbq.answer()
        return

    if data.startswith("explore:cat:"):
        slug = data.split(":")[-1]
        # stream stories (paginated could be added)
        docs = db.stories.find({"category": slug}).sort("created_at", -1).limit(50)
        await cbq.message.delete()  # remove the menu message to avoid clutter
        for s in docs:
            kb = [[("Listen", f"listen:{s['vision_id']}"), ("Back","explore:open")]]
            await client.send_photo(cbq.from_user.id, s["photo_file_id"],
                                    caption=f"{s['vision_id']} - {s['title']}\n\n{s.get('description','')}",
                                    reply_markup=make_kb(kb))
        await cbq.answer()
        return

    if data.startswith("listen:"):
        vision = data.split(":")[1]
        # set user state to listen flow
        db.set_state(cbq.from_user.id, {"action":"listen", "vision_id": vision})
        await cbq.message.reply_text("Which episode? Use format Ep1 or Ep1-10 or Ep1-100")
        await cbq.answer()
        return

    if data == "search:open":
        db.set_state(uid, {"action":"search"})
        await cbq.message.reply_text("Please send story name in CAPITAL letters (exact).")
        await cbq.answer()
        return

    if data == "request:open":
        db.set_state(uid, {"action":"request"})
        await cbq.message.reply_text("Please write your message for owner/admin. It will be forwarded.")
        await cbq.answer()
        return

    # admin: category command UI (owner/admin only)
    if data.startswith("admin:cat:"):
        # format admin:cat:fantasy:addnew etc
        parts = data.split(":")
        # e.g. admin:cat:fantasy -> show add/update
        if len(parts) >= 3:
            slug = parts[2]
            if not db.is_admin(uid) and uid != OWNER_ID:
                await cbq.answer("You are not authorized.", show_alert=True)
                return
            kb = [[("+AddNEW", f"admin:addnew:{slug}"), ("+UpdateOLD", f"admin:update:{slug}")],
                  [("⟵ Back", "start:menu")]]
            await cbq.message.edit_text(f"Admin options for {slug}", reply_markup=make_kb(kb))
            await cbq.answer()
            return

    # admin add NEW flow trigger
    if data.startswith("admin:addnew:"):
        slug = data.split(":")[-1]
        db.set_state(uid, {"action":"admin_add", "category": slug, "step":"await_title", "tmp":{}})
        await cbq.message.reply_text("Please send story title (e.g. YODDHA).")
        await cbq.answer()
        return

    # admin update OLD trigger
    if data.startswith("admin:update:"):
        slug = data.split(":")[-1]
        db.set_state(uid, {"action":"admin_update", "category": slug, "step":"await_vision"})
        await cbq.message.reply_text("Please send vision count number (e.g. fa01).")
        await cbq.answer()
        return

    # back handlers
    if data == "start:menu":
        await cbq.message.edit_text("Welcome! Choose an option:", reply_markup=make_kb([
            [("Explore All", "explore:open"), ("Search", "search:open")],
            [("Request & Comment", "request:open")]
        ]))
        await cbq.answer()
        return

    # admin episode buttons dynamic (like admin:addep:fa01:1)
    if data.startswith("admin:addep:"):
        # format admin:addep:vision:ep_no or admin:addeprange:vision:start:end
        parts = data.split(":")
        # admin:addep:fa01:1
        if len(parts) == 4:
            vision = parts[2]
            epno = int(parts[3])
            db.set_state(uid, {"action":"admin_add_ep", "vision":vision, "start_ep":epno, "step":"await_link", "range":False})
            await cbq.message.reply_text(f"Send redirect link for Ep{epno}.")
            await cbq.answer()
            return
        # admin:adderange:fa01:1:50
    if data.startswith("admin:adderange:"):
        parts = data.split(":")
        if len(parts) == 5:
            vision = parts[2]
            start = int(parts[3])
            end = int(parts[4])
            db.set_state(uid, {"action":"admin_add_ep", "vision":vision, "start_ep":start, "end_ep":end, "step":"await_shortlink", "range":True})
            await cbq.message.reply_text(f"Send shortlink that covers Ep{start}-Ep{end}.")
            await cbq.answer()
            return

    await cbq.answer()

# Text message handler for states & search & admin flows
async def on_message(client, message):
    uid = message.from_user.id
    txt = (message.text or "").strip()
    st = db.get_state(uid) or {}

    # Utility: message id compatibility
    msg_id = getattr(message, "message_id", None) or getattr(message, "id", None)

    # If listening flow
    if st.get("action") == "listen":
        vision = st.get("vision_id")
        if not vision:
            db.clear_state(uid)
            await message.reply_text("Session expired. Try again.")
            return
        if not re.match(r"^Ep\d+(-\d+)?$", txt):
            await message.reply_text("Wrong format. Use Ep1 or Ep1-10 (case sensitive Ep).")
            return
        # remove Ep prefix and parse
        part = txt[2:]
        if "-" in part:
            start_s, end_s = part.split("-")
            start = int(start_s); end = int(end_s)
            doc = db.find_shortlink_for_range(vision, start, end)
            if doc:
                await message.reply_text(f"Shortlink: {doc['link']}")
            else:
                await message.reply_text("No shortlink found for that range. Sorry.")
        else:
            ep_no = int(part)
            doc = db.find_episode_single(vision, ep_no)
            if doc:
                await message.reply_text(f"Ep{ep_no} link: {doc['link']}")
            else:
                await message.reply_text("Episode not found.")
        db.clear_state(uid)
        return

    # Search flow
    if st.get("action") == "search":
        # User asked to send story name in CAPITAL letters
        query = txt.strip()
        if not query or query != query.upper():
            await message.reply_text("Please send story name in CAPITAL letters only.")
            return
        results = db.search_stories_text(query, limit=10)
        if not results:
            await message.reply_text("This story is not available. Use Request & Comment to ask owner.")
        else:
            for r in results:
                kb = [[("Listen", f"listen:{r['vision_id']}")], [("⟵ Back", "start:menu")]]
                await client.send_photo(uid, r.get("photo_file_id"), caption=f"{r['vision_id']} - {r.get('title')}\n\n{r.get('description','')}", reply_markup=make_kb(kb))
        db.clear_state(uid)
        return

    # Request & Comment flow
    if st.get("action") == "request":
        # forward message content to owner/admins channel or to owner id
        doc = {"from_user": uid, "text": txt, "created_at":__import__("datetime").datetime.utcnow()}
        db.requests.insert_one(doc)
        # forward to owner/admin via DM
        owner_id = db.get_admins_doc().get("owner_id") or OWNER_ID
        try:
            # forward original message if possible
            await client.send_message(owner_id, f"Request from @{message.from_user.username or message.from_user.first_name} ({uid}):\n\n{txt}")
            await message.reply_text("Your message has been forwarded to the owner/admin. Thank you.")
        except Exception:
            await message.reply_text("Couldn't forward. But your request is saved.")
        db.clear_state(uid)
        return

    # Admin add story flow (state machine)
    if st.get("action") == "admin_add":
        if not db.is_admin(uid) and uid != OWNER_ID:
            db.clear_state(uid)
            await message.reply_text("You are not authorized to perform admin actions.")
            return
        step = st.get("step")
        tmp = st.get("tmp", {})
        cat = st.get("category")
        if step == "await_title":
            # accept title
            tmp["title"] = txt
            st["tmp"] = tmp
            st["step"] = "await_photo"
            db.set_state(uid, st)
            await message.reply_text("Now send story photo (as photo, not file).")
            return
        if step == "await_photo" and message.photo:
            # get largest photo file_id
            file_id = message.photo[-1].file_id
            tmp["photo_file_id"] = file_id
            st["tmp"] = tmp
            st["step"] = "await_description"
            db.set_state(uid, st)
            await message.reply_text("Photo set successfully. Now send story description.")
            return
        if step == "await_description":
            tmp["description"] = txt
            # finalize add
            created_by = uid
            story = db.add_story(cat, tmp["title"], tmp["photo_file_id"], tmp["description"], created_by)
            # post to DB channel
            caption = f"{story['vision_id']} - {story['title']}\n\n{story['description']}"
            try:
                await client.send_photo(DB_CHANNEL_ID, story['photo_file_id'], caption=caption)
            except Exception as e:
                # still continue
                print("Failed posting to DB channel:", e)
            db.clear_state(uid)
            # send next options (Add EP)
            kb = [
                [("+AddEP1", f"admin:addep:{story['vision_id']}:1"),
                 ("+AddEP1-10", f"admin:adderange:{story['vision_id']}:1:10")],
                [("+AddEP1-50", f"admin:adderange:{story['vision_id']}:1:50"),
                 ("+AddEP1-100", f"admin:adderange:{story['vision_id']}:1:100")]
            ]
            await message.reply_text(f"Congrats — Story added: {story['vision_id']} ({story['title']}). Choose episode option:", reply_markup=make_kb(kb))
            return
        # fallback
        await message.reply_text("Please follow the steps. Send title / photo / description as prompted.")
        return

    # Admin add episode link flow
    if st.get("action") == "admin_add_ep" and st.get("step") in ("await_link", "await_shortlink"):
        if not db.is_admin(uid) and uid != OWNER_ID:
            db.clear_state(uid); await message.reply_text("Not authorized."); return
        if st.get("range"):
            # expecting shortlink for a range
            link = txt
            vision = st.get("vision")
            start = st.get("start_ep"); end = st.get("end_ep")
            db.add_episode(vision, ep_no=None, link=link, short=True, ep_no_start=start, ep_no_end=end)
            db.clear_state(uid)
            await message.reply_text(f"Shortlink saved for Ep{start}-Ep{end} successfully.")
            return
        else:
            # single ep
            if not txt.startswith("http"):
                await message.reply_text("Please send a valid URL starting with http/https.")
                return
            vision = st.get("vision")
            ep = st.get("start_ep")
            db.add_episode(vision, ep_no=ep, link=txt, short=False)
            db.clear_state(uid)
            # reply and show next ep button (increment)
            next_ep = ep + 1
            kb = [[(f"+AddEP{next_ep}", f"admin:addep:{vision}:{next_ep}"),("⟵ Back","start:menu")]]
            await message.reply_text(f"Ep{ep} link saved successfully. Add next?", reply_markup=make_kb(kb))
            return

    # default: if no state matched, allow commands like /ping or owner admin commands
    if txt.startswith("/"):
        cmd = txt.split()[0].lstrip("/").lower()
        # Admin category command creation: only owner/admin
        if cmd in ("fantasy","love","sifi","sci_fi","mythology","thriller"):
            if not db.is_admin(uid) and uid != OWNER_ID:
                await message.reply_text("Not authorized to use this command.")
                return
            # show admin menu for this category
            kb = [[("+AddNEW", f"admin:addnew:{cmd}"), ("+UpdateOLD", f"admin:update:{cmd}")]]
            await message.reply_text(f"Admin options for {cmd}:", reply_markup=make_kb(kb))
            return
        if cmd == "ping":
            await message.reply_text("Pong ✅")
            return

    # If nothing matched:
    await message.reply_text("I didn't understand that. Use the buttons or /start to go to main menu.")
