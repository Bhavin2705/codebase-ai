import uuid
from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.indexing_job import IndexingJob
    from app.models.file import File

class RepositoryVersion(Base):
    __tablename__ = "repository_versions"
    __table_args__ = (UniqueConstraint("repository_id", "commit_sha", name="uix_repo_commit_sha"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    symbol_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False)

    repository: Mapped["Repository"] = relationship("Repository", foreign_keys=[repository_id], back_populates="versions")
    indexing_jobs: Mapped[List["IndexingJob"]] = relationship("IndexingJob", back_populates="repository_version", cascade="all, delete-orphan")
    files: Mapped[List["File"]] = relationship("File", back_populates="repository_version", cascade="all, delete-orphan")
