# AI Codebase Knowledge Assistant

A full-stack developer assistant that indexes Git repositories and answers architectural and implementation questions with line-level source code citations. It uses AST/syntax parsing, PostgreSQL pgvector embeddings, and hybrid retrieval to provide grounded code explanations.

## Key Features

- **Automated Repository Ingestion**: Clones public GitHub repos and extracts symbols (functions, classes, routes, models) with exact line ranges.
- **Hybrid RAG Engine**: Combines pgvector cosine similarity, lexical matching, and structural file prioritization (e.g. `package.json`, `README.md`).
- **Resilient LLM Pipeline**: Primary generation via NVIDIA NIM (`meta/llama-3.1-8b-instruct`) with automatic fallback to Google Gemini (`gemini-3.6-flash`).
- **Interactive 3-Panel UI**: File explorer, SSE streaming chat with thought process disclosure, and synchronized source code viewer with citation navigation.
- **Bulk COPY Ingestion**: High-throughput symbol inserts via PostgreSQL `asyncpg` COPY protocol.

## Tech Stack

- **Backend**: FastAPI (Python 3.10+), SQLAlchemy 2.0, `asyncpg`, `pgvector`, HTTPX
- **Frontend**: React 18, Vite, React Router 7, Lucide Icons, Vanilla CSS
- **Database**: PostgreSQL 16 with `pgvector` & `pg_trgm` extensions
- **Models**: NVIDIA NIM (`nvidia/nv-embedqa-e5-v5` embeddings, `meta/llama-3.1-8b-instruct`), Google Gemini (`gemini-3.6-flash`)

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (repositories, chat, health)
│   │   ├── models/       # SQLAlchemy ORM models (Repository, File, Symbol, Chat)
│   │   └── services/     # Git, CodeParser, Embedding, Retrieval, LLM, Indexing services
│   └── tests/            # Pytest test suite (28 tests)
├── frontend/
│   └── src/
│       ├── components/   # Chat, Evidence, Navigation, Overview, Layout components
│       └── App.jsx       # App routing & workspace state
```

## Setup & Environment

### Backend Configuration (`backend/.env`)

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codebase_ai
NVIDIA_NIM_API_KEY=nvapi-your-key
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_CHAT_MODEL=meta/llama-3.1-8b-instruct
NVIDIA_NIM_EMBED_MODEL=nvidia/nv-embedqa-e5-v5
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-3.6-flash
FRONTEND_URL=http://localhost:5173
API_ACCESS_KEY=
ENVIRONMENT=development
```

### Running Locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`, backend API at `http://localhost:8000`.

## How the RAG Pipeline Works

1. **Indexing**: Scans source files, parses functions/classes/routes with AST and syntax boundary matching, batches 768-dim embeddings via NVIDIA NIM, and writes records via `asyncpg` COPY.
2. **Retrieval**: Executes parallel pgvector vector search + lexical ILIKE queries, applies structural file bonuses for overview questions, and caps per-file slice counts for diversity.
3. **Synthesis & Streaming**: Formats reference blocks with exact line numbers, streams tokens via SSE from NVIDIA NIM (or fallback Gemini), and persists conversation history in PostgreSQL.

## Benchmarks & Evaluation

- **Evaluation Metric**: 90.0% Mean Recall@5 across 20 reference code queries (`scripts/evaluate_retrieval.py`).
- **Ingestion Speed**: `asyncpg` COPY reduced symbol database writes from ~11.95s to sub-second on medium repositories.
- **Test Suite**: 30 passing unit and integration tests (`python -m pytest`).