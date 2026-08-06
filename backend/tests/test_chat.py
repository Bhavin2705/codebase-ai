import uuid

def test_chat_query_contract(client):
    repo_id = "repo-1"
    chat_payload = {
        "repository_id": repo_id,
        "question": "How does owner search work?"
    }
    res = client.post("/chat", json=chat_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["repository_id"] == repo_id
    assert "answer" in data
    assert len(data["citations"]) > 0
    citation = data["citations"][0]
    assert "filePath" in citation
    assert "startLine" in citation
    assert "endLine" in citation

def test_chat_query_imported_repo(client):
    # Import repo first
    import_payload = {"github_url": "https://github.com/spring-projects/spring-petclinic"}
    res = client.post("/repositories", json=import_payload)
    assert res.status_code == 201
    repo_id = res.json()["id"]

    chat_payload = {
        "repository_id": repo_id,
        "question": "How does OwnerController work?"
    }
    chat_res = client.post("/chat", json=chat_payload)
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["repository_id"] == repo_id
    assert len(chat_data["citations"]) > 0
