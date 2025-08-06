import asyncio
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import psutil
from openai import AsyncOpenAI
import anthropic
from huggingface_hub import AsyncInferenceClient
import google.generativeai as genai
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

class THOTH:
    def __init__(self):
        load_dotenv()
        self.clients = {}
        self.active_ais = []
        self.history = {}
        logger.debug("THOTH initialized")

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
                    response = await client.chat.completions.create(
                        model=model,
                        messages=self.history[user_id][-5:],
                        max_tokens=500
                    )
                    content = response.choices[0].message.content
                    self.history[user_id].append({'role': 'assistant', 'content': content})
                    logger.debug(f"API response: {content[:50]}")
                    return {'content': content, 'sources': ['https://api.openai.com']}
                elif ai_id == 'claude':
                    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY", ""))
                    if user_id not in self.history:
                        self.history[user_id] = []
                    self.history[user_id].append({'role': 'user', 'content': content})
                    prompt = content
                    if is_critic:
                        prompt = f"As a Devil's Advocate, critically analyze and challenge this input: {content}"
                    response = client.messages.create(
                        model=model,
                        messages=self.history[user_id][-5:],
                        max_tokens=500
                    )
                    content = response.content[0].text
                    self.history[user_id].append({'role': 'assistant', 'content': content})
                    logger.debug(f"API response: {content[:50]}")
                    return {'content': content, 'sources': ['https://api.anthropic.com']}
                elif ai_id == 'huggingface':
                    client = AsyncInferenceClient(model=model, token=os.getenv("HF_API_KEY", ""))
                    if user_id not in self.history:
                        self.history[user_id] = []
                    self.history[user_id].append({'role': 'user', 'content': content})
                    prompt = content
                    if is_critic:
                        prompt = f"Act as a Devil's Advocate and critically challenge this input: {content}"
                    response = await client.text_generation(prompt, max_new_tokens=500)
                    content = response
                    self.history[user_id].append({'role': 'assistant', 'content': content})
                    logger.debug(f"API response: {content[:50]}")
                    return {'content': content, 'sources': ['https://api.huggingface.co']}
                elif ai_id == 'gemini':
                    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
                    model = genai.GenerativeModel(model)
                    if user_id not in self.history:
                        self.history[user_id] = []
                    self.history[user_id].append({'role': 'user', 'content': content})
                    prompt = content
                    if is_critic:
                        prompt = f"As a Devil's Advocate, critically analyze and challenge this input: {content}"
                    response = await model.generate_content_async(prompt)
                    content = response.text
                    self.history[user_id].append({'role': 'assistant', 'content': content})
                    logger.debug(f"API response: {content[:50]}")
                    return {'content': content, 'sources': ['https://api.gemini.google.com']}
                elif ai_id == 'grok':
                    return {'content': 'Grok API not publicly available', 'sources': []}
                return {'content': f'Error: {ai_id} not supported', 'sources': []}
            except Exception as e:
                logger.error(f"AI {ai_id} failed: {str(e)}, attempt {attempt+1}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return {'content': f'Error: {str(e)}', 'sources': []}
        logger.debug(f"Memory after API call: {process.memory_info().rss / 1024**2:.2f} MB")

thoth = THOTH()

@app.get("/list_ais")
async def list_ais():
    return {"ais": thoth.active_ais}

@app.post("/add_ai")
async def add_ai(request: AIRequest):
    if request.ai_id in thoth.clients:
        raise HTTPException(status_code=400, detail=f"{request.ai_id} already added")
    if request.ai_id not in ['gpt', 'claude', 'huggingface', 'gemini', 'grok']:
        raise HTTPException(status_code=400, detail="Only GPT, Claude, Hugging Face, Gemini, or Grok supported")
    thoth.clients[request.ai_id] = AIClient(ai_id=request.ai_id, model=request.model, api_key=os.getenv(f"{request.ai_id.upper()}_API_KEY", ""))
    thoth.active_ais.append(request.ai_id)
    logger.debug(f"Added AI: {request.ai_id}")
    return {'type': 'ai_added', 'ai_id': request.ai_id, 'is_primary': True}

@app.post("/remove_ai")
async def remove_ai(request: AIRemove):
    if request.ai_id not in thoth.clients:
        raise HTTPException(status_code=400, detail=f"{request.ai_id} not found")
    thoth.clients.pop(request.ai_id, None)
    thoth.active_ais.remove(request.ai_id) if request.ai_id in thoth.active_ais else None
    logger.debug(f"Removed AI: {request.ai_id}")
    return {'type': 'ai_removed', 'ai_id': request.ai_id, 'new_primary': thoth.active_ais[0] if thoth.active_ais else None}

@app.post("/message")
async def process_message(message: Message):
    if not thoth.active_ais:
        raise HTTPException(status_code=400, detail="No active AIs")
    responses = {}
    for ai_id, client in list(thoth.clients.items()):
        response = await thoth.query_ai(ai_id, client.model, message.content, is_critic=ai_id == message.critic)
        responses[ai_id] = {'content': response['content'], 'sources': response.get('sources', [])}
        logger.debug(f"Got response from {ai_id}: {response['content'][:50]}")
    return responses

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
