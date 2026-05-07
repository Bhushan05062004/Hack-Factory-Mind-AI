# Factory Mind AI — AI-Powered Order Management System

> Conversational order-tracking for precision manufacturing, powered by a **hybrid AI architecture** using Google Gemini.

---

## 🏗️ Architecture

**Hybrid AI** — LLM is used *only* for extracting structured data from free-text orders and natural-language queries. Status changes, quality logs, and most business logic are handled by a **deterministic regex rule engine** (zero token cost).

**RAG (Retrieval-Augmented Generation)** — FAISS vector stores index the product catalog and SOPs. When a user mentions a product, the system retrieves relevant snippets and injects them into the LLM prompt.

```
User Message → Regex Rule Engine → (match?) → Execute directly (0 tokens)
                                  → (no match?) → RAG Retrieval → Gemini API → Function Call → Execute
```

### Key Features
- **3 Roles**: User (stakeholder), Operator (ops team), Quality (QC team)
- **Token Efficient**: LLM calls never exceed 500 input tokens; ≤200 output tokens
- **Stateless API**: No conversation history sent to LLM; all state in SQLite
- **Function Calling**: 6 Gemini tool declarations for structured extraction
- **RBAC**: Users can't see Accepted status, quality notes, or SOP details

---

## 📋 Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Gemini API Key** — [Get one free](https://aistudio.google.com/apikey)

---

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env → set your GEMINI_API_KEY

# 2. Run the demo script
chmod +x demo.sh
./demo.sh
```

This will:
- Build and start API + Frontend containers
- Seed 3 demo users, 10 products, 5 SOPs
- Build FAISS vector indices
- Open http://localhost:3000

### Option 2: Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env .env  # or create with GEMINI_API_KEY
python seed.py   # Seed demo data + build FAISS indices
python app.py    # Start API on :8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev      # Start UI on :3000
```

---

## 👥 Demo Accounts

| Email | Role | Capabilities |
|---|---|---|
| `alice@demo.com` | **User** | Create orders, query own orders, cancel within window |
| `bob@demo.com` | **Operator** | Update status, query all orders, view SOPs |
| `carol@demo.com` | **Quality** | Log quality notes, update status, view SOPs |

---

## 💬 Usage Examples

### As Customer (alice@demo.com)
- *"I need 200 titanium aerospace-grade flanges with 80mm bore, deliver by 2025-07-20"*
- *"Show me all my orders"*
- *"Cancel order #1"*
- *"Do you have steel brackets?"*

### As Operator (bob@demo.com)
- *"Move order #1 to In Review"*
- *"Accept order #2"*
- *"Show all received orders"*
- *"What is the inspection procedure for flanges?"*

### As Quality (carol@demo.com)
- *"Quality update on order #1 — passed visual inspection, no surface defects"*
- *"Order #3 failed dimensional check"*

---

## 📊 Token Usage & Metrics

```bash
# View cumulative token usage
curl http://localhost:8000/metrics
```

Returns:
```json
{
  "total_input_tokens": 1250,
  "total_output_tokens": 380,
  "total_tokens": 1630,
  "total_calls": 5,
  "estimated_cost_usd": 0.000208
}
```

---

## 🔌 API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/login` | No | Email-based login → JWT |
| `POST` | `/chat` | JWT | Process user utterance |
| `GET` | `/orders` | JWT | List orders (RBAC-filtered) |
| `GET` | `/metrics` | No | Cumulative token usage |
| `GET` | `/health` | No | Health check |
| `GET` | `/docs` | No | Swagger UI |

---

## 🧪 Testing

```bash
cd backend
pip install -r requirements.txt
cd ..
pytest tests/ -v
```

Test coverage:
- 30-utterance extraction benchmark (≥90% accuracy)
- Auth and RBAC enforcement
- Order lifecycle
- Response structure validation

---

## 📁 Project Structure

```
├── backend/
│   ├── app.py              # FastAPI entrypoint, routers
│   ├── auth.py             # JWT utils, RBAC dependency
│   ├── db.py               # SQLite connection + CRUD
│   ├── llm.py              # Gemini wrapper, regex engine, function schemas
│   ├── products.py         # Product embedding + FAISS search
│   ├── sops.py             # SOP embedding + FAISS search
│   ├── schemas.py          # Pydantic request/response models
│   ├── seed.py             # Demo data seeder
│   ├── utils.py            # Token counter, datetime helpers
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # Login, Chat, Dashboard, OperatorDashboard, ProductSearch
│   │   ├── hooks/          # useAuth (login, token, role context)
│   │   └── App.tsx         # Main app with routing
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   ├── package.json
│   └── Dockerfile
├── tests/
│   ├── conftest.py         # Fixtures
│   ├── test_api.py         # API + RBAC tests
│   └── test_llm_extraction.py  # 30-utterance benchmark
├── docker-compose.yml
├── demo.sh
├── .env.example
└── README.md
```

---

## 🔧 Extending

### Add a new product
```bash
# Edit backend/seed.py → add to DEMO_PRODUCTS list, then:
docker exec nova-nexus-api python /app/seed.py --rebuild
```

### Add a new SOP
```bash
# Edit backend/seed.py → add to DEMO_SOPS list, then:
docker exec nova-nexus-api python /app/seed.py --rebuild
```

---

## 🏛️ Technology Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn, Pydantic v2
- **AI**: Google Gemini API (function-calling), sentence-transformers (all-MiniLM-L6-v2)
- **Vector DB**: FAISS (in-process)
- **Database**: SQLite (WAL mode)
- **Auth**: python-jose (JWT/HS256)
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS
- **Containerisation**: Docker Compose
