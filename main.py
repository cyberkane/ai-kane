import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Импортируем настроенный логгер и провайдер
from telemetry import logger, logger_provider 
from authorization import get_vault_secrets
from memory import save_chat_history, get_chat_history, clear_chat_history

# Глобальная переменная для хранения секретов Vault
vault_secrets = {}

# Lifespan-контекст: код внутри выполнится ОДИН раз при запуске и завершении приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    global vault_secrets
    logger.info("Запуск FastAPI приложения ai_kane_agent...")
    try:
        from authorization import get_vault_secrets
        vault_secrets = get_vault_secrets(logger)
        logger.info("Инициализация Vault при старте успешно завершена")
    except Exception as err:
        logger.critical(f"Критическая ошибка старта: не удалось получить секреты Vault: {err}")
        raise err
    yield
    logger.info("Остановка FastAPI приложения...")
    logger_provider.shutdown()

app = FastAPI(title="AI Kane Agent Service", lifespan=lifespan)

# Описываем структуру входящего JSON-запроса
class PromptRequest(BaseModel):
    prompt: str
    session_id: str = None
    model: str = None

@app.post("/api/v1/generate")
async def generate_response(payload: PromptRequest):
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ai_ollama_core:11434")
    MODEL_NAME = payload.model or os.getenv("CHAT_MODEL", "llama3.1:8b")
    
    # Собираем массив сообщений с четким разделением ролей
    messages = []
    
    if payload.session_id:
        history = get_chat_history(payload.session_id)
        for msg in history:
            messages.append({
                "role": msg["role"], # Передаем строго 'user' или 'assistant'
                "content": msg["content"]
            })

    messages.append({
        "role": "user",
        "content": payload.prompt
    })

    logger.info("API-запрос на генерацию через /api/chat", extra={"session_id": payload.session_id})
    
    try:
        # Стучимся строго в чат-эндпоинт Ollama
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False
            },
            timeout=30
        )
        response.raise_for_status()
        result_data = response.json()
        
        # Парсим ответ чат-модели по стандарту Ollama
        model_response = result_data.get("message", {}).get("content", "")
        
        # Сохраняем в Dragonfly раздельные роли
        if payload.session_id:
            save_chat_history(payload.session_id, "user", payload.prompt)
            save_chat_history(payload.session_id, "assistant", model_response)

        return {
            "status": "success",
            "session_id": payload.session_id,
            "response": model_response
        }
        
    except Exception as e:
        logger.error("Ошибка при обращении к Ollama chat", extra={"error.message": str(e)})
        raise HTTPException(status_code=500, detail=f"Ollama chat error: {str(e)}")

@app.delete("/api/v1/session/{session_id}")
async def delete_session(session_id: str):
    logger.info(f"Запрос на очистку сессии: {session_id}")
    clear_chat_history(session_id)
    return {"status": "success", "message": f"История сессии {session_id} полностью удалена из Dragonfly"}

# Тестовый эндпоинт проверки работоспособности (Healthcheck)
@app.get("/health")
async def health_check():
    return {"status": "healthy", "vault_connected": bool(vault_secrets)}