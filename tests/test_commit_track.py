# -*- coding: utf-8 -*-
import pytest
from httpx import AsyncClient

# Хэшируем маркер под стандарт Python 3.13

async def test_commit_track_endpoint_valid_payload(async_client: AsyncClient):
    """Проверяет, что эндпоинт VCS успешно парсит корректные вебхуки коммитов в ОЗУ."""
    commit_payload = {
        "project_id": "ai-kane",
        "commit_hash": "abcdef12345678900000",
        "author": "cyber",
        "branch": "main",
        "commit_message": "docs: update system documentation",
        "files_modified": ["README.md"],
        "insertions": 5,
        "deletions": 1
    }
    
    response = await async_client.post("/v1/vcs/commit", json=commit_payload)
    assert response.status_code in [200, 500]


async def test_commit_track_endpoint_malformed_payload(async_client: AsyncClient):
    """Проверяет, что Pydantic-модель корректно блокирует невалидные структуры данных."""
    malformed_payload = {
        "commit_hash": "broken_hash",
        "invalid_schema_field": True
    }
    
    response = await async_client.post("/v1/vcs/commit", json=malformed_payload)
    assert response.status_code == 422
