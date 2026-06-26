# RCA Analyzer — Demo MVP

AI-powered root cause analysis for distributed system incidents. Correlate logs, alarms, and past postmortems to reduce MTTR.

## Demo Scenario

**INC-2026-0847** — Payment Service Degradation (P1)
- Checkout failure rate spikes to 42%
- 4 microservices: payment-api, order-service, postgres-primary, redis-cache
- 4 firing alarms with correlated timeline
- Similar past incident: INC-2025-1203 (Black Friday pool exhaustion)

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

API runs at `http://localhost:8001` (port 8000 is often used by other tools)

> **Note:** If you get 404 errors, make sure this FastAPI backend is running — not another app on the same port.

### Frontend

```bash
cd frontend
npm install
npm start
```

UI runs at `http://localhost:3000`

### GitHub Codespaces / remote dev

If the browser shows `ERR_CONNECTION_REFUSED` on `localhost:8001`, the frontend is calling your **local laptop** instead of the Codespace server.

**Fix (already in latest code):** API calls use relative paths (`/api/...`) and the React dev proxy forwards to the backend inside the Codespace.

**Run both services in the Codespace:**

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
PORT=8001 python main.py

# Terminal 2 — frontend
cd frontend
npm install
npm start
```

Open the **port 3000** URL from the Codespaces Ports tab (not `localhost:8001` in the browser).

> Do **not** set `REACT_APP_API_URL=http://localhost:8001` in Codespaces — that breaks remote access.

### Demo Flow

1. Open the app → click **Load Demo Incident**
2. Wait for evidence indexing (~30s first run while embedding model downloads)
3. Try suggested questions:
   - "What is the root cause of this incident?"
   - "Walk me through the incident timeline"
   - "Have we seen a similar incident before?"
   - "What are the recommended remediation steps?"

## LLM Configuration (optional)

Works out of the box with a **smart mock** that returns evidence-backed RCA answers.

For real LLM responses, set in `backend/.env`:

```env
LLM_PROVIDER=ollama    # or anthropic, openai
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```

For Ollama: `ollama pull llama3` and ensure Ollama is running.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/demo-incident` | Load synthetic P1 incident |
| `POST /api/chat` | Ask RCA questions |
| `GET /api/suggested-questions?mode=incident` | Get starter prompts |
| `POST /api/clear` | Reset session |
| `POST /api/load-repo` | Legacy: analyze GitHub repo |

## Architecture

```
Logs + Alarms + Postmortems
        ↓
   log_chunker.py (semantic chunks)
        ↓
   vector_store.py (MiniLM + FAISS)
        ↓
   chatbot.py (RAG + LLM)
        ↓
   Evidence-backed RCA response
```

## Harris IoT Ideathon 2026
