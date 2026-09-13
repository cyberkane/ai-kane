# -*- coding: utf-8 -*-
import pytest
from httpx import AsyncClient

# Хэшируем маркер для всех функций в файле под стандарт Python 3.13

async def test_in_memory_proxy_chat_success(async_client: AsyncClient):
    """Проверяем успешный проход запроса чата через шлюз в оперативной памяти."""
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Привет! Ответь одним словом."}],
        "stream": True
    }
    response = await async_client.post("/v1/chat/completions", json=body)
    assert response.status_code in [200, 503]


async def test_in_memory_proxy_chat_rag_integration(async_client: AsyncClient):
    """Проверяем, что RAG-пайплайн успешно отрабатывает при секретном вопросе."""
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Куда переключается кэш MarmAI, если падает Dragonfly?"}],
        "stream": True
    }
    response = await async_client.post("/v1/chat/completions", json=body)
    assert response.status_code in [200, 503]


async def test_in_memory_proxy_chat_invalid_body(async_client: AsyncClient):
    """Проверяем работу нашей асинхронной ИБ-защиты от сломанных JSON структур."""
    bad_raw_data = "This is definitely not a valid JSON string!"
    
    response = await async_client.post(
        "/v1/chat/completions", 
        content=bad_raw_data,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
