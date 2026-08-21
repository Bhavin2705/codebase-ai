import pytest

def test_repository_import_and_index(client):
    import_payload = {"github_url": "https://github.com/spring-projects/spring-petclinic"}
    res = client.post("/repositories", json=import_payload)
    assert res.status_code in (200, 201)
    repo_data = res.json()
    assert "id" in repo_data
    assert repo_data["github_url"] == import_payload["github_url"]

    bad_res = client.post("/repositories", json={"github_url": "invalid-url"})
    assert bad_res.status_code == 400

    repo_id = repo_data["id"]
    index_res = client.post(f"/repositories/{repo_id}/index")
    assert index_res.status_code in (200, 202)
    index_data = index_res.json()
    assert "job_id" in index_data or index_data.get("status") in ("pending", "ready", "running")

def test_repository_tree_and_file(client):
    import_payload = {"github_url": "https://github.com/spring-projects/spring-petclinic"}
    res = client.post("/repositories", json=import_payload)
    assert res.status_code in (200, 201)
    repo_id = res.json()["id"]

    tree_res = client.get(f"/repositories/{repo_id}/tree")
    assert tree_res.status_code == 200
    tree_data = tree_res.json()
    assert isinstance(tree_data, list)

    bad_file = client.get(f"/repositories/{repo_id}/file?path=nonexistent_file_path.java")
    assert bad_file.status_code == 404

def test_import_nonexistent_repository_fails_preflight(client):
    import_payload = {"github_url": "https://github.com/nonexistent-org-test-9999/fake-repo-test-8888"}
    res = client.post("/repositories", json=import_payload)
    assert res.status_code == 404
    data = res.json()
    assert "Repository not found" in data["detail"]
    assert "No indexing job was created" in data["detail"]

@pytest.mark.anyio
async def test_file_viewer_path_resolutions():
    import uuid
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.database import AsyncSessionLocal
    from app.models.repository import Repository
    from app.models.file import File as FileModel
    from app.models.symbol import Symbol as SymbolModel

    repo_id = uuid.uuid4()
    file_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        repo = Repository(
            id=repo_id,
            name="test/viewer-test-repo",
            github_url=f"https://github.com/test/viewer-{repo_id.hex[:6]}",
            language="Python",
            status="ready",
        )
        file_rec = FileModel(
            id=file_id,
            repository_id=repo_id,
            path="src/components/Main.py",
            language=".py",
            content="def execute():\n    return 'success'\n",
        )
        sym = SymbolModel(
            id=uuid.uuid4(),
            file_id=file_id,
            name="execute",
            symbol_type="function",
            signature="def execute() -> str",
            source_code="def execute():\n    return 'success'\n",
            start_line=1,
            end_line=2,
        )
        session.add_all([repo, file_rec, sym])
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Exact path
        res = await ac.get(f"/repositories/{repo_id}/file?path=src/components/Main.py")
        assert res.status_code == 200
        assert "def execute():" in res.json()["content"]
        assert len(res.json()["symbols"]) == 1

        # Leading ./
        res_dot = await ac.get(f"/repositories/{repo_id}/file?path=./src/components/Main.py")
        assert res_dot.status_code == 200
        assert res_dot.json()["content"] == res.json()["content"]

        # URL encoded and backslashes
        res_encoded = await ac.get(f"/repositories/{repo_id}/file?path=src%5Ccomponents%5CMain.py")
        assert res_encoded.status_code == 200

        # Path traversal rejected with 400
        res_traversal = await ac.get(f"/repositories/{repo_id}/file?path=../../etc/passwd")
        assert res_traversal.status_code == 400


