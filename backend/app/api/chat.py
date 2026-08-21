import json
import logging
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.limiter import rate_limit
from app.database import AsyncSessionLocal, get_db
from app.models.chat import Chat as ChatModel
from app.models.repository import Repository
from app.schemas.chat import ChatRequest, ChatResponse, CitationItem
from app.services.llm_service import LLMService
from app.services.retrieval_service import RetrievalService, retrieval_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# Service dependency providers
_default_llm_service = LLMService()


def get_llm_service() -> LLMService:
    return _default_llm_service


def get_retrieval_service() -> RetrievalService:
    return retrieval_service


GREETING_PATTERNS = {
    "hi", "hello", "hey", "hi there", "hello there",
    "good morning", "good evening", "howdy", "thanks", "thank you"
}

OVERVIEW_INTENT_PATTERNS = [
    "what is this repo about", "repo about", "repository about", "overview", "what does this repo do",
    "architecture", "explain repo", "explain repository", "project structure", "readme",
    "workspace", "workspace about", "what is this workspace about", "project about", "explain project",
    "explain workspace", "what is this project about", "what does this project do", "summary", "about this"
]

GREETING_ANSWER = (
    "Hello! I am your AI Codebase Knowledge Assistant. "
    "Ask me anything about this repository's architecture, functions, API endpoints, or code logic."
)


def _is_greeting(query: str) -> bool:
    cleaned = query.strip().lower().rstrip("!.")
    return cleaned in GREETING_PATTERNS


def _classify_query_type(question: str) -> str:
    q_lower = question.strip().lower()
    if any(pattern in q_lower for pattern in OVERVIEW_INTENT_PATTERNS):
        return "Workspace Overview"
    if len(question.split()) <= 3:
        return "Fast Query Path"
    return "Targeted Code RAG"


async def _resolve_repository(repo_id_input: str, db: AsyncSession) -> Repository:
    try:
        parsed_uuid = uuid.UUID(repo_id_input)
        stmt = select(Repository).where(Repository.id == parsed_uuid)
        repo = (await db.execute(stmt)).scalars().first()
    except ValueError:
        stmt = select(Repository).where(Repository.name.ilike(f"%{repo_id_input}%"))
        repo = (await db.execute(stmt)).scalars().first()

    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id_input}"
        )
    return repo


@router.post("", response_model=ChatResponse, dependencies=[Depends(verify_api_key), Depends(rate_limit(limit_count=20, window_seconds=60, tag="chat"))])
async def chat_query(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMService = Depends(get_llm_service),
    retriever: RetrievalService = Depends(get_retrieval_service),
):
    start_time = time.time()
    if not payload.repository_id or not payload.repository_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repository_id is required",
        )

    repo = await _resolve_repository(payload.repository_id.strip(), db)
    repo_id_str = str(repo.id)

    if _is_greeting(payload.question):
        elapsed = round((time.time() - start_time) * 1000, 1)
        chat_id = f"chat-{uuid.uuid4().hex[:8]}"
        return {
            "id": chat_id,
            "repository_id": repo_id_str,
            "question": payload.question,
            "answer": GREETING_ANSWER,
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

    contexts, repo_meta = await retriever.retrieve_contexts(
        question=payload.question,
        repository_id=repo_id_str,
        db=db,
        top_k=8
    )

    rag_result = await llm.generate_rag_response(payload.question, contexts, repo_meta)
    elapsed = round((time.time() - start_time) * 1000, 1)

    query_type = _classify_query_type(payload.question)
    analyzed_paths = [ctx["file_path"] for ctx in contexts]

    thought_process = {
        "query_type": query_type,
        "total_files_scanned": repo_meta.get("total_files", len(contexts)),
        "contexts_retrieved": len(contexts),
        "contexts_analyzed": analyzed_paths,
        "execution_time_ms": elapsed,
        "keywords_extracted": [],
        "llm_engine": rag_result.get("provider") or (
            f"NVIDIA NIM ({llm.nim_model})"
            if (llm.nim_api_key and llm.nim_api_key.startswith("nvapi-"))
            else f"Gemini ({llm.gemini_model})"
        ),
    }

    record_id = uuid.uuid4()
    chat_id = f"chat-{record_id.hex[:8]}"

    chat_record = ChatModel(
        id=record_id,
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


@router.post("/stream", dependencies=[Depends(verify_api_key), Depends(rate_limit(limit_count=20, window_seconds=60, tag="chat"))])
async def chat_query_stream(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMService = Depends(get_llm_service),
    retriever: RetrievalService = Depends(get_retrieval_service),
):
    start_time = time.time()
    if not payload.repository_id or not payload.repository_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repository_id is required",
        )

    repo = await _resolve_repository(payload.repository_id.strip(), db)
    repo_id_str = str(repo.id)
    repo_db_id = repo.id

    if _is_greeting(payload.question):
        async def greeting_stream() -> AsyncGenerator[str, None]:
            elapsed = round((time.time() - start_time) * 1000, 1)
            yield f"data: {json.dumps({'type': 'token', 'text': GREETING_ANSWER})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'answer': GREETING_ANSWER, 'citations': [], 'execution_time_ms': elapsed, 'thought_process': {'query_type': 'Conversational Greeting', 'total_files_scanned': 0, 'contexts_retrieved': 0, 'contexts_analyzed': [], 'execution_time_ms': elapsed, 'keywords_extracted': [], 'llm_engine': 'Instant Router'}})}\n\n"

        return StreamingResponse(
            greeting_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    contexts, repo_meta = await retriever.retrieve_contexts(
        question=payload.question,
        repository_id=repo_id_str,
        db=db,
        top_k=8
    )

    query_type = _classify_query_type(payload.question)
    analyzed_paths = [ctx["file_path"] for ctx in contexts]

    async def event_generator() -> AsyncGenerator[str, None]:
        accumulated_answer = ""
        citations_list = []
        provider_name = ""

        try:
            async for event in llm.stream_rag_response(payload.question, contexts, repo_meta):
                ev_type = event.get("type")
                if ev_type == "token":
                    accumulated_answer += event.get("text", "")
                    yield f"data: {json.dumps(event)}\n\n"
                elif ev_type == "done":
                    final_ans = event.get("answer", accumulated_answer)
                    citations_list = event.get("citations", [])
                    provider_name = event.get("provider", "LLM")
                    elapsed = round((time.time() - start_time) * 1000, 1)

                    thought_process = {
                        "query_type": query_type,
                        "total_files_scanned": repo_meta.get("total_files", len(contexts)),
                        "contexts_retrieved": len(contexts),
                        "contexts_analyzed": analyzed_paths,
                        "execution_time_ms": elapsed,
                        "keywords_extracted": [],
                        "llm_engine": provider_name,
                    }

                    # Persist chat record asynchronously
                    try:
                        async with AsyncSessionLocal() as session:
                            record_id = uuid.uuid4()
                            chat_record = ChatModel(
                                id=record_id,
                                repository_id=repo_db_id,
                                question=payload.question,
                                answer=final_ans,
                                confidence="high" if citations_list else "low",
                                citations=citations_list,
                            )
                            session.add(chat_record)
                            await session.commit()
                    except Exception as db_err:
                        logger.warning("Failed to persist streaming chat record: %s", db_err)

                    done_payload = {
                        "type": "done",
                        "answer": final_ans,
                        "citations": citations_list,
                        "execution_time_ms": elapsed,
                        "thought_process": thought_process,
                    }
                    yield f"data: {json.dumps(done_payload)}\n\n"
                elif ev_type == "error":
                    yield f"data: {json.dumps(event)}\n\n"

        except Exception as err:
            logger.error("SSE stream generation error: %s", err, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(err)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{repository_id}", dependencies=[Depends(verify_api_key)])
async def get_chat_history(repository_id: str, db: AsyncSession = Depends(get_db)):
    repo = await _resolve_repository(repository_id, db)
    stmt = (
        select(ChatModel)
        .where(ChatModel.repository_id == repo.id)
        .order_by(ChatModel.created_at.asc())
    )
    records = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": f"chat-{r.id}",
            "repositoryId": str(r.repository_id),
            "question": r.question,
            "answer": r.answer,
            "confidence": r.confidence,
            "citations": r.citations or [],
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.delete("/history/{repository_id}", dependencies=[Depends(verify_api_key)])
async def clear_chat_history(repository_id: str, db: AsyncSession = Depends(get_db)):
    repo = await _resolve_repository(repository_id, db)
    stmt = sa_delete(ChatModel).where(ChatModel.repository_id == repo.id)
    await db.execute(stmt)
    await db.commit()
    return {"status": "cleared", "repository_id": str(repo.id)}
