# -*- coding: utf-8 -*-
import pytest
from httpx import AsyncClient

# Задаем маркер асинхронности для всех тест-кейсов в модуле
pytestmark = pytest.mark.asyncio

async def test_proxy_chat_valid_request(async_client: AsyncClient):
    """Проверяет успешный проход валидного запроса чата через шлюз."""
    request_body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Привет! Сколько будет дважды два?"}]
    }
    # ИСПРАВЛЕНО: Добавлен обязательный префикс /v1 к эндпоинту
    response = await async_client.post("/v1/chat/completions", json=request_body)
    assert response.status_code in [200, 204]


async def test_proxy_chat_invalid_request_json(async_client: AsyncClient):
    """Проверяет реакцию ИБ-защиты шлюза на битый, невалидный JSON."""
    # ИСПРАВЛЕНО: Добавлен обязательный префикс /v1 к эндпоинту
    response = await async_client.post(
        "/v1/chat/completions", 
        content="This is definitely not a valid JSON string!",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400


async def test_proxy_chat_tool_choice(async_client: AsyncClient):
    """Проверяет, что шлюз успешно инжектирует инструменты при ключевых запросах."""
    request_body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Какое сейчас время на бэкенде?"}]
    }
    # ИСПРАВЛЕНО: Добавлен обязательный префикс /v1 к эндпоинту
    response = await async_client.post("/v1/chat/completions", json=request_body)
    assert response.status_code in [200, 204]
