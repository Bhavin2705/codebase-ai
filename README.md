# AI Codebase Assistant

## Problem Statement

Developers spend a significant amount of time understanding unfamiliar codebases before they can make changes or fix issues. Reading source files manually becomes difficult as projects grow in size and complexity.

This project provides an AI-powered assistant that indexes a source code repository and allows developers to ask questions in natural language. Instead of searching through multiple files manually, users receive context-aware answers with references to the relevant source files.

---

## Features

- Import and index a local or Git repository
- Parse source code using Tree-sitter
- Generate embeddings for semantic code search
- Ask questions about the indexed codebase in natural language
- Retrieve relevant code snippets before generating responses
- Display file references with AI responses
- Repository statistics and file exploration
- REST API built using FastAPI
- React-based frontend for interacting with the assistant

---

## Architecture

```text
                  +------------------+
                  |   React Frontend |
                  +---------+--------+
                            |
                            | HTTP
                            v
                  +------------------+
                  |  FastAPI Backend |
                  +---------+--------+
                            |
         +------------------+------------------+
         |                  |                  |
         v                  v                  v
 +---------------+  +---------------+  +---------------+
 | Git Service   |  | Parser Service|  | LLM Service   |
 | Clone/Read    |  | Tree-sitter   |  | AI Responses  |
 +-------+-------+  +-------+-------+  +-------+-------+
         |                  |                  |
         +------------------+------------------+
                            |
                            v
                  +------------------+
                  | Embedding Service|
                  +---------+--------+
                            |
                            v
                  +------------------+
                  | PostgreSQL +     |
                  | pgvector Storage |
                  +------------------+
```

---

## Tech Stack

### Frontend

- React 18
- Vite
- React Router
- Lucide React

### Backend

- FastAPI
- Python
- SQLAlchemy
- PostgreSQL
- pgvector
- Tree-sitter
- GitPython

### AI

- OpenAI API
- Google Gemini API
- Vector Embeddings

### Database

- PostgreSQL
- pgvector

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <repository-url>
cd codebase-ai-main
```

### 2. Start PostgreSQL

```bash
docker-compose up -d
```

### 3. Configure environment variables

Create a `.env` file inside the backend directory using `.env.example`.

Example variables:

```text
OPENAI_API_KEY=your_api_key
GOOGLE_API_KEY=your_api_key
DATABASE_URL=your_database_url
```

### 4. Install backend dependencies

```bash
cd backend

python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 5. Start the backend

```bash
uvicorn app.main:app --reload
```

The backend will run on:

```
http://localhost:8000
```

---

### 6. Install frontend dependencies

```bash
cd frontend

npm install
```

### 7. Start the frontend

```bash
npm run dev
```

The frontend will run on:

```
http://localhost:5173
```

---

## Known Limitations

- Supports only the programming languages configured in the parser service.
- AI responses depend on the quality of the retrieved context and selected language model.
- Large repositories require additional indexing time before queries can be answered.
- Repository data is stored in memory during runtime, making the current implementation more suitable for an MVP than production deployment.
- Authentication and role-based access control are not implemented.
- The application currently focuses on understanding existing code rather than editing or refactoring it automatically.