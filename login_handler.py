import os
import sys
import asyncio
import requests
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
WORKER_URL = os.environ["WORKER_URL"].rstrip("/")
WORKER_SECRET = os.environ["WORKER_SECRET"]

ACTION = os.environ.get("ACTION")
USER_ID = os.environ.get("USER_ID")
PHONE = os.environ.get("PHONE")
CODE = os.environ.get("CODE")
PASSWORD = os.environ.get("PASSWORD")
PHONE_CODE_HASH = os.environ.get("PHONE_CODE_HASH")
TEMP_SESSION = os.environ.get("TEMP_SESSION")

def send_callback(data):
    headers = {"X-Secret-Key": WORKER_SECRET, "Content-Type": "application/json"}
    payload = {"user_id": USER_ID, **data}
    requests.post(f"{WORKER_URL}/callback/login", json=payload, headers=headers)

async def handle_send_code():
    client = Client("temp_session", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    await client.connect()
    try:
        sent_code = await client.send_code(PHONE)
        temp_session = await client.export_session_string()
        send_callback({
            "action": "code_sent",
            "phone_code_hash": sent_code.phone_code_hash,
            "temp_session": temp_session
        })
    except Exception as e:
        send_callback({"action": "login_failed", "error": str(e)})
    finally:
        await client.disconnect()

async def handle_verify_code():
    client = Client("temp_session", api_id=API_ID, api_hash=API_HASH, session_string=TEMP_SESSION, in_memory=True)
    await client.connect()
    try:
        await client.sign_in(PHONE, PHONE_CODE_HASH, CODE)
        final_session = await client.export_session_string()
        send_callback({"action": "login_success", "session": final_session})
    except SessionPasswordNeeded:
        temp_session = await client.export_session_string()
        send_callback({"action": "need_2fa", "temp_session": temp_session})
    except (PhoneCodeInvalid, PhoneCodeExpired) as e:
        send_callback({"action": "login_failed", "error": "Invalid or expired login code."})
    except Exception as e:
        send_callback({"action": "login_failed", "error": str(e)})
    finally:
        await client.disconnect()

async def handle_verify_2fa():
    client = Client("temp_session", api_id=API_ID, api_hash=API_HASH, session_string=TEMP_SESSION, in_memory=True)
    await client.connect()
    try:
        await client.check_password(PASSWORD)
        final_session = await client.export_session_string()
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
