import uuid
import re
from typing import List, Dict, Any, Tuple
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.chat import Chat as ChatModel
from app.schemas.chat import ChatRequest, ChatResponse, CitationItem
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService
from app.api.repositories import REPO_DB, ensure_default_repository

router = APIRouter(prefix="/chat", tags=["Chat"])
llm_service = LLMService()
embedding_service = EmbeddingService()

import time

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)

@router.post("", response_model=ChatResponse)
async def chat_query(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    start_time = time.time()
    ensure_default_repository()
    repo_id = payload.repository_id or "repo-1"
    repo_data = REPO_DB.get(repo_id) or REPO_DB.get("repo-1")

    files_dict = repo_data.get("files", {}) if repo_data else {}
    lowercase_question = payload.question.strip().lower()

    # 1. Direct handling for standard conversational greetings
    greetings_list = ["hi", "hello", "hey", "hi there", "hello there", "good morning", "good evening", "howdy", "thanks", "thank you"]
    if lowercase_question in greetings_list or lowercase_question.rstrip("!.") in greetings_list:
        execution_time_ms = round((time.time() - start_time) * 1000, 1)
        chat_id = f"chat-{uuid.uuid4().hex[:8]}"
        greeting_reply = "Hello! I am your AI Codebase Knowledge Assistant. Ask me anything about this repository's architecture, functions, API endpoints, or code logic."
        return {
            "id": chat_id,
            "repository_id": repo_id,
            "question": payload.question,
            "answer": greeting_reply,
            "confidence": "high",
            "citations": [],
            "execution_time_ms": execution_time_ms,
            "thought_process": {
                "query_type": "Conversational Greeting",
                "total_files_scanned": len(files_dict),
                "contexts_retrieved": 0,
                "contexts_analyzed": [],
                "execution_time_ms": execution_time_ms,
                "keywords_extracted": [],
                "llm_engine": "Instant Router"
            }
        }

    is_overview_query = any(phrase in lowercase_question for phrase in [
        "what is this repo about", "repo about", "repository about", "overview", "what does this repo do",
        "architecture", "explain repo", "explain repository", "project structure", "readme",
        "workspace", "workspace about", "what is this workspace about", "project about", "explain project",
        "explain workspace", "what is this project about", "what does this project do", "summary", "about this"
    ])

    # 2. Dense Vector Embedding Generation
    query_vector = []
    try:
        query_vector = await embedding_service.generate_embedding(payload.question)
    except Exception as embed_err:
        print(f"Embedding generation notice: {embed_err}")

    raw_tokens = set(re.findall(r"[A-Za-z0-9_]+", lowercase_question))
    stop_words = {"what", "how", "does", "the", "and", "for", "this", "repo", "repository", "workspace", "project", "where", "are", "code", "explain", "about", "is", "a", "an", "in", "of", "to"}
    query_terms = [t for t in raw_tokens if t not in stop_words and len(t) >= 2]

    repo_meta = {
        "name": repo_data.get("name", "Workspace"),
        "language": repo_data.get("language", "Multi-Language"),
        "all_files": list(files_dict.keys()),
        "total_files": len(files_dict)
    }

    scored_files: List[Dict[str, Any]] = []

    # 3. Dense Vector & AST Hybrid Scoring
    for file_path, file_data in files_dict.items():
        content = file_data.get("content", "")
        file_path_lower = file_path.lower()
        content_lower = content.lower()
        symbols = file_data.get("symbols", [])
        symbol_names = [s.get("name", "").lower() for s in symbols]

        # A. Semantic Vector Score (0.0 to 1.0)
        file_vector = file_data.get("embedding")
        vector_score = 0.0
        if query_vector and file_vector:
            vector_score = max(0.0, cosine_similarity(query_vector, file_vector))

        # B. AST Symbol & Path Match Score
        lexical_score = 0
        for term in query_terms:
            if term in file_path_lower.split("/")[-1]:
                lexical_score += 40
            elif term in file_path_lower:
                lexical_score += 15

            if any(term in sym for sym in symbol_names):
                lexical_score += 25

            if term in content_lower:
                lexical_score += min(content_lower.count(term), 5)

        # Combined Hybrid Score
        final_score = (vector_score * 100.0) + lexical_score

        if final_score > 0 or is_overview_query:
            lines = content.split("\n")
            scored_files.append({
                "score": final_score,
                "context": {
                    "name": file_path.split("/")[-1],
                    "file_path": file_path,
                    "signature": f"file {file_path}",
                    "start_line": 1,
                    "end_line": min(len(lines), 150),
                    "source_code": content[:2500]
                }
            })

    scored_files.sort(key=lambda item: item["score"], reverse=True)
    max_context_count = 6 if not is_overview_query else 4
    contexts = [scored_item["context"] for scored_item in scored_files[:max_context_count]]

    if not contexts:
        added_paths = set()
        for file_path, file_data in files_dict.items():
            if file_path not in added_paths:
                content = file_data.get("content", "")
                lines = content.split("\n")
                symbols = file_data.get("symbols", [])
                symbol_name = symbols[0].get("name") if symbols else file_path.split("/")[-1]
                contexts.append({
                    "name": symbol_name,
                    "file_path": file_path,
                    "signature": f"file {file_path}",
                    "start_line": 1,
                    "end_line": min(len(lines), 30),
                    "source_code": content[:300]
                })
                added_paths.add(file_path)
                if len(contexts) >= 2:
                    break

    rag_result = await llm_service.generate_rag_response(payload.question, contexts, repo_meta)
    execution_time_ms = round((time.time() - start_time) * 1000, 1)

    is_simple_query = len(payload.question.split()) <= 3 and not is_overview_query
    analyzed_paths = [context_item["file_path"] for context_item in contexts]
    thought_process = {
        "query_type": "Fast Query Path" if is_simple_query else ("Workspace Overview" if is_overview_query else "Targeted Code RAG"),
        "total_files_scanned": len(files_dict),
        "contexts_retrieved": len(contexts),
        "contexts_analyzed": analyzed_paths,
        "execution_time_ms": execution_time_ms,
        "keywords_extracted": query_terms,
        "llm_engine": f"NVIDIA NIM ({llm_service.nim_model})" if (llm_service.nim_api_key and llm_service.nim_api_key.startswith("nvapi-")) else f"Gemini ({llm_service.gemini_model})"
    }

    chat_id = f"chat-{uuid.uuid4().hex[:8]}"

    try:
        if repo_id and repo_id.startswith("repo-"):
            repository_uuid = uuid.uuid4()
        else:
            repository_uuid = uuid.UUID(repo_id)

        chat_record = ChatModel(
            id=uuid.uuid4(),
            repository_id=repository_uuid,
            question=payload.question,
            answer=rag_result["answer"],
            confidence=rag_result["confidence"],
            citations=rag_result["citations"]
        )
        db.add(chat_record)
        await db.commit()
    except Exception as db_err:
        print(f"AsyncSession Chat DB Notice: {db_err}")

    return {
        "id": chat_id,
        "repository_id": repo_id,
        "question": payload.question,
        "answer": rag_result["answer"],
        "confidence": rag_result["confidence"],
        "citations": [
            CitationItem(**cite) for cite in rag_result["citations"]
        ],
        "execution_time_ms": execution_time_ms,
        "thought_process": thought_process
    }

