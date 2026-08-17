from datetime import datetime
from pydantic import BaseModel, ConfigDict

class RepoImportRequest(BaseModel):
    github_url: str

class RepoStats(BaseModel):
    files: int = 0
    symbols: int = 0

class RepoResponse(BaseModel):
    id: str
    name: str
    github_url: str
    language: str
    status: str
    commit_sha: str | None = None
    indexed_at: datetime | None = None
    stats: RepoStats | None = None

    model_config = ConfigDict(from_attributes=True)
