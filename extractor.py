import os
import sys
import re
import asyncio
import requests
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid, ChannelPrivate, ChatAdminRequired, FloodWait

API_ID_RAW = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")
LINK = os.environ.get("LINK", "")
TARGET_CHAT_ID = os.environ.get("CHAT_ID", "")

print(f"--- EXTRACTION RUNNER LOGS ---")
print(f"LINK received: {LINK}")
print(f"CHAT_ID received: {TARGET_CHAT_ID}")
print(f"BOT_TOKEN present: {bool(BOT_TOKEN)}")
print(f"STRING_SESSION present: {bool(STRING_SESSION)}")

def send_bot_message(text):
    """Sends status updates back to the user via Telegram Bot API."""
    if not BOT_TOKEN or not TARGET_CHAT_ID:
        print(f"[WARNING] Cannot send Telegram message. BOT_TOKEN or CHAT_ID missing! Text: {text}")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TARGET_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"Bot sendMessage status: {res.status_code}")
    except Exception as e:
        print(f"Failed to send bot message: {e}")

def parse_telegram_link(link):
    """Extracts chat identifier and message ID from Telegram links."""
    pvt_match = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    if pvt_match:
        raw_id = pvt_match.group(1)
        chat_id = int("-100" + raw_id)
        message_id = int(pvt_match.group(2))
        return chat_id, raw_id, message_id

    pub_match = re.search(r"t\.me/([^/]+)/(\d+)", link)
    if pub_match:
        raw_chat = pub_match.group(1)
        chat_id = int(raw_chat) if raw_chat.lstrip('-').isdigit() else raw_chat
        message_id = int(pub_match.group(2))
        return chat_id, raw_chat, message_id

    return None, None, None

async def run_extraction():
    if not API_ID_RAW or not API_HASH or not STRING_SESSION:
        send_bot_message("❌ **Extraction Error:** Missing API credentials or session string in GitHub Secrets.")
        return

    chat_id, raw_id, message_id = parse_telegram_link(LINK)
    if not chat_id or not message_id:
        send_bot_message("❌ **Invalid Link Format:** Could not parse message ID from link.")
        return

    client = Client(
        "user_session",
        api_id=int(API_ID_RAW),
        api_hash=API_HASH,
        session_string=STRING_SESSION,
        in_memory=True
    )

    try:
        await client.connect()
    except Exception as conn_err:
        send_bot_message(f"❌ **Connection Error:** Failed to connect to Telegram: {conn_err}")
        return

    try:
        if isinstance(chat_id, int):
            print("Syncing recent dialogs...")
            async for dialog in client.get_dialogs(limit=100):
                pass

        msg = await client.get_messages(chat_id, message_id)

        if not msg or msg.empty:
            send_bot_message("❌ **Message Not Found:** The post might be deleted or unavailable.")
            return

        print("Message fetched successfully. Sending content...")

        # Copy directly to user chat
        try:
            await msg.copy(chat_id=int(TARGET_CHAT_ID))
            print("Successfully copied message via user session.")
            send_bot_message("✅ **Extraction Complete!** Check your chat above.")
        except Exception as copy_err:
            print(f"Direct copy failed: {copy_err}. Downloading media...")
            caption = msg.caption or msg.text or ""
            if msg.media:
                file_path = await client.download_media(msg)
                if file_path:
                    if msg.photo:
                        await client.send_photo(int(TARGET_CHAT_ID), photo=file_path, caption=caption)
                    elif msg.video:
                        await client.send_video(int(TARGET_CHAT_ID), video=file_path, caption=caption)
                    elif msg.document:
                        await client.send_document(int(TARGET_CHAT_ID), document=file_path, caption=caption)
                    elif msg.audio:
                        await client.send_audio(int(TARGET_CHAT_ID), audio=file_path, caption=caption)
                    elif msg.voice:
                        await client.send_voice(int(TARGET_CHAT_ID), voice=file_path, caption=caption)
                    else:
                        await client.send_document(int(TARGET_CHAT_ID), document=file_path, caption=caption)
                    
                    if os.path.exists(file_path):
                        os.remove(file_path)
            elif caption:
                await client.send_message(int(TARGET_CHAT_ID), text=caption)
            
            send_bot_message("✅ **Extraction Complete!**")

    except FloodWait as fw:
        send_bot_message(f"⏳ **Rate Limited:** Telegram requested a wait of `{fw.value}` seconds.")
    except PeerIdInvalid:
        send_bot_message("❌ **Peer Invalid:** Make sure your logged-in account has joined this private channel!")
    except ChannelPrivate:
        send_bot_message("❌ **Channel Private:** Your account does not have permission to view posts here.")
    except Exception as e:
        send_bot_message(f"❌ **Extraction Error:** `{str(e)}`")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_extraction())
