# Factory Mind AI — Conversational Order Management System
**DSATM Hackathon 2025 · Team Submission**

---

## Project Structure

```
factory_mind_ai/
├── main.py            ← FastAPI backend (routes, in-memory DB, intent routing)
├── models.py          ← Pydantic schemas: Order, QualityLog, AIResponse + intents
├── ai_engine.py       ← OpenAI structured-output wrapper + System Prompt
├── requirements.txt   ← Pinned Python dependencies
├── .env.example       ← Environment variable template
├── start.sh           ← One-command startup script
├── README.md          ← This file
└── static/
    └── index.html     ← Single-page UI (Tailwind CSS + Vanilla JS)
```

---

## Quick Start

### 1. Set your API key
```bash
cp .env.example .env
# Edit .env and paste your OpenAI API key
```

### 2. Install & run
```bash
pip install -r requirements.txt
python main.py
```

### 3. Open browser
```
http://localhost:8000
```

---

## Features

| Feature | How to trigger |
|---|---|
| Create order | *"Order 50 steel brackets, deadline June 20"* |
| Update status → In Review | *"Move order #1 to In Review"* |
| Update status → Accepted | *"Accept order #2"* |
| Log quality note | *"Order #3 passed visual inspection"* |
| List all orders | *"Show all orders"* |
| Filter by status | *"List all accepted orders"* |
| View single order | *"Show order #1"* |

---

## Architecture Decisions

- **gpt-4o-mini** — cheapest capable model; `temperature=0` for deterministic extraction; `max_tokens=256` caps cost per call.
- **Structured Output via `response_format=json_object`** — guarantees parseable JSON, eliminating retry loops.
- **Pydantic v2 models** — strict validation on both AI output and API I/O.
- **In-memory storage** — Python list + dict; zero infrastructure overhead for hackathon scope.
- **Single HTML file** — no build step, instant deployment, Tailwind via CDN.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the frontend |
| `GET` | `/orders` | Returns all orders (JSON) |
| `POST` | `/chat` | Processes a chat message, returns reply + updated orders |
| `GET` | `/docs` | FastAPI auto-generated Swagger UI |
