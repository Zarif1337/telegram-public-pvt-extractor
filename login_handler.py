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

    await client.connect()

    try:
        # Check logged in user account info
        me = await client.get_me()
        user_info = f"{me.first_name or ''} {me.last_name or ''}".strip()
        if me.username:
            user_info += f" (@{me.username})"

        target_peer = None
        user_channels = []

        # Scan ALL account dialogs to locate channel entity
        async for dialog in client.get_dialogs():
            chat = dialog.chat
            if chat.type in ["channel", "supergroup", "group"]:
                user_channels.append(f"• **{chat.title}** (ID: `{chat.id}`)")

            # Match exact ID or matching numerical suffix
            if chat.id == chat_id or str(chat.id).endswith(str(raw_id)):
                target_peer = chat
                break

        # If not found, send account diagnostic message to Telegram
        if not target_peer and isinstance(chat_id, int):
            channel_list_str = "\n".join(user_channels[:15]) if user_channels else "_No channels detected_"
            send_bot_message(
                f"🔍 **Account Diagnostic Report**\n\n"
                f"👤 **Bot is logged into account:** {user_info}\n"
                f"🎯 **Looking for Channel ID:** `{chat_id}` (raw: `{raw_id}`)\n\n"
                f"📋 **Channels found in this account ({len(user_channels)} total):**\n"
                f"{channel_list_str}\n\n"
                f"👉 **Why this happened:** If the channel you want is not listed above, the bot's session is logged into a different account than the one you joined the channel with!"
            )
            return

        if not target_peer:
            target_peer = chat_id

        # Fetch message using target_peer
        msg = await client.get_messages(target_peer, message_id)

        if not msg or msg.empty:
            send_bot_message("❌ **Message Not Found:** The post might be deleted or unavailable.")
            return

        # Direct Copy or Download Fallback
        try:
            await msg.copy(chat_id=int(TARGET_CHAT_ID))
        except Exception:
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
    
