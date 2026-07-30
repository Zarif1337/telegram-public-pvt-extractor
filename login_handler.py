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
    pvt_match = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    if pvt_match:
        chat_id = int("-100" + pvt_match.group(1))
        message_id = int(pvt_match.group(2))
        return chat_id, message_id

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

        # Scan dialogs to build internal peer cache for private channels
        if isinstance(chat_id, int):
            found_peer = None
            print(f"Scanning account dialogs for channel ID: {chat_id}...")
            async for dialog in client.get_dialogs(limit=500):
                if dialog.chat.id == chat_id:
                    found_peer = dialog.chat
                    break
            
            if found_peer:
                target_peer = found_peer
            else:
                send_bot_message(
                    f"❌ **Channel Not Found in Chat List:** Channel ID `{chat_id}` was not found in your top 500 chats.\n\n"
                    "Please double-check that your logged-in account is currently a member of this channel!"
                )
                return

        # Fetch message using resolved target_peer object
        msg = await client.get_messages(target_peer, message_id)

        if not msg or msg.empty:
            send_bot_message("❌ **Message Not Found:** The post might be deleted or unavailable.")
            return

        # Attempt Method 1: Direct Message Copy
        try:
            await msg.copy(chat_id=int(TARGET_CHAT_ID))
        except Exception as copy_err:
            print(f"Direct copy failed ({copy_err}). Attempting download & re-upload fallback...")
            
            # Attempt Method 2: Restricted Content Bypass (Download & Send)
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

    except PeerIdInvalid:
        send_bot_message("❌ **Peer Invalid:** Unable to resolve channel. Make sure your account is inside the channel!")
    except ChannelPrivate:
        send_bot_message("❌ **Channel Private:** Account does not have permission to view posts here.")
    except Exception as e:
        send_bot_message(f"❌ **Extraction Error:** {str(e)}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_extraction())
        
