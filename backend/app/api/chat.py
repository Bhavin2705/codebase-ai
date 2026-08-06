import uuid
import time
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.chat import Chat as ChatModel
from app.schemas.chat import ChatRequest, ChatResponse, CitationItem
from app.services.llm_service import LLMService
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/chat", tags=["Chat"])
llm_service = LLMService()

@router.post("", response_model=ChatResponse)
async def chat_query(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    start_time = time.time()
    repo_id = payload.repository_id or "repo-1"
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
                "total_files_scanned": 0,
                "contexts_retrieved": 0,
                "contexts_analyzed": [],
                "execution_time_ms": execution_time_ms,
                "keywords_extracted": [],
                "llm_engine": "Instant Router"
            }
        }

    # 2. Retrieve Hybrid Contexts using RetrievalService and Database Session
    contexts, repo_meta = await retrieval_service.retrieve_contexts(
        question=payload.question,
        repository_id=repo_id,
        db=db,
        top_k=5
    )

    # 3. Generate RAG Response from LLM Service
    rag_result = await llm_service.generate_rag_response(payload.question, contexts, repo_meta)
    execution_time_ms = round((time.time() - start_time) * 1000, 1)

    is_overview_query = any(phrase in lowercase_question for phrase in [
        "what is this repo about", "repo about", "repository about", "overview", "what does this repo do",
        "architecture", "explain repo", "explain repository", "project structure", "readme",
        "workspace", "workspace about", "what is this workspace about", "project about", "explain project",
        "explain workspace", "what is this project about", "what does this project do", "summary", "about this"
    ])
    is_simple_query = len(payload.question.split()) <= 3 and not is_overview_query
    analyzed_paths = [context_item["file_path"] for context_item in contexts]

    thought_process = {
        "query_type": "Fast Query Path" if is_simple_query else ("Workspace Overview" if is_overview_query else "Targeted Code RAG"),
        "total_files_scanned": repo_meta.get("total_files", len(contexts)),
        "contexts_retrieved": len(contexts),
        "contexts_analyzed": analyzed_paths,
        "execution_time_ms": execution_time_ms,
        "keywords_extracted": [],
        "llm_engine": f"NVIDIA NIM ({llm_service.nim_model})" if (llm_service.nim_api_key and llm_service.nim_api_key.startswith("nvapi-")) else f"Gemini ({llm_service.gemini_model})"
    }

    chat_id = f"chat-{uuid.uuid4().hex[:8]}"

    # 4. Save Chat History Record
    try:
        try:
            repository_uuid = uuid.UUID(repo_id)
        except ValueError:
            repository_uuid = uuid.uuid4()

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
