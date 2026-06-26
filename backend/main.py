"""Main FastAPI application."""
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from core.chatbot import chatbot
from data.sample_repo_data import load_demo_repo
from data.sample_incident_data import load_demo_incident

load_dotenv()

app = FastAPI(
    title="RCA Analyzer",
    description="AI-powered root cause analysis for incidents — logs, alarms, and past postmortems",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoadRepoRequest(BaseModel):
    repo_url: str


class ChatRequest(BaseModel):
    message: str


INCIDENT_QUESTIONS = [
    "What is the root cause of this incident?",
    "Walk me through the incident timeline.",
    "Which alarm fired first and what does it indicate?",
    "Have we seen a similar incident before?",
    "What changed right before the outage started?",
    "What are the recommended immediate remediation steps?",
]

REPO_QUESTIONS = [
    "What does this project do? Give me an overview.",
    "Explain the main architecture and design patterns.",
    "What are the key functions and classes?",
    "Show me how authentication is implemented.",
    "Find potential bugs or security issues.",
    "What are the main dependencies?",
]


@app.get("/")
async def root():
    return {
        "name": "RCA Analyzer",
        "version": "1.0.0",
        "status": "operational",
        "llm_provider": os.getenv('LLM_PROVIDER', 'mock'),
        "modes": ["incident", "repo"],
    }


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "loaded": chatbot.is_loaded,
        "mode": chatbot.mode,
    }


@app.post("/api/demo-incident")
async def demo_incident():
    """Load synthetic P1 payment outage for RCA demo."""
    try:
        chatbot.clear()
        demo_data = await load_demo_incident()

        if demo_data['status'] == 'error':
            raise HTTPException(status_code=500, detail=demo_data['message'])

        chatbot.apply_demo_incident_state(demo_data)
        return demo_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Demo incident failed: {str(e)}")


@app.post("/api/load-repo")
async def load_repository(request: LoadRepoRequest):
    try:
        result = await chatbot.load_repository(request.repo_url)
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load repo: {str(e)}")


@app.post("/api/demo")
async def demo_mode():
    try:
        chatbot.clear()
        demo_data = await load_demo_repo()

        if demo_data['status'] == 'error':
            raise HTTPException(status_code=500, detail=demo_data['message'])

        chatbot.current_repo = {'platform': 'github', 'owner': 'pallets', 'repo': 'click'}
        chatbot.mode = 'repo'
        chatbot.repo_info = demo_data['repo_info']
        chatbot.incident_info = None
        chatbot.indexed_files = demo_data['stats']['files_indexed']
        chatbot.total_chunks = demo_data['stats']['total_chunks']
        chatbot.languages = demo_data['stats']['languages']
        chatbot.chat_history = []

        return demo_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Demo failed: {str(e)}")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Empty message")
        result = chatbot.chat(request.message)
        result['timestamp'] = datetime.now().isoformat()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.get("/api/status")
async def get_status():
    return chatbot.get_status()


@app.post("/api/clear")
async def clear_state():
    chatbot.clear()
    return {"status": "cleared"}


@app.get("/api/suggested-questions")
async def get_suggested_questions(mode: str = Query(default="incident")):
    questions = INCIDENT_QUESTIONS if mode == "incident" else REPO_QUESTIONS
    return {"questions": questions, "mode": mode}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
