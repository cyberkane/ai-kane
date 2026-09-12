import os
import time
import httpx
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from metrics.telemetry import log_event

# Импортируем наши асинхронные методы баз данных и хранилища
from database.vector_storage import search_similar_knowledge
from database.storage import load_prompt_from_minio

router = APIRouter()

def get_ollama_url(app_config: dict) -> str:
    """Функция для умной настройки адреса Ollama при локальном запуске"""
    chat_cfg = app_config.get("chat", {})
    host = chat_cfg.get("host", "http://localhost")
    port = chat_cfg.get("port", "11434")
    
    if "ollama_core" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    return f"{host}:{port}"

@router.post("/chat/completions")
async def proxy_chat(request: Request):
    from main import app_config

    body = await request.json()
    model_name = body.get('model', 'unknown')
    messages = body.get('messages', [])
    
    # Находим последнее сообщение пользователя, чтобы искать по нему в Qdrant
    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_query = msg.get("content", "")
            break

    log_event(
        body=f"Starting RAG pipeline for request: '{user_query[:50]}...'",
        event_name="rag_pipeline_start",
        attributes={"model": model_name}
    )
    
    start_time = time.perf_counter()

    # --- АСИНХРОННЫЙ RAG ЭТАП ---
    # 1. Загружаем свежий системный промпт из MinIO
    system_base = await load_prompt_from_minio("system_prompt.md")
    
    # 2. Ищем релевантный контекст в Qdrant по запросу пользователя
    rag_context = ""
    if user_query:
        rag_context = await search_similar_knowledge(query_text=user_query, limit=2)

    # 3. Собираем финальный обогащенный системный промпт
    enriched_system_content = f"{system_base}\n\n"
    if rag_context:
        enriched_system_content += (
            f"USE THE FOLLOWING EXTRACTED CONTEXT TO ANSWER THE USER:\n"
            f"{rag_context}\n"
        )

    # 4. Модифицируем входящий body запроса: подменяем system prompt на наш RAG-промпт
    system_msg_found = False
    for msg in messages:
        if msg.get("role") == "system":
            msg["content"] = enriched_system_content
            system_msg_found = True
            break
            
    if not system_msg_found:
        # Если Continue не прислал system блок, принудительно вставляем его в начало
        messages.insert(0, {"role": "system", "content": enriched_system_content})
        
    body["messages"] = messages
    # ----------------------------

    ollama_url = f"{get_ollama_url(app_config)}/v1/chat/completions"
    
    # Проверка доступности LLM
    async with httpx.AsyncClient() as client:
        try:
            base_url = get_ollama_url(app_config)
            await client.get(base_url, timeout=2.0)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama core container is unavailable."
            )

    async def stream_generator():
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", ollama_url, json=body) as response:
                    if response.status_code != 200:
                        yield f"data: {{\"error\": \"Ollama error {response.status_code}\"}}\n\n".encode('utf-8')
                        return

                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk
                            
            end_time = time.perf_counter()
            generation_time = round(end_time - start_time, 3)
            
            log_event(
                body=f"RAG Chat completed successfully in {generation_time}s",
                event_name="rag_chat_success",
                attributes={
                    "model": model_name,
                    "generation_time_seconds": generation_time,
                    "status": "success",
                    "context_injected": bool(rag_context)
                }
            )
        except Exception as e:
            yield f"data: {{\"error\": \"Stream interrupted\"}}\n\n".encode('utf-8')

    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
