import os
import sys
import re
import asyncio
import requests
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid, ChannelPrivate, FloodWait

API_ID_RAW = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")
LINK = os.environ.get("LINK", "")
TARGET_CHAT_ID = os.environ.get("CHAT_ID", "")

print(f"--- EXTRACTION RUNNER LOGS ---")
print(f"LINK received: {LINK}")
print(f"CHAT_ID received: {TARGET_CHAT_ID}")

def send_bot_message(text):
    """Sends text messages directly to the user's chat with the bot."""
    if not BOT_TOKEN or not TARGET_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TARGET_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send bot text message: {e}")

def send_bot_file(file_path, caption="", media_type="document"):
    """Uploads media directly through the Bot API into the bot chat thread."""
    if not BOT_TOKEN or not TARGET_CHAT_ID or not os.path.exists(file_path):
        return
    
    endpoint = "sendDocument"
    field_name = "document"
    
    if media_type == "photo":
        endpoint = "sendPhoto"
        field_name = "photo"
    elif media_type == "video":
        endpoint = "sendVideo"
        field_name = "video"
    elif media_type == "audio":
        endpoint = "sendAudio"
        field_name = "audio"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}"
    
    try:
        print(f"Uploading file via Bot API endpoint: {endpoint}...")
        with open(file_path, "rb") as f:
            files = {field_name: f}
            data = {"chat_id": TARGET_CHAT_ID, "caption": caption}
            res = requests.post(url, data=data, files=files, timeout=300)
            print(f"Bot {endpoint} status code: {res.status_code}")
    except Exception as e:
        print(f"Failed to upload media via Bot API: {e}")

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
        send_bot_message("❌ **Extraction Error:** Missing API credentials or session string.")
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
        send_bot_message(f"❌ **Connection Error:** Failed to connect: {conn_err}")
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

        print("Message fetched successfully. Extracting media/content...")
        caption = msg.caption or msg.text or ""

        if msg.media:
            print("Downloading media to cloud runner...")
            file_path = await client.download_media(msg)
            
            if file_path:
                mtype = "document"
                if msg.photo:
                    mtype = "photo"
                elif msg.video:
                    mtype = "video"
                elif msg.audio:
                    mtype = "audio"

                send_bot_file(file_path, caption=caption, media_type=mtype)
                
                if os.path.exists(file_path):
                    os.remove(file_path)
        elif caption:
            send_bot_message(caption)

    except FloodWait as fw:
        send_bot_message(f"⏳ **Rate Limited:** Please wait `{fw.value}` seconds.")
    except PeerIdInvalid:
        send_bot_message("❌ **Peer Invalid:** Make sure your account has joined this private channel!")
    except ChannelPrivate:
        send_bot_message("❌ **Channel Private:** Your account does not have permission to view posts here.")
    except Exception as e:
        send_bot_message(f"❌ **Extraction Error:** `{str(e)}`")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_extraction())
