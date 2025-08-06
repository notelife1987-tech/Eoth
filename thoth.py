import asyncio
import websockets
import json
import logging
import zlib
from openai import AsyncOpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import psutil
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('thoth.log', maxBytes=1024*1024, backupCount=1)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class AIClient(BaseModel):
    ai_id: str
    model: str
    api_key: str

    async def query(self, content):
        logger.debug(f"Querying {self.ai_id} with content: {content[:50]}")
        process = psutil.Process()
        logger.debug(f"Memory before API call: {process.memory_info().rss / 1024**2:.2f} MB")
        for attempt in range(3):
            try:
                if self.ai_id == 'gpt':
                    client = AsyncOpenAI(api_key=self.api_key)
                    response = await client.chat.completions.create(
                        model=self.model,
                        messages=[{'role': 'user', 'content': content[:50]}],
                        max_tokens=25
                    )
                    content = response.choices[0].message.content[:25]
                    logger.debug(f"API response: {content}")
                    return {'content': content, 'sources': ['https://api.openai.com']}
                return {'content': f'Error: {self.ai_id} not supported'[:25], 'sources': []}
            except Exception as e:
                logger.error(f"AI {self.ai_id} failed: {str(e)}, attempt {attempt+1}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return {'content': f'Error: {str(e)}'[:25], 'sources': []}
        logger.debug(f"Memory after API call: {process.memory_info().rss / 1024**2:.2f} MB")

class THOTH:
    def __init__(self):
        load_dotenv()
        self.clients = {}
        self.active_ais = []
        logger.debug("THOTH initialized")

    async def handle_websocket(self, websocket):
        logger.debug("WebSocket connection opened")
        try:
            async def ping():
                while True:
                    await asyncio.sleep(10)
                    await websocket.ping()
                    logger.debug("Sent WebSocket ping")
            asyncio.create_task(ping())
            async for message in websocket:
                try:
                    data = json.loads(zlib.decompress(message).decode('utf-8'))
                    logger.debug(f"Received message: {data}")
                except Exception as e:
                    logger.error(f"Failed to decompress/parse message: {str(e)}")
                    continue
                if data['type'] == 'add_ai':
                    if data['ai_id'] in self.clients:
                        await websocket.send(zlib.compress(json.dumps({'type': 'error', 'message': f'{data["ai_id"]} already added'}).encode('utf-8')))
                        logger.debug(f"Rejected duplicate AI: {data['ai_id']}")
                        continue
                    if data['ai_id'] != 'gpt':
                        await websocket.send(zlib.compress(json.dumps({'type': 'error', 'message': 'Only GPT supported'}).encode('utf-8')))
                        logger.debug(f"Rejected non-GPT AI: {data['ai_id']}")
                        continue
                    self.clients[data['ai_id']] = AIClient(ai_id=data['ai_id'], model=data['model'], api_key=os.getenv("GPT_API_KEY", ""))
                    self.active_ais.append(data['ai_id'])
                    await websocket.send(zlib.compress(json.dumps({'type': 'ai_added', 'ai_id': data['ai_id'], 'is_primary': True}).encode('utf-8')))
                    logger.debug(f"Added AI: {data['ai_id']}")
                elif data['type'] == 'remove_ai':
                    self.clients.pop(data['ai_id'], None)
                    self.active_ais.remove(data['ai_id']) if data['ai_id'] in self.active_ais else None
                    await websocket.send(zlib.compress(json.dumps({'type': 'ai_removed', 'ai_id': data['ai_id'], 'new_primary': self.active_ais[0] if self.active_ais else None}).encode('utf-8')))
                    logger.debug(f"Removed AI: {data['ai_id']}")
                elif data['type'] == 'message':
                    responses = await self.process_message(data['content'], data.get('target_ai'))
                    for ai_id, response in responses.items():
                        response_str = json.dumps({'type': 'response', 'ai_id': ai_id, **response})
                        chunk_size = 64 * 1024
                        compressed = zlib.compress(response_str.encode('utf-8'))
                        logger.debug(f"Sending response: {response_str[:100]}")
                        for i in range(0, len(compressed), chunk_size):
                            await websocket.send(compressed[i:i+chunk_size])
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            await websocket.send(zlib.compress(json.dumps({'type': 'error', 'message': str(e)[:25]}).encode('utf-8')))
        logger.debug("WebSocket connection closed")

    async def process_message(self, content, target_ai=None):
        logger.debug(f"Processing message: {content[:50]}")
        responses = {}
        for ai_id, client in list(self.clients.items()):
            if target_ai and ai_id != target_ai:
                continue
            response = await client.query(content)
            responses[ai_id] = {'content': response['content'], 'sources': response.get('sources', [])}
            logger.debug(f"Got response from {ai_id}: {response['content']}")
            break
        return responses

    async def start_server(self):
        logger.debug("Starting WebSocket server")
        async with websockets.serve(self.handle_websocket, 'localhost', 3001, max_size=5*1024*1024, max_queue=10, ping_interval=10, ping_timeout=20):
            logger.info('THOTH WebSocket server started on ws://localhost:3001')
            await asyncio.Future()

if __name__ == '__main__':
    thoth = THOTH()
    asyncio.run(thoth.start_server())
