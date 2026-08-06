import uuid
from pydantic import BaseModel

class CitationItem(BaseModel):
    id: str
    label: str
    filePath: str
    startLine: int
    endLine: int
    symbol: str | None = None

class ChatRequest(BaseModel):
    repository_id: str
    question: str

class ChatResponse(BaseModel):
    id: str
    repository_id: str
    question: str
    answer: str
    confidence: str = "high"
    citations: list[CitationItem] = []
    execution_time_ms: float | None = None
    thought_process: dict | None = None
