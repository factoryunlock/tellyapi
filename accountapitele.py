import os
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

app = Flask(__name__)
CORS(app)

session_path = "/persistent/sessions"

# Ensure the session directory exists
if not os.path.exists(session_path):
    os.makedirs(session_path)

code_hash_store = {}

@app.route("/connect", methods=["POST"])
def connect_telegram():
    data = request.json
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    phone_number = data.get("phone_number")

    if not api_id or not api_hash or not phone_number:
        return jsonify({"error": "Missing required parameters"}), 400

    def run_telethon():
        async def connect_client():
            client = TelegramClient(f"{session_path}/session_{phone_number}", api_id, api_hash)

            try:
                await client.connect()

                if not await client.is_user_authorized():
                    result = await client.send_code_request(phone_number)
                    code_hash_store[phone_number] = result.phone_code_hash
                    return {"status": "code_sent"}

                return {"status": "already_connected"}

            except Exception as e:
                print(f"Error in /connect: {e}")
                return {"error": str(e)}

            finally:
                await client.disconnect()

        return asyncio.run(connect_client())

    result = run_telethon()
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result), 200


@app.route("/verify", methods=["POST"])
def verify_code():
    data = request.json
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    phone_number = data.get("phone_number")
    code = data.get("code")
    password = data.get("password", None)

    phone_code_hash = code_hash_store.get(phone_number)

    if not api_id or not api_hash or not phone_number or not code or not phone_code_hash:
        return jsonify({"error": "Missing required parameters or phone_code_hash"}), 400

    def run_telethon():
        async def verify_client():
            client = TelegramClient(f"{session_path}/session_{phone_number}", api_id, api_hash)

            try:
                await client.connect()

                if not await client.is_user_authorized():
                    try:
                        await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
                    except SessionPasswordNeededError:
                        if not password:
                            return {"status": "password_needed"}
                        await client.sign_in(password=password)

                return {"status": "verified"}

            except Exception as e:
                print(f"Error in /verify: {e}")
                return {"error": str(e)}

            finally:
                await client.disconnect()

        return asyncio.run(verify_client())

    result = run_telethon()
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result), 200


@app.route("/test_connection", methods=["POST"])
def test_connection():
    data = request.json
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    phone_number = data.get("phone_number")

    if not api_id or not api_hash or not phone_number:
        return jsonify({"error": "Missing required parameters"}), 400

    def run_telethon():
        async def test_client():
            client = TelegramClient(f"session_{phone_number}", api_id, api_hash)

            try:
                await client.connect()

                # Fetch the logged-in user's profile
                me = await client.get_me()

                # Send a test message to "Saved Messages"
                message = await client.send_message("me", "This is a test message from your Telegram integration!")

                return {
                    "status": "connected",
                    "username": me.username,
                    "phone": me.phone,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "test_message_status": f"Message sent: {message.text}"
                }

            except Exception as e:
                print(f"Error in /test_connection: {e}")
                return {"error": str(e)}

            finally:
                await client.disconnect()

        return asyncio.run(test_client())

    result = run_telethon()
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result), 200


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)
