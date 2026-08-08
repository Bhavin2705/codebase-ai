import uuid
from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.chat import Chat
    from app.models.repository_version import RepositoryVersion
    from app.models.indexing_job import IndexingJob

class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    github_url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("repository_versions.id", ondelete="SET NULL"), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False)

    chats: Mapped[List["Chat"]] = relationship("Chat", back_populates="repository", cascade="all, delete-orphan")
    versions: Mapped[List["RepositoryVersion"]] = relationship("RepositoryVersion", foreign_keys="[RepositoryVersion.repository_id]", back_populates="repository", cascade="all, delete-orphan")
    indexing_jobs: Mapped[List["IndexingJob"]] = relationship("IndexingJob", back_populates="repository", cascade="all, delete-orphan")
    current_version: Mapped["RepositoryVersion | None"] = relationship("RepositoryVersion", foreign_keys=[current_version_id], post_update=True)
