import os
import sys
import re
import asyncio
import traceback
from pyrogram import Client
from pyrogram.errors import (
    PeerIdInvalid, 
    ChannelPrivate, 
    FloodWait, 
    UsernameInvalid, 
    UsernameNotOccupied, 
    UserAlreadyParticipant,
    ChatForwardsRestricted
)

API_ID_RAW = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")
LINK = os.environ.get("LINK", "")
TARGET_CHAT_ID = os.environ.get("CHAT_ID", "")

print("--- EXTRACTION RUNNER LOGS ---", flush=True)
print(f"LINK received: {LINK}", flush=True)
print(f"CHAT_ID received: {TARGET_CHAT_ID}", flush=True)

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
        if raw_chat.lstrip('-').isdigit():
            chat_id = int(raw_chat)
        else:
            chat_id = f"@{raw_chat}" if not raw_chat.startswith("@") else raw_chat
        message_id = int(pub_match.group(2))
        return chat_id, raw_chat, message_id

    return None, None, None

async def run_extraction():
    if not API_ID_RAW or not API_HASH or not STRING_SESSION or not BOT_TOKEN:
        print("❌ Missing required environment variables!", flush=True)
        return

    chat_id, raw_id, message_id = parse_telegram_link(LINK)
    if not chat_id or not message_id:
        print("❌ Invalid link format!", flush=True)
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
        target_peer = chat_id

        # --- PUBLIC CHANNEL HANDLING ---
        if isinstance(chat_id, str) and chat_id.startswith("@"):
            print(f"Handling public channel username: {chat_id}...", flush=True)
            
            try:
                await user_client.join_chat(chat_id)
                print(f"✅ Joined/Verified membership in {chat_id}", flush=True)
            except UserAlreadyParticipant:
                print(f"User is already a participant of {chat_id}", flush=True)
            except Exception as e:
                print(f"Join chat notice: {e}", flush=True)

            try:
                # Store full Chat Object entity directly (preserves access hash)
                target_peer = await user_client.get_chat(chat_id)
                print(f"✅ Resolved entity: '{target_peer.title}'", flush=True)
            except (UsernameInvalid, UsernameNotOccupied):
                await bot_client.send_message(target_chat, f"❌ **Invalid Username:** Channel `{chat_id}` does not exist.")
                return
            except Exception as e:
                print(f"Warning resolving chat entity: {e}", flush=True)
                target_peer = chat_id

        # --- PRIVATE CHANNEL HANDLING ---
        elif isinstance(chat_id, int):
            found_channel = False
            print(f"Scanning user dialogs for channel raw ID: {raw_id}...", flush=True)
            async for dialog in user_client.get_dialogs():
                chat = dialog.chat
                if chat.id == chat_id or str(chat.id).endswith(str(raw_id)):
                    target_peer = chat
                    found_channel = True
                    print(f"✅ Found target channel in dialogs: '{chat.title}' (ID: {chat.id})", flush=True)
                    break

            if not found_channel:
                print(f"⚠️ Channel {chat_id} not found in user account dialogs!", flush=True)
                await bot_client.send_message(
                    target_chat, 
                    "❌ **Channel Not Found:** Make sure your logged-in user account has joined this private channel."
                )
                return

        print(f"Fetching message {message_id}...", flush=True)
        msg = await asyncio.wait_for(user_client.get_messages(target_peer, message_id), timeout=30)

        if not msg or msg.empty:
            print("❌ Message empty or not found.", flush=True)
            await bot_client.send_message(target_chat, "❌ **Message Not Found:** Post might be deleted or unavailable.")
            return

        print(f"✅ Message {message_id} fetched successfully!", flush=True)
        caption = msg.caption or msg.text or ""

        if msg.media:
            print("Downloading media to cloud runner...", flush=True)
            file_path = await asyncio.wait_for(user_client.download_media(msg), timeout=600)
            
            if file_path and os.path.exists(file_path):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"Downloaded size: {file_size_mb:.2f} MB. Uploading via Bot MTProto engine...", flush=True)

                if msg.photo:
                    await bot_client.send_photo(target_chat, photo=file_path, caption=caption)
                elif msg.video:
                    await bot_client.send_video(target_chat, video=file_path, caption=caption)
                elif msg.audio:
                    await bot_client.send_audio(target_chat, audio=file_path, caption=caption)
                else:
                    await bot_client.send_document(target_chat, document=file_path, caption=caption)

                print("Upload completed successfully!", flush=True)

                if os.path.exists(file_path):
                    os.remove(file_path)
            else:
                print("❌ Download failed or file path invalid.", flush=True)
                await bot_client.send_message(target_chat, "❌ **Download Error:** Could not save media file.")
        elif caption:
            await bot_client.send_message(target_chat, text=caption)

    except ChatForwardsRestricted:
        await bot_client.send_message(target_chat, "🚫 **Content Protected:** Saving/forwarding is restricted in this channel by the owner.")
    except asyncio.TimeoutError:
        print("❌ Operation timed out!", flush=True)
        await bot_client.send_message(target_chat, "⏱️ **Timeout Error:** Telegram took too long to send the requested file.")
    except FloodWait as fw:
        await bot_client.send_message(target_chat, f"⏳ **Rate Limited:** Telegram requested a wait of `{fw.value}` seconds.")
    except PeerIdInvalid:
        await bot_client.send_message(target_chat, "❌ **Peer Invalid:** Unable to resolve this chat. Make sure the channel exists and is accessible.")
    except ChannelPrivate:
        await bot_client.send_message(target_chat, "❌ **Channel Private:** Your account does not have permission to view posts here.")
    except BaseException as e:
        err_detail = str(e) or type(e).__name__
        print(f"Extraction failed: {err_detail}\n{traceback.format_exc()}", flush=True)
        try:
            await bot_client.send_message(target_chat, f"❌ **Extraction Error:** `{err_detail}`")
        except Exception:
            pass
    finally:
        await user_client.stop()
        await bot_client.stop()

if __name__ == "__main__":
    asyncio.run(run_extraction())
