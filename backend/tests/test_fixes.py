import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal
from app.models.repository import Repository
from app.models.indexing_job import IndexingJob
from app.models.file import File as FileModel
from app.models.symbol import Symbol as SymbolModel
from app.models.chat import Chat as ChatModel
from app.services.indexing_service import indexing_service
from app.services.retrieval_service import retrieval_service

@pytest.mark.anyio
async def test_reindexing_already_indexed_commit():
    async with AsyncSessionLocal() as db:
        repo_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        commit_sha = "abcdef1234567890abcdef1234567890abcdef12"

        repo = Repository(
            id=repo_id,
            name="test-org/reindex-repo",
            github_url=f"https://github.com/test-org/reindex-repo-{repo_id.hex[:6]}",
            language="Python",
            status="ready",
            commit_sha=commit_sha,
            file_count=5,
            symbol_count=10,
            indexed_at=now
        )
        job_id = uuid.uuid4()
        job = IndexingJob(
            id=job_id,
            repository_id=repo_id,
            status="pending",
            current_stage="cloning"
        )
        db.add(repo)
        db.add(job)
        await db.commit()

    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        with pytest.MonkeyPatch.context() as m:
            m.setattr(indexing_service.git, "clone_repository", lambda url: tmp_dir)
            m.setattr(indexing_service.git, "get_commit_sha", lambda dir: commit_sha)
            m.setattr(indexing_service.git, "cleanup", lambda dir: None)

            await indexing_service.run_pipeline(str(job_id))

    async with AsyncSessionLocal() as db:
        res_job = (await db.execute(select(IndexingJob).where(IndexingJob.id == job_id))).scalars().first()
        res_repo = (await db.execute(select(Repository).where(Repository.id == repo_id))).scalars().first()
        
        assert res_job is not None
        assert res_job.status == "completed"
        assert res_repo is not None
        assert res_repo.status == "ready"
        assert res_repo.commit_sha == commit_sha

@pytest.mark.anyio
async def test_failed_indexing_preserves_ready_status_when_previously_indexed():
    async with AsyncSessionLocal() as db:
        repo_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        repo = Repository(
            id=repo_id,
            name="test-org/fail-repo",
            github_url=f"https://github.com/test-org/fail-repo-{repo_id.hex[:6]}",
            language="Python",
            status="ready",
            commit_sha="1111111111111111111111111111111111111111",
            file_count=3,
            symbol_count=5,
            indexed_at=now
        )
        job_id = uuid.uuid4()
        job = IndexingJob(
            id=job_id,
            repository_id=repo_id,
            status="pending",
            current_stage="cloning"
        )
        db.add(repo)
        db.add(job)
        await db.commit()

    def mock_clone_fail(url):
        raise RuntimeError("Simulated clone error")

    with pytest.MonkeyPatch.context() as m:
        m.setattr(indexing_service.git, "clone_repository", mock_clone_fail)
        await indexing_service.run_pipeline(str(job_id))

    async with AsyncSessionLocal() as db:
        res_repo = (await db.execute(select(Repository).where(Repository.id == repo_id))).scalars().first()
        res_job = (await db.execute(select(IndexingJob).where(IndexingJob.id == job_id))).scalars().first()

        assert res_job is not None
        assert res_job.status == "failed"
        assert "Simulated clone error" in (res_job.error_message or "")
        assert res_repo is not None
        assert res_repo.status == "ready"
        assert res_repo.commit_sha == "1111111111111111111111111111111111111111"

@pytest.mark.anyio
async def test_retrieval_uses_repository_files():
    async with AsyncSessionLocal() as db:
        repo1_id = uuid.uuid4()
        repo2_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        repo1 = Repository(
            id=repo1_id,
            name="test-org/repo-1",
            github_url=f"https://github.com/test-org/repo-1-{repo1_id.hex[:6]}",
            language="Python",
            status="ready",
            commit_sha="1111111111111111111111111111111111111111",
            indexed_at=now
        )
        repo2 = Repository(
            id=repo2_id,
            name="test-org/repo-2",
            github_url=f"https://github.com/test-org/repo-2-{repo2_id.hex[:6]}",
            language="Python",
            status="ready",
            commit_sha="2222222222222222222222222222222222222222",
            indexed_at=now
        )

        f1_id = uuid.uuid4()
        f1 = FileModel(id=f1_id, repository_id=repo1_id, path="repo1_file.py", language="python", content="def old_fn(): pass")
        s1 = SymbolModel(id=uuid.uuid4(), file_id=f1_id, name="old_fn", symbol_type="function", source_code="def old_fn(): pass", start_line=1, end_line=1)

        f2_id = uuid.uuid4()
        f2 = FileModel(id=f2_id, repository_id=repo2_id, path="repo2_file.py", language="python", content="def new_fn(): pass")
        s2 = SymbolModel(id=uuid.uuid4(), file_id=f2_id, name="new_fn", symbol_type="function", source_code="def new_fn(): pass", start_line=1, end_line=1)

        db.add(repo1)
        db.add(repo2)
        db.add(f1)
        db.add(s1)
        db.add(f2)
        db.add(s2)
        await db.commit()

        contexts, _ = await retrieval_service.retrieve_contexts("how does function work?", str(repo2_id), db)
        paths = [c["file_path"] for c in contexts]
        assert "repo2_file.py" in paths
        assert "repo1_file.py" not in paths

@pytest.mark.anyio
async def test_chat_persistence_using_repository_name_identifier():
    repo_name = f"test-org/chat-name-repo-{uuid.uuid4().hex[:6]}"
    repo_uuid = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        r = Repository(
            id=repo_uuid,
            name=repo_name,
            github_url=f"https://github.com/{repo_name}",
            language="Python",
            status="ready",
            commit_sha="3333333333333333333333333333333333333333"
        )
        db.add(r)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/chat", json={"repository_id": repo_name, "question": "What is in this repo?"})
        assert res.status_code == 200
        data = res.json()
        assert data["repository_id"] == str(repo_uuid)

    async with AsyncSessionLocal() as db:
        stmt = select(ChatModel).where(ChatModel.repository_id == repo_uuid)
        chats = (await db.execute(stmt)).scalars().all()
        assert len(chats) > 0

@pytest.mark.anyio
async def test_chat_invalid_repository_identifier_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/chat", json={"repository_id": "non-existent-repo-12345", "question": "Hello"})
        assert res.status_code == 404
        data = res.json()
        assert "detail" in data

@pytest.mark.anyio
async def test_embedding_failure_fails_indexing_job():
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmp_dir:
        main_py_path = os.path.join(tmp_dir, "main.py")
        with open(main_py_path, "w", encoding="utf-8") as f:
            f.write("def sample_function():\n    return 42\n")

        async with AsyncSessionLocal() as db:
            repo_id = uuid.uuid4()
            now = datetime.now(timezone.utc)

            repo = Repository(
                id=repo_id,
                name="test-org/emb-fail-repo",
                github_url=f"https://github.com/test-org/emb-fail-repo-{repo_id.hex[:6]}",
                language="Python",
                status="pending",
                indexed_at=now
            )
            job_id = uuid.uuid4()
            job = IndexingJob(
                id=job_id,
                repository_id=repo_id,
                status="pending",
                current_stage="cloning"
            )
            db.add(repo)
            db.add(job)
            await db.commit()

        async def mock_fail_embedding(*args, **kwargs):
            raise RuntimeError("Embedding pipeline failed: simulated failure")

        test_commit_sha = uuid.uuid4().hex

        with pytest.MonkeyPatch.context() as m:
            m.setattr(indexing_service.git, "clone_repository", lambda url: tmp_dir)
            m.setattr(indexing_service.git, "get_commit_sha", lambda dir: test_commit_sha)
            m.setattr(indexing_service.git, "scan_files", lambda dir: [("main.py", main_py_path)])
            m.setattr(indexing_service.embedder, "generate_embeddings_batch", mock_fail_embedding)
            m.setattr(indexing_service.git, "cleanup", lambda dir: None)

            await indexing_service.run_pipeline(str(job_id))

        async with AsyncSessionLocal() as db:
            res_job = (await db.execute(select(IndexingJob).where(IndexingJob.id == job_id))).scalars().first()
            res_repo = (await db.execute(select(Repository).where(Repository.id == repo_id))).scalars().first()

            assert res_job is not None
            assert res_job.status == "failed"
            assert "Embedding pipeline failed" in (res_job.error_message or "")
            assert res_repo is not None
            assert res_repo.status == "error"
