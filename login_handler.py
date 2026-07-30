import os
import sys
import re
import asyncio
import requests
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid, ChannelPrivate, ChatAdminRequired

# Safely load environment variables passed from GitHub Actions
API_ID_RAW = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")
LINK = os.environ.get("LINK", "")
TARGET_CHAT_ID = os.environ.get("CHAT_ID", "")

def send_bot_message(text):
    """Sends status updates back to the user via Telegram Bot API."""
    if not BOT_TOKEN or not TARGET_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TARGET_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send bot message: {e}")

def parse_telegram_link(link):
    """Extracts chat identifier and message ID from public and private Telegram links."""
    # Handles private links: t.me/c/3981274773/3 -> chat_id = -1003981274773
    pvt_match = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    if pvt_match:
        chat_id = int("-100" + pvt_match.group(1))
        message_id = int(pvt_match.group(2))
        return chat_id, message_id

    # Handles public links: t.me/channel_username/3
    pub_match = re.search(r"t\.me/([^/]+)/(\d+)", link)
    if pub_match:
        chat_id = pub_match.group(1)
        message_id = int(pub_match.group(2))
        return chat_id, message_id

    return None, None

async def run_extraction():
    if not API_ID_RAW or not API_HASH or not STRING_SESSION:
        send_bot_message("❌ **Extraction Error:** Missing API credentials or user session string.")
        return

    chat_id, message_id = parse_telegram_link(LINK)
    if not chat_id or not message_id:
        send_bot_message("❌ **Invalid Link Format:** Could not parse message ID from the provided link.")
        return

    # Initialize Pyrogram client with the saved string session
    client = Client(
        "user_session",
        api_id=int(API_ID_RAW),
        api_hash=API_HASH,
        session_string=STRING_SESSION,
        in_memory=True
    )

    await client.connect()

    try:
        # Step 1: Try fetching the message directly
        try:
            msg = await client.get_messages(chat_id, message_id)
        except PeerIdInvalid:
            # Step 2: If peer cache is missing, sync dialogs to load private chats into memory
            print("Peer ID missing in cache. Syncing account dialogs...")
            async for dialog in client.get_dialogs(limit=100):
                pass
            # Step 3: Retry fetching the message after sync
            msg = await client.get_messages(chat_id, message_id)

        if not msg or msg.empty:
            send_bot_message("❌ **Message Not Found:** The post might be deleted or restricted.")
            return

        # Step 4: Forward / copy message to your personal chat with the bot
        await client.copy_message(
            chat_id=int(TARGET_CHAT_ID),
            from_chat_id=chat_id,
            message_id=message_id
        )

    except PeerIdInvalid:
        send_bot_message("❌ **Access Denied:** Your Telegram account is NOT a member of this private channel. Please join the channel first!")
    except ChannelPrivate:
        send_bot_message("❌ **Access Denied:** This channel is private and your account does not have access.")
    except Exception as e:
        send_bot_message(f"❌ **Extraction Error:** {str(e)}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_extraction())
