import os
import sys
import re
import asyncio
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid, ChannelPrivate, FloodWait

API_ID_RAW = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")
LINK = os.environ.get("LINK", "")
TARGET_CHAT_ID = os.environ.get("CHAT_ID", "")

print("--- EXTRACTION RUNNER LOGS ---")
print(f"LINK received: {LINK}")
print(f"CHAT_ID received: {TARGET_CHAT_ID}")

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
    if not API_ID_RAW or not API_HASH or not STRING_SESSION or not BOT_TOKEN:
        print("❌ Missing required environment variables!")
        return

    chat_id, raw_id, message_id = parse_telegram_link(LINK)
    if not chat_id or not message_id:
        print("❌ Invalid link format!")
        return

    api_id = int(API_ID_RAW)
    target_chat = int(TARGET_CHAT_ID)

    user_client = Client(
        "user_session",
        api_id=api_id,
        api_hash=API_HASH,
        session_string=STRING_SESSION,
        in_memory=True
    )

    bot_client = Client(
        "bot_session",
        api_id=api_id,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )

    await user_client.start()
    await bot_client.start()

    try:
        # Smart Search: Scan user dialogs specifically for the target channel ID
        target_peer = chat_id
        found_channel = False

        if isinstance(chat_id, int):
            print(f"Scanning user dialogs for channel raw ID: {raw_id}...")
            async for dialog in user_client.get_dialogs():
                chat = dialog.chat
                # Match exact chat ID or numerical suffix
                if chat.id == chat_id or str(chat.id).endswith(str(raw_id)):
                    target_peer = chat.id
                    found_channel = True
                    print(f"✅ Found target channel in dialogs: '{chat.title}' (ID: {chat.id})")
                    break

        if isinstance(chat_id, int) and not found_channel:
            print(f"⚠️ Channel {chat_id} not found in user account dialogs!")
            await bot_client.send_message(
                target_chat, 
                "❌ **Channel Not Found:** The logged-in account is not a member of this private channel, or your account session needs to be refreshed via `/login`."
            )
            return

        print(f"Fetching private message {message_id} from target peer...")
        msg = await user_client.get_messages(target_peer, message_id)

        if not msg or msg.empty:
            await bot_client.send_message(target_chat, "❌ **Message Not Found:** Post might be deleted or unavailable.")
            return

        caption = msg.caption or msg.text or ""

        if msg.media:
            print("Downloading media to cloud runner...")
            file_path = await user_client.download_media(msg)
            
            if file_path and os.path.exists(file_path):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"Downloaded size: {file_size_mb:.2f} MB. Uploading via Bot MTProto engine...")

                if msg.photo:
                    await bot_client.send_photo(target_chat, photo=file_path, caption=caption)
                elif msg.video:
                    await bot_client.send_video(target_chat, video=file_path, caption=caption)
                elif msg.audio:
                    await bot_client.send_audio(target_chat, audio=file_path, caption=caption)
                else:
                    await bot_client.send_document(target_chat, document=file_path, caption=caption)

                print("Upload completed successfully!")

                if os.path.exists(file_path):
                    os.remove(file_path)
        elif caption:
            await bot_client.send_message(target_chat, text=caption)

    except FloodWait as fw:
        await bot_client.send_message(target_chat, f"⏳ **Rate Limited:** Telegram requested a wait of `{fw.value}` seconds.")
    except PeerIdInvalid:
        await bot_client.send_message(target_chat, "❌ **Peer Invalid:** Make sure your logged-in user account has joined this private channel!")
    except ChannelPrivate:
        await bot_client.send_message(target_chat, "❌ **Channel Private:** Your account does not have permission to view posts here.")
    except Exception as e:
        print(f"Extraction failed: {e}")
        await bot_client.send_message(target_chat, f"❌ **Extraction Error:** `{str(e)}`")
    finally:
        await user_client.stop()
        await bot_client.stop()

if __name__ == "__main__":
    asyncio.run(run_extraction())
