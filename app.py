import time
import uuid
import logging
import os
import psutil
import hashlib
import requests
import base64
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from sqlalchemy import create_engine, Column, String, Float, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from cryptography.fernet import Fernet
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
import openai
import anthropic
import google.generativeai as genai
import speech_recognition as sr
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# Initialize core components
app = Flask(__name__)
app.config['SECURE_HEADERS'] = True
CORS(app, origins=os.getenv('ALLOWED_ORIGINS', '*'))
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=False, async_mode='gevent', ping_interval=25, ping_timeout=60)
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Database setup
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'eoth.db')
engine = create_engine(f'sqlite:///{DB_PATH}', pool_size=20, max_overflow=0)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Message(Base):
    __tablename__ = 'messages'
    id = Column(String(36), primary_key=True)
    timestamp = Column(Float, index=True)
    content = Column(Text)
    sender_type = Column(String(10))
    session_id = Column(String(36), index=True)
    platform = Column(String(20))

Base.metadata.create_all(engine)

# Encryption setup
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY.encode())

# Twilio setup
TWILIO_CLIENT = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
TWILIO_PHONE = os.getenv('TWILIO_PHONE_NUMBER')

# AES Vault for message encryption
class Vault:
    def __init__(self, password):
        self.key = hashlib.shake_128(password.encode()).digest(32)

    def encrypt(self, data):
        iv = get_random_bytes(16)
        cipher = AES.new(self.key, AES.MODE_EAX, iv)
        ct, tag = cipher.encrypt_and_digest(data.encode())
        return base64.b64encode(iv + ct + tag).decode()

    def decrypt(self, encrypted_data):
        raw = base64.b64decode(encrypted_data)
        iv, ct, tag = raw[:16], raw[16:-16], raw[-16:]
        cipher = AES.new(self.key, AES.MODE_EAX, iv)
        return cipher.decrypt_and_verify(ct, tag).decode()

vault = Vault(password=os.getenv('VAULT_PASSWORD', 'your-secret-password'))

# KeyVault for API keys
class KeyVault:
    def __init__(self):
        self.keys = {}  # Dict: {provider: [encrypted_keys]}
        self.current_key = {}  # Dict: {provider: index}
        self.usage_counter = {}  # Dict: {provider: count}
        self.MAX_USAGE = 1000

    def add_key(self, provider, encrypted_key):
        if provider not in self.keys:
            self.keys[provider] = []
            self.current_key[provider] = 0
            self.usage_counter[provider] = 0
        self.keys[provider].append(encrypted_key)

    def rotate_key(self, provider):
        if provider in self.keys and self.keys[provider]:
            self.current_key[provider] = (self.current_key[provider] + 1) % len(self.keys[provider])
            self.usage_counter[provider] = 0
            logger.info(f"Rotated {provider} key to index {self.current_key[provider]}")

    def get_key(self, provider):
        if provider not in self.keys or not self.keys[provider]:
            return None
        self.usage_counter[provider] += 1
        if self.usage_counter[provider] >= self.MAX_USAGE:
            self.rotate_key(provider)
        return cipher.decrypt(self.keys[provider][self.current_key[provider]]).decode()

key_vault = KeyVault()
key_vault.add_key("anthropic", cipher.encrypt(b'your-anthropic-api-key'))  # Replace
key_vault.add_key("openai", cipher.encrypt(b'your-openai-api-key'))  # Replace
# Add when obtained:
# key_vault.add_key("grok", cipher.encrypt(b'your-grok-api-key'))
# key_vault.add_key("gemini", cipher.encrypt(b'your-gemini-api-key'))

# Blockchain proof generation
def generate_proof(files=['app.py', 'requirements.txt']):
    try:
        hasher = hashlib.sha256()
        for file in files:
            try:
                with open(file, 'rb') as f:
                    hasher.update(f.read())
            except FileNotFoundError:
                logger.warning(f"{file} not found, skipping.")
        data_hash = hasher.hexdigest()
        response = requests.get("https://mempool.space/api/blocks/tip").json()
        block_height = response[0]['height']
        block_hash = response[0]['id'][:16]
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        proof = f"{data_hash}|{block_height}|{block_hash}|{timestamp}"
        with open('helix.proof', 'w') as f:
            f.write(proof)
        logger.info(f"Generated proof: {proof}")
        return proof
    except Exception as e:
        logger.error(f"Proof generation failed: {e}")
        return None

# AI response with language style
class RateLimitError(Exception):
    pass

def generate_ai_response(user_message, api_key, provider="anthropic", style="formal"):
    style_prompts = {
        "formal": "Respond in a precise, professional tone suitable for formal communication.",
        "poetic": "Craft responses in a poetic, rhythmic style with vivid imagery.",
        "scriptural": "Answer in a biblical, King James-style tone, as if delivering a sermon."
    }
    system_prompt = style_prompts.get(style, "Respond clearly and concisely.")
    try:
        if provider == "anthropic":
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            return response.content[0].text
        elif provider == "openai":
            openai.api_key = api_key
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            return response.choices[0].message.content
        elif provider == "grok":
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                }
            )
            if response.status_code == 429:
                raise RateLimitError("Grok API rate limit exceeded")
            return response.json()["choices"][0]["message"]["content"]
        elif provider == "gemini":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")
            response = model.generate_content(f"{system_prompt}\n\n{user_message}")
            return response.text
        else:
            raise ValueError("Unknown provider")
    except (openai.error.RateLimitError, anthropic.RateLimitError, requests.exceptions.HTTPError) as e:
        raise RateLimitError(f"{provider} API rate limit exceeded")

# Speech recognition
def listen():
    try:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source)
            audio = r.listen(source, timeout=5)
        return r.recognize_google(audio)
    except Exception as e:
        logger.error(f"Speech recognition failed: {e}")
        return None

# WebSocket handling
connected_clients = {}

@socketio.on('connect')
def handle_connect():
    try:
        session_id = str(uuid.uuid4())
        client_info = {
            'session_id': session_id,
            'platform': request.headers.get('User-Agent', 'Unknown'),
            'last_active': time.time()
        }
        connected_clients[request.sid] = client_info
        emit('session_init', {
            'session_id': session_id,
            'system_time': time.time(),
            'heartbeat_interval': 30
        })
        logger.info(f"Client {session_id} connected from {client_info['platform']}")
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        emit('fatal_error', {'code': 'ECONNECT'})

@socketio.on('disconnect')
def handle_disconnect():
    try:
        client = connected_clients.pop(request.sid, None)
        if client:
            logger.info(f"Client {client['session_id']} disconnected")
    except Exception as e:
        logger.error(f"Disconnect error: {e}")

@socketio.on('heartbeat')
def handle_heartbeat(data):
    try:
        if request.sid in connected_clients:
            connected_clients[request.sid]['last_active'] = time.time()
            emit('heartbeat_ack', {'server_time': time.time()})
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")

@socketio.on('message')
def handle_message(data):
    try:
        content = data.get('content', '')
        sender_type = data.get('sender_type', 'user')
        session_id = data.get('session_id')
        style = data.get('style', 'formal')  # Default to formal
        if not content or not session_id:
            emit('error', {'code': 'PAYLOAD_OVERFLOW', 'message': 'Invalid message or session'})
            return
        encrypted_content = vault.encrypt(content)
        with Session() as session:
            user_message = Message(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                content=encrypted_content,
                sender_type=sender_type,
                session_id=session_id,
                platform=connected_clients.get(request.sid, {}).get('platform', 'Unknown')
            )
            session.add(user_message)
            session.commit()
        providers = ["anthropic", "openai"]  # Add "grok", "gemini" when keys available
        for provider in providers:
            try:
                ai_response = generate_ai_response(
                    user_message=content,
                    api_key=key_vault.get_key(provider),
                    provider=provider,
                    style=style
                )
                encrypted_response = vault.encrypt(ai_response)
                ai_msg = Message(
                    id=str(uuid.uuid4()),
                    timestamp=time.time(),
                    content=encrypted_response,
                    sender_type='assistant',
                    session_id=session_id,
                    platform='server'
                )
                break
            except RateLimitError:
                key_vault.rotate_key(provider)
                ai_msg = Message(
                    id=str(uuid.uuid4()),
                    timestamp=time.time(),
                    content=vault.encrypt("System upgrading - retry"),
                    sender_type='system',
                    session_id=session_id,
                    platform='server'
                )
                continue
        with Session() as session:
            session.add(ai_msg)
            session.commit()
        emit('response', {'content': ai_response, 'sender_type': ai_msg.sender_type, 'session_id': session_id}, broadcast=True)
        logger.info(f"Message processed for session {session_id} via {provider}")
    except Exception as e:
        logger.error(f"Message error: {e}")
        emit('error', {'code': 'SESSION_INVALID', 'message': str(e)})

@socketio.on('voice_message')
def handle_voice_message(data):
    try:
        text = listen()
        style = data.get('style', 'formal')
        if text:
            handle_message({
                'content': text,
                'sender_type': 'user',
                'session_id': data.get('session_id'),
                'style': style
            })
        else:
            emit('error', {'code': 'VOICE_FAILED', 'message': 'Could not recognize voice input'})
    except Exception as e:
        logger.error(f"Voice message error: {e}")
        emit('error', {'code': 'VOICE_FAILED', 'message': str(e)})

@socketio.on('sms_message')
def handle_sms_message(data):
    try:
        content = data.get('content', '')
        phone_number = data.get('phone_number')
        style = data.get('style', 'formal')
        session_id = data.get('session_id')
        if not content or not phone_number or not session_id:
            emit('error', {'code': 'INVALID_SMS', 'message': 'Missing content, phone, or session'})
            return
        encrypted_content = vault.encrypt(content)
        with Session() as session:
            user_message = Message(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                content=encrypted_content,
                sender_type='user',
                session_id=session_id,
                platform='sms'
            )
            session.add(user_message)
            session.commit()
        providers = ["anthropic", "openai"]
        for provider in providers:
            try:
                ai_response = generate_ai_response(
                    user_message=content,
                    api_key=key_vault.get_key(provider),
                    provider=provider,
                    style=style
                )
                encrypted_response = vault.encrypt(ai_response)
                ai_msg = Message(
                    id=str(uuid.uuid4()),
                    timestamp=time.time(),
                    content=encrypted_response,
                    sender_type='assistant',
                    session_id=session_id,
                    platform='sms'
                )
                # Send SMS response
                TWILIO_CLIENT.messages.create(
                    body=ai_response,
                    from_=TWILIO_PHONE,
                    to=phone_number
                )
                break
            except RateLimitError:
                key_vault.rotate_key(provider)
                ai_msg = Message(
                    id=str(uuid.uuid4()),
                    timestamp=time.time(),
                    content=vault.encrypt("System upgrading - retry"),
                    sender_type='system',
                    session_id=session_id,
                    platform='sms'
                )
                continue
        with Session() as session:
            session.add(ai_msg)
            session.commit()
        emit('response', {'content': ai_response, 'sender_type': ai_msg.sender_type, 'session_id': session_id}, broadcast=True)
        logger.info(f"SMS processed for session {session_id} via {provider}")
    except Exception as e:
        logger.error(f"SMS error: {e}")
        emit('error', {'code': 'SMS_FAILED', 'message': str(e)})

@app.route('/sms', methods=['POST'])
def sms_webhook():
    try:
        from_number = request.form.get('From')
        body = request.form.get('Body')
        session_id = str(uuid.uuid4())  # New session for each SMS
        encrypted_content = vault.encrypt(body)
        with Session() as session:
            user_message = Message(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                content=encrypted_content,
                sender_type='user',
                session_id=session_id,
                platform='sms'
            )
            session.add(user_message)
            session.commit()
        providers = ["anthropic", "openai"]
        for provider in providers:
            try:
                ai_response = generate_ai_response(
                    user_message=body,
                    api_key=key_vault.get_key(provider),
                    provider=provider,
                    style='formal'  # Default for SMS
                )
                encrypted_response = vault.encrypt(ai_response)
                ai_msg = Message(
                    id=str(uuid.uuid4()),
                    timestamp=time.time(),
                    content=encrypted_response,
                    sender_type='assistant',
                    session_id=session_id,
                    platform='sms'
                )
                TWILIO_CLIENT.messages.create(
                    body=ai_response,
                    from_=TWILIO_PHONE,
                    to=from_number
                )
                break
            except RateLimitError:
                key_vault.rotate_key(provider)
                continue
        with Session() as session:
            session.add(ai_msg)
            session.commit()
        resp = MessagingResponse()
        resp.message("Response sent")
        return str(resp)
    except Exception as e:
        logger.error(f"SMS webhook error: {e}")
        return str(MessagingResponse().message("Error processing SMS")), 500

@app.route('/health')
def system_health():
    try:
        with Session() as session:
            session.execute('SELECT 1')
        proof = generate_proof()
        return jsonify({
            "status": "healthy",
            "connections": len(connected_clients),
            "memory_usage": psutil.Process().memory_info().rss,
            "blockchain_proof": proof,
            "active_sessions": len({v['session_id'] for v in connected_clients.values()}),
            "platform_distribution": {
                'windows': sum('Windows' in c['platform'] for c in connected_clients.values()),
                'linux': sum('Linux' in c['platform'] for c in connected_clients.values()),
                'macos': sum('Mac' in c['platform'] for c in connected_clients.values())
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503

@app.route('/')
def index():
    return "HELIX 1.0 ACTIVE"

if __name__ == '__main__':
    proof = generate_proof()
    logger.info(f"🔗 Blockchain Proof: {proof}")
    if os.name == 'nt':
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    else:
        import gevent
        from gevent import monkey
        monkey.patch_all()
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
