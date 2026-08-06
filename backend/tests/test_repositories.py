def test_repository_import_and_index(client):
    # Test valid import
    import_payload = {"github_url": "https://github.com/spring-projects/spring-petclinic"}
    res = client.post("/repositories", json=import_payload)
    assert res.status_code == 201
    repo_data = res.json()
    assert "id" in repo_data
    assert repo_data["github_url"] == import_payload["github_url"]

    # Test invalid import
    bad_res = client.post("/repositories", json={"github_url": "invalid-url"})
    assert bad_res.status_code == 400

    # Test indexing
    repo_id = repo_data["id"]
    index_res = client.post(f"/repositories/{repo_id}/index")
    assert index_res.status_code == 200
    index_data = index_res.json()
    assert index_data["status"] == "ready"
    assert len(index_data["stages"]) == 5

def test_repository_tree_and_file(client):
    repo_id = "repo-1"
    # Get tree
    tree_res = client.get(f"/repositories/{repo_id}/tree")
    assert tree_res.status_code == 200
    tree_data = tree_res.json()
    assert isinstance(tree_data, list)
    assert len(tree_data) > 0

    # Get file content
    file_path = "src/main/java/org/springframework/samples/petclinic/owner/OwnerController.java"
    file_res = client.get(f"/repositories/{repo_id}/file?path={file_path}")
    assert file_res.status_code == 200
    file_data = file_res.json()
    assert file_data["path"] == file_path
    assert "OwnerController" in file_data["content"]
