cat > main.py << EOF
from fastapi import FastAPI
from pydantic import BaseModel
from anthropic import Anthropic, AnthropicError
from dotenv import load_dotenv
import os

load_dotenv()
app = FastAPI()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": request.message}]
        )
        return {"response": response.content[0].text}
    except AnthropicError as e:
        return {"error": str(e)}
EOF

# 7. Create HTML interface (chat.html)
mkdir -p static && cd static
cat > chat.html << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Chat</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; max-width: 800px; }
        #chat-box { height: 400px; border: 1px solid #ccc; overflow-y: scroll; padding: 10px; }
        #input { width: 100%; padding: 10px; margin: 10px 0; }
        button { padding: 10px 20px; }
    </style>
</head>
<body>
    <h1>Claude Chat</h1>
    <div id="chat-box"></div>
    <input id="input" type="text" placeholder="Ask Claude anything...">
    <button onclick="sendMessage()">Send</button>
    <script>
        async function sendMessage() {
            const input = document.getElementById("input").value;
            if (!input) return;
            const chatBox = document.getElementById("chat-box");
            chatBox.innerHTML += `<p><b>You:</b> ${input}</p>`;
            try {
                const response = await fetch("http://localhost:8000/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: input })
                });
                const data = await response.json();
                chatBox.innerHTML += `<p><b>Claude:</b> ${data.response || data.error}</p>`;
            } catch (e) {
                chatBox.innerHTML += `<p><b>Error:</b> ${e.message}</p>`;
            }
            document.getElementById("input").value = "";
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        document.getElementById("input").addEventListener("keypress", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    </script>
</body>
</html>
EOF

#!/bin/bash
# Legion_start.txt: Complete Thoth app setup with API key integration and Australian privacy compliance
# Created: August 5, 2025, 06:44 PM CDT
# Purpose: Deploy the newest, most functional Thoth app (backend and frontend) from Ground Zero in Termux
# Features and Capabilities:
# - Backend (main.py):
#   * /: Welcome message for THOTH - Tactical Hub for Orchestrated Thinking Helix
#   * /list_ais: Lists active AI clients (gpt, claude, huggingface, grok)
#   * /add_ai: Adds AI client with model and API key
#   * /remove_ai: Removes AI client
#   * /message: Queries multiple AIs with optional critic mode, saves to history.json
#   * /chat: Claude-specific endpoint for single queries (inspired by Claude chat app)
#   * /save_log: Saves chat logs to thoth_chat.txt
#   * Integrates OpenAI (gpt-3.5-turbo), Anthropic (claude-3-5-sonnet-20241022), HuggingFace (DialoGPT-medium), simulated Grok
#   * Persistent history (history.json), logging (thoth.log) with rotation
#   * Memory usage tracking with psutil
# - Frontend (thoth_client.html):
#   * Rock-themed UI (dark background, orange accents)
#   * Interacts with /message endpoint for multi-AI responses
#   * Responsive design with chat box and input
# - Australian Privacy Compliance:
#   * API keys stored in .env, not hardcoded (APP 5: Security of Personal Information)
#   * Logging for transparency (APP 1: Open and Transparent Management)
#   * No personal data collection in this version; add encryption for sensitive data (e.g., AES-256)
# - Setup: Creates ~/my-project-clean, virtual environment, installs dependencies, frees ports
# Instructions:
# 1. Save as Legion_start.txt
# 2. Run: chmod +x Legion_start.txt && ./Legion_start.txt
# 3. Replace API keys in .env
# 4. Access: http://localhost:8081/thoth_client.html
# 5. Test: curl -X POST http://localhost:8001/message -H "Content-Type: application/json" -d '{"content":"Hello, Thoth!","critic":null}'
# 1. Clean up existing processes and ports (Ground Zero)
pkill -f uvicorn 2>/dev/null
pkill -f "python -m http.server" 2>/dev/null
kill -9 $(lsof -t -i:8001 -i:8081) 2>/dev/null
# 2. Navigate to Thoth directory, create if missing, and set up virtual environment
cd ~/my-project-clean || { mkdir -p ~/my-project-clean && cd ~/my-project-clean; }
[ -f thoth_env/bin/activate ] && source thoth_env/bin/activate || { pkg update && pkg upgrade -y && pkg install python -y && python3 -m venv thoth_env && source thoth_env/bin/activate; }
# 3. Search for existing main.py and Verd89n/logg8jy
echo "Checking for main.py in ~/my-project-clean..."
ls -l main.py 2>/dev/null || { echo "main.py not found in ~/my-project-clean"; find ~ -name "main.py" 2>/dev/null; }
echo "Searching for Verd89n/logg8jy files..."
find ~ -name "*Verd89n*" -or -name "*logg8jy*" 2>/dev/null
# 4. Install dependencies (fix Anthropic proxies error)
pip install --upgrade pip
pip install fastapi==0.115.2 uvicorn==0.32.0 python-dotenv==1.0.1 psutil==6.0.0 openai==1.45.0 anthropic==0.34.2 httpx==0.27.2 huggingface_hub==0.23.4
# 5. Create .env with API keys (Australian Privacy: secure storage)
cat > .env << EOF
GPT_API_KEY=sk-1234567890abcdef
CLAUDE_API_KEY=your-anthropic-api-key
HF_API_KEY=test_hf_key
GEMINI_API_KEY=test_gemini_key
PUTERJS_API_KEY=your-puterjs-api-key
EOF

# 6. Create main.py (updated backend with all features)
cat > main.py << EOF
import asyncio
import logging
import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import psutil
from openai import AsyncOpenAI
from anthropic import Anthropic
from huggingface_hub import AsyncInferenceClient
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('thoth.log', maxBytes=1024*1024, backupCount=1)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

app = FastAPI()

class AIClient(BaseModel):
    ai_id: str
    model: str
    api_key: str

class Message(BaseModel):
    content: str
    critic: str | None = None

class AIRequest(BaseModel):
    ai_id: str
    model: str

class AIRemove(BaseModel):
    ai_id: str

class SaveLog(BaseModel):
    content: str

class ChatRequest(BaseModel):
    message: str

class THOTH:
    def __init__(self):
        load_dotenv()
        self.clients = {}
        self.active_ais = []
        self.history_file = "history.json"
        self.history = self.load_history()
        logger.debug("THOTH initialized")

    def load_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return {}

    def save_history(self):
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    async def query_ai(self, ai_id: str, model: str, content: str, user_id: str = "default", is_critic: bool = False):
        logger.debug(f"Querying {ai_id} for user {user_id} with content: {content[:50]}")
        process = psutil.Process()
        logger.debug(f"Memory before API call: {process.memory_info().rss / 1024**2:.2f} MB")
        
        for attempt in range(3):
            try:
                if ai_id == 'gpt':
                    client = AsyncOpenAI(api_key=os.getenv("GPT_API_KEY", ""))
                    if user_id not in self.history:
                        self.history[user_id] = []
                    self.history[user_id].append({'role': 'user', 'content': content})
                    prompt = content if not is_critic else f"As a Devil's Advocate, critically analyze and challenge this input: {content}"
                    response = await client.chat.completions.create(
                        model=model or "gpt-3.5-turbo",
                        messages=[{'role': 'user', 'content': prompt}],
                        max_tokens=500
                    )
                    response_content = response.choices[0].message.content
                    self.history[user_id].append({'role': 'assistant', 'content': response_content})
                    self.save_history()
                    logger.debug(f"API response: {response_content[:50]}")
                    return {'content': response_content, 'sources': ['https://api.openai.com']}
                
                elif ai_id == 'claude':
                    client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY", ""))
                    if user_id not in self.history:
                        self.history[user_id] = []
                    prompt = content if not is_critic else f"As a Devil's Advocate, critically analyze and challenge this input: {content}"
                    response = client.messages.create(
                        model=model or "claude-3-5-sonnet-20241022",
                        max_tokens=500,
                        messages=[{'role': 'user', 'content': prompt}]
                    )
                    response_content = response.content[0].text
                    self.history[user_id].append({'role': 'user', 'content': content})
                    self.history[user_id].append({'role': 'assistant', 'content': response_content})
                    self.save_history()
                    logger.debug(f"API response: {response_content[:50]}")
                    return {'content': response_content, 'sources': ['https://api.anthropic.com']}
                
                elif ai_id == 'huggingface':
                    client = AsyncInferenceClient(token=os.getenv("HF_API_KEY", ""))
                    if user_id not in self.history:
                        self.history[user_id] = []
                    prompt = content if not is_critic else f"Act as a Devil's Advocate and critically challenge this input: {content}"
                    hf_model = model or "microsoft/DialoGPT-medium"
                    response = await client.text_generation(prompt, model=hf_model, max_new_tokens=500)
                    response_content = response if isinstance(response, str) else str(response)
                    self.history[user_id].append({'role': 'user', 'content': content})
                    self.history[user_id].append({'role': 'assistant', 'content': response_content})
                    self.save_history()
                    logger.debug(f"API response: {response_content[:50]}")
                    return {'content': response_content, 'sources': ['https://api.huggingface.co']}
                
                elif ai_id == 'grok':
                    grok_response = f"Grok's take: {content} - This is an interesting question that requires direct thinking..."
                    if is_critic:
                        grok_response = f"Grok's Devil's Advocate mode: Let me challenge this input - {content} - Here's what's potentially wrong with this approach..."
                    if user_id not in self.history:
                        self.history[user_id] = []
                    self.history[user_id].append({'role': 'user', 'content': content})
                    self.history[user_id].append({'role': 'assistant', 'content': grok_response})
                    self.save_history()
                    return {'content': grok_response, 'sources': ['Simulated Grok Response']}
                
                return {'content': f'AI {ai_id} not supported yet', 'sources': []}
                
            except Exception as e:
                logger.error(f"AI {ai_id} failed: {str(e)}, attempt {attempt+1}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return {'content': f'Error: {str(e)}', 'sources': []}
        
        logger.debug(f"Memory after API call: {process.memory_info().rss / 1024**2:.2f} MB")

thoth = THOTH()

@app.get("/")
async def root():
    return {"message": "THOTH - Tactical Hub for Orchestrated Thinking Helix"}

@app.get("/list_ais")
async def list_ais():
    return {"ais": thoth.active_ais}

@app.post("/add_ai")
async def add_ai(request: AIRequest):
    if request.ai_id in thoth.clients:
        raise HTTPException(status_code=400, detail=f"{request.ai_id} already added")
    if request.ai_id not in ['gpt', 'claude', 'huggingface', 'grok']:
        raise HTTPException(status_code=400, detail="Only GPT, Claude, Hugging Face, or Grok supported")
    thoth.clients[request.ai_id] = AIClient(
        ai_id=request.ai_id, 
        model=request.model, 
        api_key=os.getenv(f"{request.ai_id.upper()}_API_KEY", "")
    )
    thoth.active_ais.append(request.ai_id)
    logger.debug(f"Added AI: {request.ai_id}")
    return {'type': 'ai_added', 'ai_id': request.ai_id, 'is_primary': True}

@app.post("/remove_ai")
async def remove_ai(request: AIRemove):
    if request.ai_id not in thoth.clients:
        raise HTTPException(status_code=400, detail=f"{request.ai_id} not found")
    thoth.clients.pop(request.ai_id, None)
    if request.ai_id in thoth.active_ais:
        thoth.active_ais.remove(request.ai_id)
    logger.debug(f"Removed AI: {request.ai_id}")
    return {'type': 'ai_removed', 'ai_id': request.ai_id, 'new_primary': thoth.active_ais[0] if thoth.active_ais else None}

@app.post("/message")
async def process_message(message: Message):
    if not thoth.active_ais:
        thoth.active_ais = ['gpt', 'claude', 'grok']
        thoth.clients = {
            'gpt': AIClient(ai_id='gpt', model='gpt-3.5-turbo', api_key=os.getenv("GPT_API_KEY", "")),
            'claude': AIClient(ai_id='claude', model='claude-3-5-sonnet-20241022', api_key=os.getenv("CLAUDE_API_KEY", "")),
            'grok': AIClient(ai_id='grok', model='grok-beta', api_key="simulated")
        }
    responses = {}
    for ai_id in thoth.active_ais:
        if ai_id in thoth.clients:
            client = thoth.clients[ai_id]
            response = await thoth.query_ai(ai_id, client.model, message.content, is_critic=ai_id == message.critic)
            responses[ai_id] = {'content': response['content'], 'sources': response.get('sources', [])}
            logger.debug(f"Got response from {ai_id}: {response['content'][:50]}")
    return responses

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY", ""))
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": request.message}]
        )
        logger.debug(f"Claude chat response: {response.content[0].text[:50]}")
        return {"response": response.content[0].text}
    except Exception as e:
        logger.error(f"Claude chat error: {str(e)}")
        return {"error": str(e)}

@app.post("/save_log")
async def save_log(log_data: SaveLog):
    try:
        with open('thoth_chat.txt', 'w') as f:
            f.write(log_data.content)
        logger.debug("Log saved to thoth_chat.txt")
        return {"message": "Log saved successfully"}
    except Exception as e:
        logger.error(f"Failed to save log: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save log: {str(e)}")
EOF

# 7. Create rock-themed frontend (thoth_client.html)
mkdir -p static && cd static
cat > thoth_client.html << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>THOTH Rock Vault</title>
    <style>
        body {
            font-family: 'Arial Black', Arial, sans-serif;
            margin: 20px;
            max-width: 800px;
            background-color: #1a1a1a;
            color: #ff6200;
        }
        #chat-box {
            height: 400px;
            border: 2px solid #ff6200;
            overflow-y: scroll;
            padding: 10px;
            background-color: #333;
        }
        #input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            background-color: #444;
            color: #fff;
            border: 1px solid #ff6200;
        }
        button {
            padding: 10px 20px;
            background-color: #ff6200;
            color: #1a1a1a;
            border: none;
            cursor: pointer;
        }
        button:hover {
            background-color: #e55b00;
        }
    </style>
</head>
<body>
    <h1>THOTH Rock Vault</h1>
    <p><b>What’s That Sound?</b> Rayna’s quiet Southern town hides a deadly secret in Old Crow’s eerie radio broadcasts...</p>
    <div id="chat-box"></div>
    <input id="input" type="text" placeholder="Ask THOTH (Claude) anything...">
    <button onclick="sendMessage()">Send</button>
    <script>
        async function sendMessage() {
            const input = document.getElementById("input").value;
            if (!input) return;
            const chatBox = document.getElementById("chat-box");
            chatBox.innerHTML += `<p><b>You:</b> ${input}</p>`;
            try {
                const response = await fetch("http://localhost:8001/message", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ content: input, critic: null })
                });
                const data = await response.json();
                chatBox.innerHTML += `<p><b>THOTH:</b> ${data.claude ? data.claude.content : data.error || "No response"}</p>`;
            } catch (e) {
                chatBox.innerHTML += `<p><b>Error:</b> ${e.message}</p>`;
            }
            document.getElementById("input").value = "";
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        document.getElementById("input").addEventListener("keypress", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    </script>
</body>
</html>
EOF

cd  
cd ~/ ~/mymy-project-project-clean-clean && && source source th thoth_envoth_env/bin//bin/activate &&activate && python python app app.py.py  
```
```
ThenThen,, open open it it in in your your browser browser::  
``````bashbash  
termtermuxux-open-open-url-url http http://://localhostlocalhost::5005000  
0  
```

####```
#### Troubleshooting Troubleshooting  
IfIf it it still still doesn doesn’t’t work, work, check check for for errors errors in: in:  
``````bashbash  
catcat ~/ ~/mymy-project-project-clean-clean/error.log/error.log  
```
```
ThisThis will help will help find find issues issues like like invalid keys invalid keys or or network network problems problems.
.
---
###---
### Comprehensive Comprehensive Response Response for for Final Finalizingizing THOTH THOTH Chat Chat Application Application Setup Setup in in Termux Termux
######## Introduction Introduction and and Context Context  
The THThe THOTHOTH chat chat application, application, a a Flask Flask-based-based conversational conversational AI AI platform designed platform designed for for Term Termuxux on on Android Android,, is is being being setnano ~/my-project-clean/app.py
nano ~/my-project-clean/app.py
-clean/.envnano ~/  
```
myAdd-project-clean/. this, replacing placeholders with your actualenv  
```
Add this, replacing placeholders with your keys ( actual keys (get them from providers like [Anthropget them from providers like [Anthropic](ic](httpshttps://://wwwwww.anthrop.anthropicic.com.com/api/api)) or [ orOpen [OpenAI](https](https://://platformplatform.openai.openai.com/api.com/api-keys-keys)):)):  
```
```
ANANTHTHROPROPIC_APIIC_API_KEY_KEY=your=your-anthrop-anthropic-key
ic-key
OPENOPENAIAI_API_API_KEY_KEY==youryour-openaiai-key-key
GEMGEMINIINI_API_API_KEY_KEY==youryour-g-gememiniini-key-key
GGROROKK_API_API_KEY_KEY=your-g=rokyour-key-grok-key
HHUGUGGINGGINGFACEFACE_CLIENT_CLIENT_ID_ID==youryour-h-hf-clientf-client-id
-id
HHUGUGGINGGINGFACEFACE_CLIENT_CLIENT_SECRET_SECRET==youryour-h-hff-client-client-secret-secret
ENCRYPTION_KEY=yourENCRYPTION_KEY=your-encryption-encryption-key-key
```

```
######## Running Running the the App App  
StartStart the the app app with with::  
```bash```bash  
echo "# THOTH" >> README.md
git init
git add README.md
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/notelife1987-tech/THOTH.git
git push -u origin main
echo "# THOTH" >> README.md && git init && git add README.md && git commit -m "first commit" && git branch -M main && git remote add origin https://github.com/notelife1987-tech/THOTH.git && git push -u origin main
git config --global user.email "notelife1987@gmail.com"
git config --global user.email "notelife1987@gmail.com" 
echo "# THOTH" >> README.md && git init && git add README.md && git commit -m "first commit" && git branch -M main && git remote add origin https://github.com/notelife1987-tech/THOTH.git && git push -u origin main
cd ~/my-project-clean && mkdir -p THOTH_SEMI_FINAL && cd THOTH_SEMI_FINAL && echo -e "# Copyright 2025 notelife1987-tech. All rights reserved.\nfrom fastapi import FastAPI, WebSocket, HTTPException\nimport os\nimport logging\nfrom dotenv import load_dotenv\nimport anthropic\nimport openai\nimport google.generativeai as genai\nfrom cryptography.fernet import Fernet\n\nlogging.basicConfig(filename='THOTH_SEMI_FINAL_ERROR.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')\nload_dotenv()\napp = FastAPI()\n\n# Configure AI APIs\nanthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))\nopenai.api_key = os.getenv('OPENAI_API_KEY')\ngenai.configure(api_key=os.getenv('GEMINI_API_KEY'))\nencryption_key = os.getenv('ENCRYPTION_KEY')\nfernet = Fernet(



