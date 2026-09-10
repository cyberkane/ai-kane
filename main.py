import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from langchain_core.messages import HumanMessage, AIMessage

# Импортируем настроенный логгер и провайдер
from telemetry import logger, logger_provider 
from authorization import get_vault_secrets
from memory import save_chat_history, get_chat_history, clear_chat_history
from agent_graph import agent_app

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
    except Exception as e:
        # ➕ Импортируем traceback и выводим его в консоль Docker, чтобы СРАЗУ видеть виновника
        import traceback
        traceback.print_exc()
        logger.error(f"Ошибка выполнения графа LangGraph: {e}", extra={"error.message": str(e)})
        raise HTTPException(status_code=500, detail=f"LangGraph error: {str(e)}")
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
    # Если session_id не передан, мы не сможем задействовать чекпоинтер LangGraph
    if not payload.session_id:
        raise HTTPException(status_code=400, detail="session_id обязателен для работы LangGraph")
        
    logger.info("Обработка запроса через LangGraph StateGraph", extra={"session_id": payload.session_id})
    
    # Настраиваем конфигурацию сессии (thread_id) для чекпоинтера Dragonfly
    config = {"configurable": {"thread_id": payload.session_id}}
    
    try:
        # Входное состояние для графа — текущее сообщение пользователя
        inputs = {"messages": [HumanMessage(content=payload.prompt)]}
        
        # Асинхронно запускаем граф. Благодаря чекпоинтеру, LangGraph сам извлечет
        # из Dragonfly всю историю прошлых шагов этой сессии!
        output = await agent_app.ainvoke(inputs, config=config)
        
        # Забираем самое последнее сообщение, сгенерированное графом
        final_message = output["messages"][-1].content
        
        return {
            "status": "success",
            "session_id": payload.session_id,
            "response": final_message
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # ➕ Извлекаем подробную ошибку через repr(e) вместо пустого str(e)
        detailed_error = repr(e)
        logger.error(f"Ошибка выполнения графа LangGraph: {detailed_error}")
        
        raise HTTPException(status_code=500, detail=f"LangGraph error: {detailed_error}")

@app.delete("/api/v1/session/{session_id}")
async def delete_session(session_id: str):
    # Логируем начало операции с контекстом сессии
    logger.info(
        f"Запрос на очистку сессии: {session_id}", 
        extra={
            "session_id": session_id, 
            "action": "clear_history",
            "component": "fastapi_api"
        }
    )
    
    try:
        clear_chat_history(session_id)
        
        # Логируем успешное завершение удаления
        logger.info(
            f"История сессии {session_id} успешно удалена",
            extra={
                "session_id": session_id,
                "action": "clear_history",
                "status": "success"
            }
        )
        return {
            "status": "success", 
            "message": f"История сессии {session_id} полностью удалена из Dragonfly"
        }
        
    except Exception as e:
        # Логируем критический сбой, если Dragonfly недоступен
        logger.error(
            f"Не удалось удалить сессию {session_id}",
            extra={
                "session_id": session_id,
                "action": "clear_history",
                "status": "error",
                "error.message": str(e)
            }
        )
        raise HTTPException(status_code=500, detail=f"Ошибка удаления сессии: {str(e)}")

@app.get("/health")
async def health_check():
    vault_status = bool(vault_secrets)
    
    # Структурированный лог проверки здоровья
    logger.info(
        "Выполнен запрос проверки работоспособности (Healthcheck)",
        extra={
            "action": "healthcheck",
            "vault_connected": vault_status,
            "status": "success" if vault_status else "warning"
        }
    )
    
    # Если Vault не подключен, возвращаем статус 503 Service Unavailable
    if not vault_status:
        raise HTTPException(
            status_code=503, 
            detail={"status": "unhealthy", "vault_connected": False}
        )
        
    return {"status": "healthy", "vault_connected": True}