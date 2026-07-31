import os
import sys
import asyncio
import base64
import struct
import requests
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

# Safely load environment variables
API_ID_RAW = os.environ.get("API_ID", "")
API_HASH = os.environ.get("API_HASH", "")

WORKER_URL = os.environ.get("WORKER_URL", "").strip().rstrip("/")
if WORKER_URL and not WORKER_URL.startswith("http://") and not WORKER_URL.startswith("https://"):
    WORKER_URL = "https://" + WORKER_URL

WORKER_SECRET = os.environ.get("WORKER_SECRET", "")

ACTION = os.environ.get("ACTION")
USER_ID = os.environ.get("USER_ID")
PHONE = os.environ.get("PHONE")
CODE = os.environ.get("CODE")
PASSWORD = os.environ.get("PASSWORD")
PHONE_CODE_HASH = os.environ.get("PHONE_CODE_HASH")
TEMP_SESSION = os.environ.get("TEMP_SESSION")

def send_callback(data):
    """Sends status updates back to Cloudflare Worker."""
    if not WORKER_URL or not WORKER_SECRET:
        print("ERROR: WORKER_URL or WORKER_SECRET missing in GitHub Secrets!")
        return
    headers = {"X-Secret-Key": WORKER_SECRET, "Content-Type": "application/json"}
    payload = {"user_id": USER_ID, **data}
    try:
        requests.post(f"{WORKER_URL}/callback/login", json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"Failed to post callback to worker: {e}")

async def safe_export_session(client: Client) -> str:
    """Safely exports session string by correctly calling Pyrogram's async storage methods."""
    s = client.storage
    
    # Pyrogram storage properties are async methods that take values to set internal state
    try:
        if await s.user_id() is None:
            await s.user_id(0)
    except Exception:
        pass
        
    try:
        if await s.is_bot() is None:
            await s.is_bot(False)
    except Exception:
        pass

    try:
        if await s.test_mode() is None:
            await s.test_mode(False)
    except Exception:
        pass

    # Method 1: Try native Pyrogram export
    try:
        return await client.export_session_string()
    except Exception:
        # Method 2: Fail-safe manual binary packing to guarantee no struct.error
        dc_id = (await s.dc_id()) or 2
        test_mode = bool(await s.test_mode())
        auth_key = await s.auth_key()
        user_id = (await s.user_id()) or 0
        is_bot = bool(await s.is_bot())
        
        packed = struct.pack(
            s.STRING_FORMAT,
            dc_id,
            test_mode,
            auth_key,
            user_id,
            is_bot
        )
        return base64.urlsafe_b64encode(packed).decode().rstrip("=")

async def handle_send_code():
    if not API_ID_RAW or not API_HASH:
        send_callback({"action": "login_failed", "error": "TELEGRAM_API_ID or TELEGRAM_API_HASH is missing in GitHub Secrets."})
        return

    client = Client("temp_session", api_id=int(API_ID_RAW), api_hash=API_HASH, in_memory=True)
    await client.connect()
    try:
        sent_code = await client.send_code(PHONE)
        temp_session = await safe_export_session(client)
        
        send_callback({
            "action": "code_sent",
            "phone_code_hash": sent_code.phone_code_hash,
            "temp_session": temp_session
        })
    except Exception as e:
        send_callback({"action": "login_failed", "error": f"Telegram API Error: {str(e)}"})
    finally:
        await client.disconnect()

async def handle_verify_code():
    client = Client("temp_session", api_id=int(API_ID_RAW), api_hash=API_HASH, session_string=TEMP_SESSION, in_memory=True)
    await client.connect()
    try:
        await client.sign_in(PHONE, PHONE_CODE_HASH, CODE)
        final_session = await safe_export_session(client)
        send_callback({"action": "login_success", "session": final_session})
    except SessionPasswordNeeded:
        temp_session = await safe_export_session(client)
        send_callback({"action": "need_2fa", "temp_session": temp_session})
    except (PhoneCodeInvalid, PhoneCodeExpired):
        send_callback({"action": "login_failed", "error": "Invalid or expired login code. Please try /login again."})
    except Exception as e:
        send_callback({"action": "login_failed", "error": str(e)})
    finally:
        await client.disconnect()

async def handle_verify_2fa():
    client = Client("temp_session", api_id=int(API_ID_RAW), api_hash=API_HASH, session_string=TEMP_SESSION, in_memory=True)
    await client.connect()
    try:
        await client.check_password(PASSWORD)
        final_session = await safe_export_session(client)
        send_callback({"action": "login_success", "session": final_session})
    except Exception as e:
        send_callback({"action": "login_failed", "error": "Incorrect 2FA password."})
    finally:
        await client.disconnect()

if __name__ == "__main__":
    if ACTION == "send_code":
        asyncio.run(handle_send_code())
    elif ACTION == "verify_code":
        asyncio.run(handle_verify_code())
    elif ACTION == "verify_2fa":
        asyncio.run(handle_verify_2fa())
