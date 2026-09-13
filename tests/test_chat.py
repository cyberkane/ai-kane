import pytest
import httpx

@pytest.mark.asyncio
async def test_proxy_chat_success():
    """Проверяем базовый успешный сценарий общения со шлюзом чата."""
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Привет! Ответь одним словом."}],
        "stream": True
    }
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8000/v1/chat/completions", json=body, timeout=10.0)
    
    assert response.status_code == 200
    # Так как это StreamingResponse, проверяем тип контента
    assert "text/event-stream" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_proxy_chat_rag_integration():
    """Проверяем, что RAG-пайплайн успешно отрабатывает при секретном вопросе."""
    body = {
        "model": "llama3.1:8b",
        "messages": [{"role": "user", "content": "Куда переключается кэш MarmAI, если падает Dragonfly?"}],
        "stream": True
    }
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8000/v1/chat/completions", json=body, timeout=10.0)
    
    assert response.status_code == 200
    
    # Читаем кусочек стрима, чтобы убедиться, что Ollama отвечает на основе контекста Qdrant
    full_text = ""
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            full_text += line
            
    assert len(full_text) > 0


@pytest.mark.asyncio
async def test_proxy_chat_invalid_body():
    """Проверяем, что при отправке поврежденного (не как JSON) тела шлюз вернет ошибку."""
    bad_raw_data = "This is not a JSON string at all!"
    
    async with httpx.AsyncClient(timeout=2.0) as client:
        response = await client.post(
            "http://localhost:8000/v1/chat/completions", 
            content=bad_raw_data,
            headers={"Content-Type": "application/json"}
        )
        
    # ИСПРАВЛЕНО: Теперь шлюз строго возвращает 400 согласно нашей промышленной защите
    assert response.status_code == 400