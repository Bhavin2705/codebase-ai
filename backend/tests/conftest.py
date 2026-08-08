import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService

@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    async def mock_generate_rag_response(question, contexts, repo_meta=None):
        citations = []
        for idx, ctx in enumerate(contexts):
            citations.append({
                "id": f"cite-{idx + 1}",
                "label": f"{ctx['file_path'].split('/')[-1]}:{ctx['start_line']}-{ctx['end_line']}",
                "filePath": ctx["file_path"],
                "startLine": ctx["start_line"],
                "endLine": ctx["end_line"],
                "symbol": ctx["name"]
            })
        return {
            "answer": f"Mocked RAG response for: {question}",
            "confidence": "high",
            "citations": citations
        }

    async def mock_generate_embedding(text):
        return [0.01] * 768

    monkeypatch.setattr(LLMService, "generate_rag_response", AsyncMock(side_effect=mock_generate_rag_response))
    monkeypatch.setattr(EmbeddingService, "generate_embedding", AsyncMock(side_effect=mock_generate_embedding))

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

from app.database import engine

@pytest.fixture(autouse=True)
def cleanup_db():
    engine.sync_engine.dispose()
    yield
    engine.sync_engine.dispose()
