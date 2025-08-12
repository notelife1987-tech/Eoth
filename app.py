from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
from dotenv import load_dotenv
import requests
from datetime import datetime
import json
import logging
from functools import wraps
import uuid

# Load environment variables
load_dotenv()

# Configure logging for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super-secret-key-' + str(uuid.uuid4()))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///chatbot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Database Models
class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), db.ForeignKey('chat_session.session_id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(50))  # 'deepseek', 'gpt-hf', etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Error handling decorator for API calls
def safe_execute(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            return {"error": f"Unexpected error: {str(e)}"}
    return wrapper

# Enhanced AI Provider Functions
@safe_execute
def call_deepseek_api(messages, model="deepseek-chat"):
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        return {"error": "DeepSeek API key not configured. Add DEEPSEEK_API_KEY to .env"}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    data = {'model': model, 'messages': messages[-10:], 'max_tokens': 2000, 'temperature': 0.7}
    response = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data, timeout=30)
    if response.status_code == 200:
        result = response.json()
        return {"content": result['choices'][0]['message']['content'], "provider": "deepseek", "model": model}
    elif response.status_code == 429:
        return {"error": "DeepSeek rate limit exceeded. Try again later."}
    elif response.status_code == 401:
        return {"error": "DeepSeek authentication failed. Check API key."}
    else:
        return {"error": f"DeepSeek API error: {response.status_code}"}

@safe_execute
def call_gpt_via_huggingface(messages, model="microsoft/DialoGPT-large"):
    api_key = os.getenv('HUGGINGFACE_API_KEY')
    if not api_key:
        return {"error": "Hugging Face API key not configured. Add HUGGINGFACE_API_KEY to .env"}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages[-5:]]) + "\nassistant:"
    data = {'inputs': prompt, 'parameters': {'max_new_tokens': 500, 'temperature': 0.7, 'return_full_text': False}, 'options': {'wait_for_model': True}}
    response = requests.post(f'https://api-inference.huggingface.co/models/{model}', headers=headers, json=data, timeout=60)
    if response.status_code == 200:
        result = response.json()
        content = result[0]['generated_text'].strip() if result and 'generated_text' in result[0] else "No response generated."
        return {"content": content, "provider": "gpt-hf", "model": model}
    elif response.status_code == 503:
        return {"error": "Hugging Face model loading. Try again soon."}
    else:
        return {"error": f"Hugging Face API error: {response.status_code}"}

# Routes
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/sessions')
def list_sessions():
    try:
        sessions = ChatSession.query.order_by(ChatSession.created_at.desc()).all()
        session_list = []
        for session in sessions:
            last_message = ChatMessage.query.filter_by(session_id=session.session_id).order_by(ChatMessage.timestamp.desc()).first()
            session_list.append({
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "last_message": last_message.content[:100] + "..." if last_message and len(last_message.content) > 100 else last_message.content if last_message else "No messages",
                "message_count": len(session.messages)
            })
        return jsonify({"sessions": session_list})
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        return jsonify({"error": str(e)}), 500

# SocketIO Events
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('join_session')
def handle_join_session(data):
    session_id = data.get('session_id', 'default')
    join_room(session_id)
    emit('joined_session', {'session_id': session_id})
    # Send chat history
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    history = [{"role": msg.role, "content": msg.content, "provider": msg.provider, "timestamp": msg.timestamp.isoformat()} for msg in messages]
    emit('chat_history', {"history": history})

@socketio.on('leave_session')
def handle_leave_session(data):
    session_id = data.get('session_id', 'default')
    leave_room(session_id)
    emit('left_session', {'session_id': session_id})

@socketio.on('send_message')
def handle_message(data):
    message = data.get('message', '').strip()
    session_id = data.get('session_id', 'default')
    provider = data.get('provider', 'deepseek')
    model = data.get('model', 'deepseek-chat')
    if not message:
        emit('error', {"error": "Message is required"})
        return
    # Create session if needed
    chat_session = ChatSession.query.filter_by(session_id=session_id).first()
    if not chat_session:
        chat_session = ChatSession(session_id=session_id)
        db.session.add(chat_session)
        db.session.commit()
    # Save and emit user message
    user_message = ChatMessage(session_id=session_id, role='user', content=message, provider=provider)
    db.session.add(user_message)
    db.session.commit()
    emit('new_message', {'role': 'user', 'content': message, 'timestamp': user_message.timestamp.isoformat()}, room=session_id)
    # Get history
    history = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).limit(10).all()
    messages = [{"role": msg.role, "content": msg.content} for msg in history]
    # Call AI
    if provider == 'deepseek':
        response = call_deepseek_api(messages, model)
    elif provider == 'gpt':
        response = call_gpt_via_huggingface(messages, model)
    else:
        emit('error', {"error": "Invalid provider"})
        return
    if "error" in response:
        emit('error', response)
        return
    # Save and emit assistant message
    assistant_message = ChatMessage(session_id=session_id, role='assistant', content=response['content'], provider=provider)
    db.session.add(assistant_message)
    db.session.commit()
    emit('new_message', {'role': 'assistant', 'content': response['content'], 'provider': response['provider'], 'model': response.get('model', model), 'timestamp': assistant_message.timestamp.isoformat()}, room=session_id)

# HTML Template (Polished Frontend)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Chat Interface</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); min-height: 100vh; display: flex; flex-direction: column; }
        .header { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); padding: 1rem; text-align: center; border-bottom: 1px solid rgba(255, 255, 255, 0.2); }
        .header h1 { color: white; font-size: 1.8rem; margin-bottom: 0.5rem; }
        .provider-selector { display: flex; gap: 1rem; justify-content: center; align-items: center; flex-wrap: wrap; flex-direction: column; }
        .provider-buttons { display: flex; gap: 1rem; }
        .provider-btn { background: rgba(255, 255, 255, 0.2); border: 2px solid rgba(255, 255, 255, 0.3); color: white; padding: 0.5rem 1rem; border-radius: 25px; cursor: pointer; transition: all 0.3s ease; font-weight: 500; }
        .provider-btn:hover { background: rgba(255, 255, 255, 0.3); transform: translateY(-2px); }
        .provider-btn.active { background: #4CAF50; border-color: #4CAF50; box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3); }
        .main-container { display: flex; flex: 1; max-width: 1200px; margin: 0 auto; width: 100%; gap: 1rem; padding: 1rem; }
        .sidebar { width: 300px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 1rem; height: fit-content; }
        .sidebar h3 { color: white; margin-bottom: 1rem; font-size: 1.1rem; }
        .session-list { max-height: 400px; overflow-y: auto; }
        .session-item { background: rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 0.75rem; margin-bottom: 0.5rem; cursor: pointer; transition: all 0.3s ease; border: 1px solid transparent; }
        .session-item:hover { background: rgba(255, 255, 255, 0.2); transform: translateX(5px); }
        .session-item.active { border-color: #4CAF50; background: rgba(76, 175, 80, 0.2); }
        .session-item h4 { color: white; font-size: 0.9rem; margin-bottom: 0.25rem; }
        .session-item p { color: rgba(255, 255, 255, 0.7); font-size: 0.8rem; }
        .chat-container { flex: 1; background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border-radius: 15px; display: flex; flex-direction: column; overflow: hidden; }
        .chat-messages { flex: 1; padding: 1rem; overflow-y: auto; max-height: 60vh; }
        .message { margin-bottom: 1rem; padding: 1rem; border-radius: 15px; max-width: 80%; animation: fadeIn 0.3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .message.user { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; margin-left: auto; }
        .message.assistant { background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.2); }
        .message-info { font-size: 0.75rem; opacity: 0.7; margin-top: 0.5rem; }
        .chat-input-container { padding: 1rem; background: rgba(0, 0, 0, 0.2); border-top: 1px solid rgba(255, 255, 255, 0.1); }
        .chat-input-form { display: flex; gap: 0.5rem; }
        .chat-input { flex: 1; padding: 0.75rem; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 25px; background: rgba(255, 255, 255, 0.1); color: white; outline: none; font-size: 1rem; }
        .chat-input::placeholder { color: rgba(255, 255, 255, 0.5); }
        .chat-input:focus { border-color: #4CAF50; box-shadow: 0 0 10px rgba(76, 175, 80, 0.3); }
        .send-btn { background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); border: none; color: white; padding: 0.75rem 1.5rem; border-radius: 25px; cursor: pointer; transition: all 0.3s ease; font-weight: 500; }
        .send-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3); }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .new-session-btn { width: 100%; background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); border: none; color: white; padding: 0.75rem; border-radius: 10px; cursor: pointer; margin-bottom: 1rem; transition: all 0.3s ease; font-weight: 500; }
        .new-session-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3); }
        .loading { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(255, 255, 255, 0.3); border-radius: 50%; border-top-color: white; animation: spin 1s ease-in-out infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @media (max-width: 768px) { .main-container { flex-direction: column; } .sidebar { width: 100%; order: 2; } .chat-container { order: 1; } .provider-buttons { flex-direction: column; gap: 0.5rem; } }
    </style>
</head>
<body>
    <div class="header">
        <h1>AI Chat Interface</h1>
        <div class="provider-selector">
            <div class="provider-buttons">
                <button class="provider-btn active" data-provider="deepseek">DeepSeek AI</button>
                <button class="provider-btn" data-provider="gpt">GPT Models</button>
            </div>
            <small style="color: rgba(255,255,255,0.7); margin-top: 0.5rem;">GPT powered by Hugging Face</small>
        </div>
    </div>
    <div class="main-container">
        <div class="sidebar">
            <button class="new-session-btn" onclick="createNewSession()">+ New Chat</button>
            <h3>Chat Sessions</h3>
            <div class="session-list" id="sessionList"></div>
        </div>
        <div class="chat-container">
            <div class="chat-messages" id="chatMessages">
                <div class="message assistant">
                    <div>Hello! I'm your AI assistant. Choose your preferred AI provider above and start chatting!</div>
                    <div class="message-info">System • Just now</div>
                </div>
            </div>
            <div class="chat-input-container">
                <form class="chat-input-form" onsubmit="sendMessage(event)">
                    <input type="text" class="chat-input" id="messageInput" placeholder="Type your message..." required>
                    <button type="submit" class="send-btn" id="sendBtn">Send</button>
                </form>
            </div>
        </div>
    </div>
    <script>
        let currentProvider = 'deepseek';
        let currentSession = 'default';
        let isLoading = false;
        const socket = io();
        document.addEventListener('DOMContentLoaded', () => { loadSessions(); socket.emit('join_session', {session_id: currentSession}); });
        document.querySelectorAll('.provider-btn').forEach(btn => { btn.addEventListener('click', () => { document.querySelector('.provider-btn.active').classList.remove('active'); btn.classList.add('active'); currentProvider = btn.dataset.provider; }); });
        function createNewSession() {
            currentSession = 'session_' + Date.now();
            document.getElementById('chatMessages').innerHTML = '<div class="message assistant"><div>New chat session started! How can I help you today?</div><div class="message-info">System • Just now</div></div>';
            socket.emit('join_session', {session_id: currentSession});
            loadSessions();
        }
        async function loadSessions() {
            try {
                const response = await fetch('/api/sessions');
                const data = await response.json();
                const sessionList = document.getElementById('sessionList');
                sessionList.innerHTML = '';
                data.sessions.forEach(session => {
                    const div = document.createElement('div');
                    div.className = 'session-item' + (session.session_id === currentSession ? ' active' : '');
                    div.onclick = () => switchSession(session.session_id);
                    div.innerHTML = `<h4>Chat ${session.session_id.replace('session_', '').substring(0, 8)}...</h4><p>${session.last_message}</p>`;
                    sessionList.appendChild(div);
                });
            } catch (error) { console.error('Error loading sessions:', error); }
        }
        function switchSession(sessionId) {
            socket.emit('leave_session', {session_id: currentSession});
            currentSession = sessionId;
            socket.emit('join_session', {session_id: currentSession});
            loadSessions();
        }
        function addMessageToChat(content, role, provider = 'system') {
            const chatMessages = document.getElementById('chatMessages');
            const div = document.createElement('div');
            div.className = `message ${role}`;
            const now = new Date().toLocaleTimeString();
            div.innerHTML = `<div>${content}</div><div class="message-info">${provider} • ${now}</div>`;
            chatMessages.appendChild(div);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        function sendMessage(event) {
            event.preventDefault();
            if (isLoading) return;
            const input = document.getElementById('messageInput');
            const btn = document.getElementById('sendBtn');
            const message = input.value.trim();
            if (!message) return;
            addMessageToChat(message, 'user');
            input.value = '';
            isLoading = true;
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span>';
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message assistant';
            loadingDiv.id = 'loading-message';
            loadingDiv.innerHTML = `<div><span class="loading"></span> Thinking...</div><div class="message-info">${currentProvider} • Just now</div>`;
            document.getElementById('chatMessages').appendChild(loadingDiv);
            socket.emit('send_message', { message, session_id: currentSession, provider: currentProvider });
        }
        socket.on('connect', () => { console.log('SocketIO connected!'); socket.emit('join_session', {session_id: currentSession}); });
        socket.on('disconnect', () => { console.log('SocketIO disconnected'); });
        socket.on('joined_session', data => { console.log('Joined session:', data.session_id); });
        socket.on('new_message', data => {
            const loading = document.getElementById('loading-message');
            if (loading) loading.remove();
            addMessageToChat(data.content, data.role, data.provider || 'system');
            if (data.role === 'assistant') loadSessions();
            isLoading = false;
            document.getElementById('sendBtn').disabled = false;
            document.getElementById('sendBtn').innerHTML = 'Send';
        });
        socket.on('error', data => {
            const loading = document.getElementById('loading-message');
            if (loading) loading.remove();
            addMessageToChat(`Error: ${data.error}`, 'assistant', 'error');
            isLoading = false;
            document.getElementById('sendBtn').disabled = false;
            document.getElementById('sendBtn').innerHTML = 'Send';
        });
        socket.on('chat_history', data => {
            const chatMessages = document.getElementById('chatMessages');
            chatMessages.innerHTML = '';
            if (data.history.length === 0) {
                chatMessages.innerHTML = '<div class="message assistant"><div>Hello! I\'m your AI assistant. How can I help you today?</div><div class="message-info">System • Just now</div></div>';
                return;
            }
            data.history.forEach(msg => addMessageToChat(msg.content, msg.role, msg.provider || 'system'));
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
        document.getElementById('messageInput').addEventListener('keypress', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(e); } });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
