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
