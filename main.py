import os
import httpx
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from telemetry import logger, logger_provider 
from memory import save_chat_history, get_chat_history, clear_chat_history
from agent_graph import agent_app
from storage import init_prompt_storage, load_prompt_from_minio

vault_secrets = {}
agent_system_prompt = ""  

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vault_secrets, agent_system_prompt
    print("🚀 [System] Старт lifespan-контекста FastAPI приложения ai_kane_agent...")
    
    try:
        from authorization import get_vault_secrets
        vault_secrets = get_vault_secrets(logger)
        print("🔑 [System] Vault успешно вернул секреты.")
    except Exception as err:
        print(f"❌ [System] Critical Vault error: {err}")
        raise err
        
    try:
        print("📦 [System] Инициализация хранилища MinIO...")
        init_prompt_storage()  
        agent_system_prompt = load_prompt_from_minio("system_prompt.md")
        print(f"✅ [System] Промпт успешно загружен. Длина: {len(agent_system_prompt)} симв.")
    except Exception as s3_err:
        print(f"⚠️ [System] Ошибка MinIO, локальный режим: {s3_err}")

    yield
    print("🛑 [System] Остановка FastAPI приложения...")
    logger_provider.shutdown()

app = FastAPI(title="AI Kane Agent Service & Ollama Gateway", lifespan=lifespan)

class PromptRequest(BaseModel):
    prompt: str
    session_id: str = None
    model: str = None

# --- СТАРЫЙ КАСТОМНЫЙ ЭНДПОИНТ (Оставляем для тестов из PowerShell) ---
@app.post("/api/v1/generate")
async def generate_response(payload: PromptRequest):
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id обязателен")
    config = {"configurable": {"thread_id": payload.session_id}}
    try:
        from langchain_core.messages import HumanMessage
        inputs = {"messages": [HumanMessage(content=payload.prompt)]}
        output = await agent_app.ainvoke(inputs, config=config)
        return {"status": "success", "session_id": payload.session_id, "response": output["messages"][-1].content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=repr(e))

# =====================================================================
# 🔮 ЭМУЛЯЦИЯ OLLAMA API ДЛЯ ПЛАГИНА CONTINUE (VS CODE)
# =====================================================================

# 1. Список моделей (Continue запрашивает его при старте для валидации)
@app.get("/api/tags")
async def get_ollama_tags():
    logger.info("Continue запросил список доступных локальных моделей")
    return {
        "models": [
            {"name": "llama3.1:8b", "details": {"family": "llama"}},
            {"name": "qwen2.5-coder:1.5b", "details": {"family": "qwen2"}}
        ]
    }

# 2. Полноценный эндпоинт ЧАТА с поддержкой системного промпта из MinIO и стриминга (stream=true/false)
@app.post("/api/chat")
async def ollama_chat_gateway(request: dict):
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ai_ollama_core:11434")
    
    model_name = request.get("model", "llama3.1:8b")
    incoming_messages = request.get("messages", [])
    should_stream = request.get("stream", True)
    
    # Извлекаем входящие опции или создаем новые для управления креативностью
    options = request.get("options", {})
    
    # 🔥 КРИТИЧЕСКИ ВАЖНО ДЛЯ ХАРАКТЕРА: Поднимаем температуру и креативность,
    # иначе Llama будет игнорировать художественную часть системного промпта!
    options["temperature"] = 0.78
    options["top_p"] = 0.9
    options["presence_penalty"] = 0.6  # Стимулирует модель использовать новые мармеладные метафоры
    
    # Собираем итоговый массив сообщений
    final_messages = []
    
    # Подгружаем все md-файлы из MinIO, чтобы котик знал и роль, и архитектуру, и свою личность
    full_system_context = ""
    try:
        # Динамически докачиваем все инструкции, если они обновились в MinIO
        prompt = load_prompt_from_minio("system_prompt.md")
        architecture = load_prompt_from_minio("architecture.md")
        pipeline = load_prompt_from_minio("agent_pipeline.md")
        
        full_system_context = f"{prompt}\n\n{architecture}\n\n{pipeline}"
    except Exception as s3_err:
        print(f"⚠️ Ошибка склейки контекста из S3, используем базовый: {s3_err}")
        full_system_context = agent_system_prompt

    if full_system_context:
        final_messages.append({"role": "system", "content": full_system_context})
        
    # Добавляем историю сообщений из VS Code (исключая их внутренние системные промпты)
    for msg in incoming_messages:
        if msg.get("role") != "system":
            final_messages.append(msg)
            
    logger.info(
        f"Запрос MarmAI из VS Code направлен в Ollama с мармеладной температурой", 
        extra={"model": model_name, "stream": should_stream, "temperature": options["temperature"]}
    )

    # Payload для Ollama с нашими жесткими опциями личности
    ollama_payload = {
        "model": model_name, 
        "messages": final_messages, 
        "stream": True,
        "options": options # <-- Передаем параметры генерации
    }

    async def stream_generator():
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", 
                f"{OLLAMA_URL}/api/chat", 
                json=ollama_payload,
                timeout=60.0
            ) as response:
                async for chunk in response.aiter_lines():
                    if chunk:
                        yield chunk + "\n"

    if should_stream:
        return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
        
    # Для одиночных запросов
    ollama_payload["stream"] = False
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{OLLAMA_URL}/api/chat", json=ollama_payload, timeout=60.0)
        return res.json()

@app.delete("/api/v1/session/{session_id}")
async def delete_session(session_id: str):
    clear_chat_history(session_id)
    return {"status": "success", "message": f"Сессия {session_id} удалена"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "vault_connected": bool(vault_secrets)}
