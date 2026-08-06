import uuid
from datetime import datetime
from pydantic import BaseModel, HttpUrl

class RepoImportRequest(BaseModel):
    github_url: str

class RepoStats(BaseModel):
    files: int = 0
    classes: int = 0
    methods: int = 0

class IndexStage(BaseModel):
    id: int
    name: str
    status: str
    detail: str | None = None

class RepoResponse(BaseModel):
    id: str
    name: str
    github_url: str
    language: str
    status: str
    indexed_at: datetime | None = None
    stats: RepoStats | None = None

    class Config:
        from_attributes = True

class RepoIndexResponse(BaseModel):
    repository_id: str
    status: str
    stats: RepoStats
    stages: list[IndexStage]
