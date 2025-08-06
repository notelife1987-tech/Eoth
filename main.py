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
