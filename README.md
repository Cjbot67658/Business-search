Fill .env using .env.example.
Upload your files to a private Telegram channel and note their file_id (e.g., copy file_id from message.document.file_id via a small helper bot or from Pyrogram).
Seed DB: python db_seed.py (then update file_ids in DB with real ones).
Run locally: python bot.py or build Docker and run.
Deploy to Koyeb, Railway, or Render etc.
