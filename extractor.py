import os
import re
import asyncio
from pyrogram import Client

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = int(os.environ["CHAT_ID"])
LINK = os.environ["LINK"]
STRING_SESSION = os.environ["STRING_SESSION"]

def parse_telegram_link(link: str):
    """Extracts channel ID and message ID from standard public or private links."""
    private_match = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    public_match = re.search(r"t\.me/([^/]+)/(\d+)", link)

    if private_match:
        # Private channels use -100 prefix in Telegram API
        channel_id = int("-100" + private_match.group(1))
        msg_id = int(private_match.group(2))
        return channel_id, msg_id
    elif public_match:
        channel_id = public_match.group(1)
        msg_id = int(public_match.group(2))
        return channel_id, msg_id
    
    return None, None

async def main():
    channel, msg_id = parse_telegram_link(LINK)
    if not channel or not msg_id:
        print("Invalid message link provided.")
        return

    # User client (for accessing private/restricted channels)
    app = Client(
        "user_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=STRING_SESSION,
        in_memory=True
    )

    # Bot client (for delivering downloaded media directly to chat)
    bot = Client(
        "bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )

    await app.start()
    await bot.start()

    try:
        # Fetch target message via user session
        message = await app.get_messages(channel, msg_id)

        if not message:
            await bot.send_message(CHAT_ID, "❌ Message not found or access denied.")
            return

        if message.text:
            await bot.send_message(CHAT_ID, message.text)
        elif message.media:
            caption = message.caption or ""
            
            # Download file locally to runner
            file_path = await app.download_media(message)

            # Upload media back to user using Bot account
            if message.photo:
                await bot.send_photo(CHAT_ID, file_path, caption=caption)
            elif message.video:
                await bot.send_video(CHAT_ID, file_path, caption=caption)
            elif message.document:
                await bot.send_document(CHAT_ID, file_path, caption=caption)
            elif message.audio:
                await bot.send_audio(CHAT_ID, file_path, caption=caption)

            # Remove temp file to keep runner clean
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

        await bot.send_message(CHAT_ID, "✅ **Extraction complete!**")

    except Exception as e:
        await bot.send_message(CHAT_ID, f"❌ **Error during extraction:** `{str(e)}`")
    finally:
        await app.stop()
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())