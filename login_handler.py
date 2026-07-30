import os
import sys
import re
import asyncio
import requests
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid, ChannelPrivate, ChatAdminRequired

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
    """Extracts chat identifier and message ID from Telegram links."""
    # Private link: t.me/c/3981274773/3 -> -1003981274773
    pvt_match = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    if pvt_match:
        chat_id = int("-100" + pvt_match.group(1))
        message_id = int(pvt_match.group(2))
        return chat_id, message_id

    # Public link: t.me/channel_username/3
    pub_match = re.search(r"t\.me/([^/]+)/(\d+)", link)
    if pub_match:
        raw_chat = pub_match.group(1)
        chat_id = int(raw_chat) if raw_chat.lstrip('-').isdigit() else raw_chat
        message_id = int(pub_match.group(2))
        return chat_id, message_id

    return None, None

async def run_extraction():
    if not API_ID_RAW or not API_HASH or not STRING_SESSION:
        send_bot_message("❌ **Extraction Error:** Missing API credentials or session string.")
        return

    chat_id, message_id = parse_telegram_link(LINK)
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

    await client.connect()

    try:
        target_peer = chat_id

        # For private integer channel IDs, scan dialogs to find the chat & cache its Access Hash
        if isinstance(chat_id, int):
            found = False
            print(f"Scanning account dialogs for channel ID: {chat_id}...")
            async for dialog in client.get_dialogs():
                if dialog.chat.id == chat_id:
                    target_peer = dialog.chat
                    found = True
                    break
            
            if not found:
                send_bot_message(
                    f"❌ **Access Denied:** Your logged-in Telegram account is **NOT a member** of channel ID `{chat_id}`.\n\n"
                    "👉 **How to Fix:** Open Telegram on your phone, join the private channel using its invite link, and try sending the link again!"
                )
                return

        # Fetch message using resolved chat entity
        msg = await client.get_messages(target_peer, message_id)

        if not msg or msg.empty:
            send_bot_message("❌ **Message Not Found:** The post might be deleted or restricted.")
            return

        # Forward/copy message back to user chat
        await client.copy_message(
            chat_id=int(TARGET_CHAT_ID),
            from_chat_id=chat_id,
            message_id=message_id
        )

    except PeerIdInvalid:
        send_bot_message("❌ **Peer Invalid:** Unable to resolve channel. Make sure your account has joined the private channel!")
    except ChannelPrivate:
        send_bot_message("❌ **Channel Private:** Account does not have permission to view posts here.")
    except Exception as e:
        send_bot_message(f"❌ **Extraction Error:** {str(e)}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_extraction())
