import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

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
    current_version_id: str | None = None
    commit_sha: str | None = None
    indexed_at: datetime | None = None
    stats: RepoStats | None = None

    model_config = ConfigDict(from_attributes=True)

class RepoIndexResponse(BaseModel):
    job_id: str
    status: str
    stats: RepoStats | None = None
    stages: list[IndexStage] = []
