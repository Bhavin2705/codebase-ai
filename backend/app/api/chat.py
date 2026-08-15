import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import verify_api_key
from app.models.repository import Repository
from app.models.chat import Chat as ChatModel
from app.schemas.chat import ChatRequest, ChatResponse, CitationItem
from app.services.llm_service import LLMService
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/chat", tags=["Chat"])
llm_service = LLMService()

async def _resolve_repository(repo_id_input: str, db: AsyncSession) -> Repository:
    repo = None
    try:
        parsed_uuid = uuid.UUID(repo_id_input)
        stmt = select(Repository).where(Repository.id == parsed_uuid)
        repo = (await db.execute(stmt)).scalars().first()
    except ValueError:
        stmt = select(Repository).where(Repository.name.ilike(f"%{repo_id_input}%"))
        repo = (await db.execute(stmt)).scalars().first()

    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Repository not found: {repo_id_input}")
    return repo

@router.post("", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat_query(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    start_time = time.time()
    raw_repo_id = payload.repository_id or "repo-1"
    repo = await _resolve_repository(raw_repo_id, db)
    repo_id_str = str(repo.id)

    question_text = payload.question.strip().lower()

    greetings = ["hi", "hello", "hey", "hi there", "hello there", "good morning", "good evening", "howdy", "thanks", "thank you"]
    if question_text in greetings or question_text.rstrip("!.") in greetings:
        elapsed = round((time.time() - start_time) * 1000, 1)
        chat_id = f"chat-{uuid.uuid4().hex[:8]}"
        reply = "Hello! I am your AI Codebase Knowledge Assistant. Ask me anything about this repository's architecture, functions, API endpoints, or code logic."
        return {
            "id": chat_id,
            "repository_id": repo_id_str,
            "question": payload.question,
            "answer": reply,
            "confidence": "high",
            "citations": [],
            "execution_time_ms": elapsed,
            "thought_process": {
                "query_type": "Conversational Greeting",
                "total_files_scanned": 0,
                "contexts_retrieved": 0,
                "contexts_analyzed": [],
                "execution_time_ms": elapsed,
                "keywords_extracted": [],
                "llm_engine": "Instant Router"
            }
        }

    contexts, repo_meta = await retrieval_service.retrieve_contexts(
        question=payload.question,
        repository_id=repo_id_str,
        db=db,
        top_k=5
    )

    rag_result = await llm_service.generate_rag_response(payload.question, contexts, repo_meta)
    elapsed = round((time.time() - start_time) * 1000, 1)

    is_overview_query = any(pattern in question_text for pattern in [
        "what is this repo about", "repo about", "repository about", "overview", "what does this repo do",
        "architecture", "explain repo", "explain repository", "project structure", "readme",
        "workspace", "workspace about", "what is this workspace about", "project about", "explain project",
        "explain workspace", "what is this project about", "what does this project do", "summary", "about this"
    ])
    is_simple_query = len(payload.question.split()) <= 3 and not is_overview_query
    analyzed_paths = [ctx["file_path"] for ctx in contexts]

    thought_process = {
        "query_type": "Fast Query Path" if is_simple_query else ("Workspace Overview" if is_overview_query else "Targeted Code RAG"),
        "total_files_scanned": repo_meta.get("total_files", len(contexts)),
        "contexts_retrieved": len(contexts),
        "contexts_analyzed": analyzed_paths,
        "execution_time_ms": elapsed,
        "keywords_extracted": [],
        "llm_engine": f"NVIDIA NIM ({llm_service.nim_model})" if (llm_service.nim_api_key and llm_service.nim_api_key.startswith("nvapi-")) else f"Gemini ({llm_service.gemini_model})"
    }

    chat_id = f"chat-{uuid.uuid4().hex[:8]}"

    chat_record = ChatModel(
        id=uuid.uuid4(),
        repository_id=repo.id,
        question=payload.question,
        answer=rag_result["answer"],
        confidence=rag_result["confidence"],
        citations=rag_result["citations"]
    )
    db.add(chat_record)
    await db.commit()

    return {
        "id": chat_id,
        "repository_id": repo_id_str,
        "question": payload.question,
        "answer": rag_result["answer"],
        "confidence": rag_result["confidence"],
        "citations": [CitationItem(**cite) for cite in rag_result["citations"]],
        "execution_time_ms": elapsed,
        "thought_process": thought_process
    }
