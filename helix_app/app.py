# app.py

import os
import json
import requests
from datetime import datetime, timedelta
import threading
from dotenv import load_dotenv

from flask import Flask, jsonify, request, render_template, session
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from uuid import uuid4

# Load environment variables
load_dotenv()

# Init app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///chatbot.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# -----------------------------
# Database Models
# -----------------------------
class ChatSession(db.Model):
    __tablename__ = 'chat_session'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('ChatMessage', backref='session', lazy=True, cascade='all, delete-orphan')

class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), db.ForeignKey('chat_session.session_id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'host', etc.
    content = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class BetaEnrollment(db.Model):
    __tablename__ = 'beta_enrollment'
    id = db.Column(db.Integer, primary_key=True)
    organization = db.Column(db.String(200))
    project = db.Column(db.String(200))
    email = db.Column(db.String(200))
    country = db.Column(db.String(100))
    expected_users = db.Column(db.Integer, default=1)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDING')
    verifier = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GenieOutput(db.Model):
    __tablename__ = 'genie_output'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    provider = db.Column(db.String(50))
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class GenieCritique(db.Model):
    __tablename__ = 'genie_critique'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GenieExecution(db.Model):
    __tablename__ = 'genie_execution'
    id = db.Column(db.Integer, primary_key=True)
    genie_output_id = db.Column(db.Integer, db.ForeignKey('genie_output.id'), nullable=False)
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
    exit_code = db.Column(db.Integer)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)

class LegionGroup(db.Model):
    __tablename__ = 'legion_group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LegionProposal(db.Model):
    __tablename__ = 'legion_proposal'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    legion_id = db.Column(db.Integer, db.ForeignKey('legion_group.id'))
    command_text = db.Column(db.Text, nullable=False)
    rationale = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDING')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# -----------------------------
# AI Provider Functions
# -----------------------------
def call_deepseek_api(messages, model="deepseek-chat"):
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key: return {"error": "DeepSeek API key not configured"}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    data = {'model': model, 'messages': messages, 'max_tokens': 2000, 'temperature': 0.7}
    try:
        r = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data, timeout=30)
        if r.status_code == 200:
            res = r.json()
            return {"content": res['choices'][0]['message']['content'], "provider": "deepseek", "model": model}
        return {"error": f"DeepSeek API error: {r.status_code}"}
    except Exception as e:
        return {"error": f"DeepSeek API error: {str(e)}"}

def call_gpt_via_huggingface(messages, model="microsoft/DialoGPT-large"):
    api_key = os.getenv('HUGGINGFACE_API_KEY')
    if not api_key: return {"error": "Hugging Face API key not configured"}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    data = {'inputs': prompt, 'parameters': {'max_new_tokens': 500, 'temperature': 0.7, 'do_sample': True}}
    try:
        r = requests.post(f'https://api-inference.huggingface.co/models/{model}', headers=headers, json=data, timeout=30)
        if r.status_code == 200:
            result = r.json()
            if isinstance(result, list) and len(result) > 0:
                generated = result[0].get('generated_text', '')
                if prompt in generated:
                    generated = generated.replace(prompt, '').strip()
                return {"content": generated, "provider": "gpt-hf", "model": model}
        return {"error": f"Hugging Face API error: {r.status_code}"}
    except Exception as e:
        return {"error": f"Hugging Face API error: {str(e)}"}

def call_anthropic_api(messages, model="claude-3-haiku-20240307"):
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key: return {"error": "Anthropic API key not configured"}
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }
    data = {
        "model": model,
        "max_tokens": 1024,
        "messages": messages
    }
    try:
        r = requests.post('https://api.anthropic.com/v1/messages', headers=headers, json=data, timeout=30)
        if r.status_code == 200:
            res = r.json()
            return {"content": res['content'][0]['text'], "provider": "anthropic", "model": model}
        return {"error": f"Anthropic API error: {r.status_code} - {r.text}"}
    except Exception as e:
        return {"error": f"Anthropic API error: {str(e)}"}

def call_gemini_api(messages, model="gemini-pro"):
    # Placeholder for Gemini; replace with real endpoint when available
    return {"content": "Gemini response placeholder based on inputs.", "provider": "gemini", "model": model}

# -----------------------------
# Mode Logic Functions
# -----------------------------
def get_llm_response(provider, messages, model=None):
    if provider == 'deepseek':
        return call_deepseek_api(messages, model)
    elif provider == 'gpt':
        return call_gpt_via_huggingface(messages, model)
    elif provider == 'anthropic':
        return call_anthropic_api(messages, model)
    elif provider == 'gemini':
        return call_gemini_api(messages, model)
    return {"error": "Invalid provider"}

def process_helix_mode(session_id, user_message_content, history):
    providers = ['deepseek', 'gpt', 'anthropic', 'gemini']
    responses = {}
    threads = []
    
    # Function to run API call in a thread
    def call_api(provider):
        responses[provider] = get_llm_response(provider, history + [{"role": "user", "content": user_message_content}])

    for provider in providers:
        thread = threading.Thread(target=call_api, args=(provider,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()

    # Save all responses to DB and emit to client
    for provider, response in responses.items():
        if "error" not in response:
            assistant_message = ChatMessage(
                session_id=session_id,
                role='assistant',
                content=response['content'],
                provider=provider
            )
            db.session.add(assistant_message)
            socketio.emit('new_message', {
                'role': 'assistant',
                'content': response['content'],
                'provider': provider,
                'timestamp': assistant_message.timestamp.isoformat(),
                'session_id': session_id
            }, room=session_id)
        
    db.session.commit()
    return responses

def process_legion_mode(session_id, user_message_content, history, host_assistant):
    providers = ['deepseek', 'gpt', 'anthropic', 'gemini']
    providers.remove(host_assistant)
    
    responses = {}
    threads = []

    def call_api(provider):
        responses[provider] = get_llm_response(provider, history + [{"role": "user", "content": user_message_content}])

    for provider in providers:
        thread = threading.Thread(target=call_api, args=(provider,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()

    # Generate the prompt for the host assistant
    legion_prompt = f"Critique and synthesize the following responses to the user's query: '{user_message_content}'. The responses are from different AI models:\n\n"
    for provider, response in responses.items():
        legion_prompt += f"--- {provider.upper()} Response ---\n{response.get('content', 'Error')}\n\n"
    legion_prompt += f"Based on these, provide a single, cohesive, and high-quality response to the user. You are the host of this legion of intelligences, speaking for all of them."

    host_response = get_llm_response(host_assistant, [{"role": "user", "content": legion_prompt}])

    if "error" not in host_response:
        host_message = ChatMessage(
            session_id=session_id,
            role='host',
            content=host_response['content'],
            provider=host_assistant
        )
        db.session.add(host_message)
        db.session.commit()
        socketio.emit('new_message', {
            'role': 'host',
            'content': host_response['content'],
            'provider': host_assistant,
            'timestamp': host_message.timestamp.isoformat(),
            'session_id': session_id
        }, room=session_id)

    return host_response

def process_genie_mode(session_id, user_message_content, host_assistant):
    # This is an initial implementation. The full Genie logic would be more complex.
    # It will trigger the Genie logic and emit updates to the client as it progresses.
    # For now, it will return a placeholder response while the backend work is simulated.
    
    # Here we would simulate the multi-step process
    socketio.emit('genie_status', {'step': 'gathering_inputs', 'message': 'Genie is gathering outputs from multiple models...'}, room=session_id)
    # Simulate API calls and critique
    
    # For now, let's just use the host assistant to give a final placeholder
    genie_prompt = f"The user has initiated Genie mode with the prompt: '{user_message_content}'. You are the Genie, and you must respond with a welcoming, magical, and helpful tone. Your purpose is to fulfill the user's wishes by creating a perfect, synthesized response."
    genie_response = get_llm_response(host_assistant, [{"role": "user", "content": genie_prompt}])
    
    if "error" not in genie_response:
        genie_message = ChatMessage(
            session_id=session_id,
            role='host',
            content=genie_response['content'],
            provider=host_assistant
        )
        db.session.add(genie_message)
        db.session.commit()
        socketio.emit('new_message', {
            'role': 'host',
            'content': genie_response['content'],
            'provider': host_assistant,
            'timestamp': genie_message.timestamp.isoformat(),
            'session_id': session_id
        }, room=session_id)
    
    return genie_response

# -----------------------------
# Routes
# -----------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        data = request.json
        message = data.get('message', '').strip()
        session_id = data.get('session_id', str(uuid4()))
        mode = data.get('mode', 'helix')
        host_assistant = data.get('host_assistant', 'deepseek')

        if not message:
            return jsonify({"error": "Message is required"}), 400

        # Create session if it doesn't exist
        chat_session = ChatSession.query.filter_by(session_id=session_id).first()
        if not chat_session:
            chat_session = ChatSession(session_id=session_id)
            db.session.add(chat_session)
            db.session.commit()
        
        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            role='user',
            content=message
        )
        db.session.add(user_message)
        db.session.commit()

        # Get conversation history
        history = ChatMessage.query.filter_by(session_id=session_id)\
                                     .order_by(ChatMessage.timestamp.asc())\
                                     .limit(10).all()
        
        messages_for_llm = [{"role": msg.role, "content": msg.content} for msg in history if msg.role != 'host']
        messages_for_llm.append({"role": "user", "content": message})

        # Process based on mode
        if mode == 'helix':
            # Helix mode handled by SocketIO for streaming responses
            process_helix_mode(session_id, message, messages_for_llm)
        elif mode == 'legion':
            process_legion_mode(session_id, message, messages_for_llm, host_assistant)
        elif mode == 'genie':
            process_genie_mode(session_id, message, host_assistant)
        
        return jsonify({"status": "success", "session_id": session_id})
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/sessions/<session_id>/history')
def get_chat_history(session_id):
    try:
        messages = ChatMessage.query.filter_by(session_id=session_id)\
                                     .order_by(ChatMessage.timestamp.asc()).all()
        
        history = [{"role": msg.role, "content": msg.content, "provider": msg.provider, "timestamp": msg.timestamp.isoformat()} for msg in messages]
        return jsonify({"history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sessions')
def list_sessions():
    try:
        sessions_db = ChatSession.query.order_by(ChatSession.created_at.desc()).all()
        session_list = []
        for session_item in sessions_db:
            last_message = ChatMessage.query.filter_by(session_id=session_item.session_id)\
                                             .order_by(ChatMessage.timestamp.desc()).first()
            session_list.append({
                "session_id": session_item.session_id,
                "created_at": session_item.created_at.isoformat(),
                "last_message": last_message.content[:100] + "..." if last_message and len(last_message.content) > 100 else last_message.content if last_message else "No messages",
                "message_count": len(session_item.messages)
            })
        return jsonify({"sessions": session_list})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/beta/apply', methods=['POST'])
def apply_beta():
    data = request.json or {}
    e = BetaEnrollment(
        organization=data.get('organization'), project=data.get('project'), email=data.get('email'),
        country=data.get('country'), expected_users=data.get('expected_users', 1), description=data.get('description', '')
    )
    db.session.add(e)
    db.session.commit()
    return jsonify({"id": e.id, "status": e.status})

@app.route('/api/beta/status/<int:id>')
def beta_status(id):
    e = BetaEnrollment.query.get(id)
    if not e: return jsonify({"error": "Not found"}), 404
    return jsonify({"id": e.id, "status": e.status, "organization": e.organization, "project": e.project})

@app.route('/api/beta/approve', methods=['POST'])
def beta_approve():
    data = request.json or {}
    e = BetaEnrollment.query.get(data.get('id'))
    if not e: return jsonify({"error": "Not found"}), 404
    e.verifier = data.get('verifier', 'admin')
    e.updated_at = datetime.utcnow()
    e.status = 'APPROVED' if data.get('approve', False) else 'DENIED'
    db.session.commit()
    return jsonify({"id": e.id, "status": e.status})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_session')
def handle_join_session(data):
    session_id = data.get('session_id', 'default')
    join_room(session_id)
    emit('joined_session', {'session_id': session_id})
    print(f"Client joined session: {session_id}")

@socketio.on('leave_session')
def handle_leave_session(data):
    session_id = data.get('session_id')
    leave_room(session_id)
    print(f"Client left session: {session_id}")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
