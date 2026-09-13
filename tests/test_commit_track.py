import pytest
from fastapi.testclient import TestClient
from yourapp import app  # Replace 'yourapp' with your actual app module
from yourapp.main import router  # Replace 'yourapp.main' with your actual router module
from unittest.mock import Mock
import time
from pydantic import BaseModel
from fastapi import HTTPException

class VcsCommitRequest(BaseModel):
    project_id: str
    commit_hash: str
    author: str
    branch: str
    commit_message: str
    files_added: list[str]
    files_modified: list[str]
    insertions: int
    deletions: int

client = TestClient(app)

def test_receive_vcs_commit():
    payload = VcsCommitRequest(
        project_id="test_project",
        commit_hash="test_commit_hash",
        author="test_author",
        branch="test_branch",
        commit_message="test_commit_message",
        files_added=["test_file1", "test_file2"],
        files_modified=["test_file3", "test_file4"],
        insertions=10,
        deletions=5
    )

    response = client.post("/vcs/commit", json=payload.dict())
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": f"Коммит {payload.commit_hash} успешно сохранен в память ИИ-агента."}

def test_receive_vcs_commit_invalid_payload():
    payload = VcsCommitRequest(
        project_id=None,
        commit_hash="test_commit_hash",
        author="test_author",
        branch="test_branch",
        commit_message="test_commit_message",
        files_added=["test_file1", "test_file2"],
        files_modified=["test_file3", "test_file4"],
        insertions=10,
        deletions=5
    )

    response = client.post("/vcs/commit", json=payload.dict())
    assert response.status_code == 422

def test_receive_vcs_commit_http_exception():
    payload = VcsCommitRequest(
        project_id="test_project",
        commit_hash="test_commit_hash",
        author="test_author",
        branch="test_branch",
        commit_message="test_commit_message",
        files_added=["test_file1", "test_file2"],
        files_modified=["test_file3", "test_file4"],
        insertions=10,
        deletions=5
    )

    mock_save_knowledge_point = Mock(return_value=False)
    app.dependency_overrides[save_knowledge_point] = mock_save_knowledge_point

    response = client.post("/vcs/commit", json=payload.dict())
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to index commit history in vector storage."

def test_receive_vcs_commit_critical_error():
    payload = VcsCommitRequest(
        project_id="test_project",
        commit_hash="test_commit_hash",
        author="test_author",
        branch="test_branch",
        commit_message="test_commit_message",
        files_added=["test_file1", "test_file2"],
        files_modified=["test_file3", "test_file4"],
        insertions=10,
        deletions=5
    )

    mock_save_knowledge_point = Mock(side_effect=Exception("Test exception"))
    app.dependency_overrides[save_knowledge_point] = mock_save_knowledge_point

    response = client.post("/vcs/commit", json=payload.dict())
    assert response.status_code == 500
    assert response.json()["detail"] == "VCS tracking critical error: Test exception."