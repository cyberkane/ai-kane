# -*- coding: utf-8 -*-
import json
import inspect
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Импортируем твои реальные структуры из реестра
from tools.registry import TOOLS_REGISTRY, TOOLS_SCHEMAS

router = APIRouter()

class AgentRequest(BaseModel):
    messages: list
    model: str = "llama3.1:8b"

@router.post("/v1/agent/run")
async def run_agent(body: AgentRequest):
    """
    Эндпоинт оркестрации агента. Подтягивает схемы TOOLS_SCHEMAS,
    передает их в LLM и автоматически выполняет привязанный Python-код из TOOLS_REGISTRY.
    """
    
    # Формируем payload для Ollama, используя твои схемы
    ollama_payload = {
        "model": body.model,
        "messages": body.messages,
        "stream": False
    }
    
    # Передаем инструменты, если они описаны в реестре
    if TOOLS_SCHEMAS:
        ollama_payload["tools"] = TOOLS_SCHEMAS
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("http://localhost:11434/api/chat", json=ollama_payload, timeout=30.0)
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Ollama error: {response.text}")
                
            res_json = response.json()
            message = res_json.get("message", {})
            tool_calls = message.get("tool_calls", [])
            
            # ВЫПОЛНЕНИЕ ИНСТРУМЕНТОВ (Tool Execution):
            if tool_calls:
                for call in tool_calls:
                    func_name = call.get("function", {}).get("name")
                    arguments = call.get("function", {}).get("arguments", {})
                    
                    # Декодируем аргументы, если они прилетели строкой
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except Exception:
                            arguments = {}
                    
                    print(f"🎯 [ИИ-АГЕНТ] Вызов инструмента: {func_name} с аргументами {arguments}")
                    
                    # Проверяем наличие функции в твоем маппинге TOOLS_REGISTRY
                    if func_name in TOOLS_REGISTRY:
                        func = TOOLS_REGISTRY[func_name]
                        
                        try:
                            # Проверяем, асинхронная ли функция (async def) или обычная (def)
                            if inspect.iscoroutinefunction(func):
                                result_data = await func(**arguments)
                            else:
                                result_data = func(**arguments)
                                
                            return {
                                "role": "assistant",
                                "content": f"🤖 [MarmAI Вызов] {result_data}"
                            }
                        except Exception as tool_err:
                            return {
                                "role": "assistant",
                                "content": f"❌ Ошибка внутри инструмента '{func_name}': {str(tool_err)}"
                            }
                    else:
                        return {
                            "role": "assistant",
                            "content": f"❌ Ошибка: Инструмент '{func_name}' вызван моделью, но отсутствует в TOOLS_REGISTRY"
                        }
            
            # Если модель просто сгенерировала текст
            return {
                "role": "assistant",
                "content": message.get("content", "")
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent workflow crashed: {str(e)}")
