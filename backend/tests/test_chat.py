def test_chat_query_contract(client):
    import_payload = {"github_url": "https://github.com/spring-projects/spring-petclinic"}
    res = client.post("/repositories", json=import_payload)
    assert res.status_code in (200, 201)
    repo_id = res.json()["id"]

    chat_payload = {
        "repository_id": repo_id,
        "question": "How does owner search work?"
    }
    chat_res = client.post("/chat", json=chat_payload)
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert data["repository_id"] == repo_id
    assert "answer" in data

def test_chat_query_imported_repo(client):
    import_payload = {"github_url": "https://github.com/spring-projects/spring-petclinic"}
    res = client.post("/repositories", json=import_payload)
    assert res.status_code in (200, 201)
    repo_id = res.json()["id"]

def test_chat_query_missing_repo_id(client):
    chat_res_empty = client.post("/chat", json={"repository_id": "", "question": "What is this repo?"})
    assert chat_res_empty.status_code == 400
    assert "repository_id is required" in chat_res_empty.json()["detail"]

    chat_res_missing = client.post("/chat", json={"question": "What is this repo?"})
    assert chat_res_missing.status_code == 422


