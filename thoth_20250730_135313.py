#!/usr/bin/env python3
import asyncio, websockets, json, uuid, requests
from datetime import datetime
from config import CLAUDE_API_KEY
print("🧠 THOTH - AI Multi-Agent Chat System\nInitializing AI connections...")
messages = []; users = {}; ai_models = {}
async def query_claude(prompt, model):
    try:
        headers = {"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2024-10-22", "content-type": "application/json"}
        data = {"model": model, "max_tokens": 1000, "messages": [{"role": "user", "content": prompt}]}
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except Exception as e:
        return f"Claude error: {str(e)} - Response: {response.text if 'response' in locals() else 'No response'}"
async def handle_client(websocket):
    user_id = str(uuid.uuid4())[:8]
    users[user_id] = {"name": f"User-{user_id}", "type": "human"}
    ai_models[user_id] = "claude-3-sonnet-20240229"
    print(f"🔗 User connected: {users[user_id]['name']}")
    try:
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "message":
                msg = {"id": str(uuid.uuid4()), "content": data["content"], "sender": users[user_id]["name"], "timestamp": datetime.now().isoformat()}
                messages.append(msg)
                print(f"📨 {msg['sender']}: {msg['content']}")
                await websocket.send(json.dumps(msg))
                if "claude" in msg["content"].lower():
                    claude_response = await query_claude(msg["content"], ai_models[user_id])
                    claude_msg = {"id": str(uuid.uuid4()), "content": claude_response, "sender": "Claude", "timestamp": datetime.now().isoformat()}
                    messages.append(claude_msg)
                    print(f"📨 Claude: {claude_response}")
                    await websocket.send(json.dumps(claude_msg))
            elif data["type"] == "addAI":
                model = "claude-3-sonnet-20240229" if data["aiType"].lower() == "claude" else "claude-3-opus-20240229"
                ai_models[user_id] = model
                msg = {"id": str(uuid.uuid4()), "content": f"Added AI: {data['aiType']} ({model})", "sender": "THOTH", "timestamp": datetime.now().isoformat()}
                messages.append(msg)
                print(f"🤖 Added AI: {data['aiType']} ({model})")
                await websocket.send(json.dumps(msg))
    except Exception as e:
        print(f"❌ Client disconnected: {e}")
        del users[user_id]; del ai_models[user_id]
async def main():
    print("🚀 THOTH Multi-AI Chat running on 0.0.0.0:3001")
    async with websockets.serve(handle_client, "0.0.0.0", 3001):
        await asyncio.Future()
if __name__ == "__main__":
    asyncio.run(main())
