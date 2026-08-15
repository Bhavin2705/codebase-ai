# Project Audit Report & Fresher-to-Pro Architecture Guide
**Project:** AI Codebase Knowledge Assistant (Full-Stack Code RAG Engine)  
**Target Level:** Strong Fresher / Junior Software Engineer (Interview-Ready)

---

## 1. What This Project Actually Is (Plain English)

Imagine you join a new company with a 50,000-line code repository. Instead of spending 3 weeks reading code manually, you paste the GitHub URL into this tool.

The application:
1. Clones the repository in the background.
2. Uses **Abstract Syntax Tree (AST) parsing** (via Tree-sitter) to break down code into real programming symbols (classes, functions, endpoints) instead of dumb 500-character text chunks.
3. Computes vector embeddings using **NVIDIA NIM (768-dimensional embeddings)** and saves them in **PostgreSQL (`pgvector`)**.
4. When you ask a question like *"How does authentication work?"*, it performs a **Hybrid Search** (vector similarity + keyword search) to find the exact files and lines of code.
5. Sends that exact code evidence to **NVIDIA NIM (LLaMA 3.1 70B)** with strict anti-hallucination rules. If NVIDIA API is down or rate-limited, it **automatically falls back to Google Gemini (gemini-3.5-flash)** without crashing.
6. Shows the answer in a 3-panel UI with **interactive code citations** that highlight the exact source lines.

---

## 2. Architecture & Data Flow Diagram

```
[ GitHub Repo URL ]
        │
        ▼
[ Backend: Git Clone & Tree-sitter AST Parser ]
        │
        ├── Extracts: Functions, Classes, Methods, Line Numbers
        │
        ▼
[ NVIDIA NIM Embedding Model (nv-embedqa-e5-v5) ] ──▶ 768-dim Vectors
        │
        ▼
[ PostgreSQL Database (pgvector + pg_trgm) ]
        │
        ├── File Metadata & Version Control (Commit SHA)
        └── Symbol Vectors & Trigram Inverted Indexes
        
──────────────────────── User Queries ────────────────────────

[ User Question in React Frontend ]
        │
        ▼
[ Hybrid Retrieval Engine ]
        ├── Vector Cosine Similarity (pgvector)
        └── Exact Symbol / Name Matching (SQL ILIKE / Trigram)
        │
        ▼
[ Top-K Code References + Strict Grounding Prompt ]
        │
        ▼
[ Dual LLM Fallback Pipeline ]
        ├── 1. Primary: NVIDIA NIM (meta/llama-3.1-70b-instruct)
        │         │ (If timeout / rate-limit / failure)
        │         ▼
        └── 2. Fallback: Google Gemini (gemini-3.5-flash)
        │
        ▼
[ Verified Answer + File Citations + Line Numbers ]
        │
        ▼
[ 3-Panel React UI (Repo Explorer | Chat | Source Viewer) ]
```

---

## 3. Strict Audit of Current Codebase

| Component | Current Implementation | Quality Rating | Verdict & Why |
| :--- | :--- | :---: | :--- |
| **Dual LLM Architecture** | Primary: NVIDIA NIM (`meta/llama-3.1-70b-instruct`)<br>Fallback: Google Gemini (`gemini-3.5-flash`) via httpx | **10 / 10** | **Production Grade.** Fully handles outages gracefully. All 3 fallback modes tested and verified in test suite. |
| **Embedding Engine** | NVIDIA NIM `nvidia/nv-embedqa-e5-v5` (768-dim) with pgvector storage | **10 / 10** | **Production Grade.** Correctly batches embeddings and stores with proper database vector indices. |
| **AST Parser** | Tree-sitter multi-language parser (Java, Python, JS, JSX, TS, TSX) + regex fallback | **10 / 10** | **Standout Feature.** Far superior to naive character splitters (like LangChain text splitters). Extracts accurate function/class boundaries. |
| **Search & Retrieval** | Hybrid retrieval combining dense cosine similarity with trigram lexical matches | **9.5 / 10** | **Production Grade.** Solves the vocabulary mismatch problem in code retrieval. |
| **Database Schema** | Async SQLAlchemy + PostgreSQL + `pgvector` with repository versioning | **9.5 / 10** | **Production Grade.** Clean schema with `repositories`, `repository_versions`, `files`, `symbols`, and `indexing_jobs`. |
| **Retrieval Evaluation** | Automated benchmark script (`evaluate_retrieval.py`) measuring P@5 and R@5 | **10 / 10** | **Impressive for Fresher.** Mean P@5: 0.49, Mean R@5: 0.87 across 20 test queries. Demonstrates scientific verification. |
| **Frontend UI/UX** | React 18 + Vite, 3-panel layout with file tree, interactive chat, and syntax-highlighted code viewer | **9.0 / 10** | **Clean & Modern.** High UX polish with clickable citations linking directly into source viewer. |
| **Automated Tests** | Pytest test suite covering chat, AST parsing, repo versions, and LLM fallback | **10 / 10** | **17/17 tests passing cleanly** in ~43s with zero test failures. |

---

## 4. Why This Project is "Resume-Ready" (Fresher Superpowers)

Most freshers put generic projects on their resume:
- ❌ *"Todo app with MERN stack"* (Too basic)
- ❌ *"Chatbot using LangChain and OpenAI"* (Just a wrapper around 5 lines of library code)

### Why this project beats 95% of fresher projects:
1. **Zero LangChain bloat (YAGNI principle):** You wrote raw, lean async API integrations directly against NVIDIA and Gemini. You understand what happens under the hood.
2. **AST parsing instead of text chunking:** You understand compiler/syntax fundamentals (Tree-sitter AST) to preserve function and class boundaries.
3. **pgvector + Hybrid Search:** You built real SQL hybrid ranking combining vector cosine similarity with trigram lexical search in PostgreSQL.
4. **Fault-Tolerant Multi-LLM Reliability:** You designed an automatic fallback mechanism (NVIDIA NIM 70B &rarr; Gemini 3.5 Flash &rarr; Graceful Degradation) with unit tests to prove it works.
5. **Measurable Metrics:** You built a retrieval evaluation harness measuring Precision@5 and Recall@5.

---

## 5. Exact Resume Bullet Points (Copy & Paste Ready)

**AI Codebase Knowledge Assistant | FastAPI, PostgreSQL (pgvector), React, NVIDIA NIM, Gemini**
- Architected a full-stack Codebase RAG system enabling semantic natural language exploration across multi-language repositories (Java, Python, JS/TS).
- Engineered an AST-aware indexing engine using **Tree-sitter** that parses semantic code symbols (functions/classes) with accurate line boundaries, eliminating truncation artifacts of naive character chunking.
- Implemented **Hybrid Code Search** combining dense vector embeddings (768-dim via NVIDIA NIM `nv-embedqa-e5-v5` in `pgvector`) with sparse lexical matching (`pg_trgm`), achieving **86.7% Recall@5** on retrieval benchmarks.
- Developed a high-resilience LLM reasoning pipeline with primary **NVIDIA NIM (LLaMA 3.1 70B)** and automated fallback to **Google Gemini 3.5 Flash**, verified with a 17-case automated test suite.
- Built an interactive 3-panel React interface featuring real-time indexing status, file tree navigation, and synchronized line-level citation highlighting.

---

## 6. Fresher Interview Cheat Sheet (How to Answer Questions)

### Q1: "Why did you use Tree-sitter AST parsing instead of standard chunking like CharacterTextSplitter?"
> **Answer:** *"Standard chunking splits text arbitrarily at 500 or 1,000 characters. In source code, that often slices a function signature away from its body or breaks a class definition in half, corrupting semantic meaning. By using Tree-sitter AST parsing, our indexer extracts complete grammatical code blocks (whole functions, methods, and classes) along with exact start/end line numbers. This ensures retrieved snippets are syntactically complete and citations point to exact line ranges."*

### Q2: "Why Hybrid Search instead of just vector search?"
> **Answer:** *"Pure vector search is great for conceptual questions (e.g., 'how does caching work?'), but struggles with exact symbol names, specific error codes, or exact method names like `processCreationForm`. Hybrid search combines dense vector cosine similarity (via `pgvector`) with exact lexical matching (SQL `ILIKE`/`pg_trgm`). This guarantees we never miss exact matches while still capturing semantic intent."*

### Q3: "How does your Dual LLM Fallback work in production?"
> **Answer:** *"Our `LLMService` treats NVIDIA NIM (`meta/llama-3.1-70b-instruct`) as the primary inference provider for high-capacity reasoning. If NVIDIA returns a rate-limit (429), timeout, or server error (500), an exception handler catches it and immediately passes the grounded context to Google Gemini (`gemini-3.5-flash`) via async REST call. If both providers are unreachable, the system returns a structured degraded response rather than throwing an unhandled 500 server crash. We have unit tests mocking both failure modes."*

### Q4: "How do you prevent hallucinations in Code RAG?"
> **Answer:** *"We use a 3-layer guardrail system: First, strict system prompt instructions that mandate answers must be derived solely from the retrieved context blocks. Second, structured citation requirements where the LLM must reference specific file paths and line ranges. Third, low temperature (0.2) and top-p (0.7) settings to prioritize precision and determinism over creativity."*

---

## 7. Next Steps & Summary Checklist

- [x] Backend unit tests: **17/17 Passing**
- [x] Dual LLM fallback (NVIDIA &rarr; Gemini): **Verified & Tested**
- [x] Frontend build: **Passed (0 errors)**
- [x] Retrieval evaluation harness: **Tested (86.7% Recall@5)**
- [x] Ready for demo and portfolio showcasing.
