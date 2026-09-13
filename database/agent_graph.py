import os
import re
import json
import time
import httpx
from typing import Annotated, Sequence
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver 
from metrics.telemetry import log_event

# --- 1. ОПРЕДЕЛЕНИЕ ИНСТРУМЕНТОВ (TOOLS) ---
@tool
def get_weather_forecast(location: str) -> str:
    """Возвращает текущую погоду для указанного города или локации."""
    return f"В локации '{location}' сейчас солнечно, +22°C, мармеладный ветер."

@tool
def get_system_time() -> str:
    """Возвращает текущее системное время сервера."""
    from datetime import datetime
    return f"Текущее время на сервере: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

tools = [get_weather_forecast, get_system_time]
tool_node = ToolNode(tools)


# --- 2. ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ (STATE) ---
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# --- 3. ХЕЛПЕР ДЛЯ ДИНАМИЧЕСКИХ URL ИЗ CONFIG.INI ---
def get_ollama_chat_config() -> tuple[str, str]:
    """Извлекает актуальные адреса и модель для агента из общего конфига"""
    from main import app_config
    chat_cfg = app_config.get("chat", {})
    host = chat_cfg.get("host", "http://localhost")
    port = chat_cfg.get("port", "11434")
    model = chat_cfg.get("model", "llama3.1:8b")
    
    if "ollama_core" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    return f"{host}:{port}/api/chat", model


# --- 4. АСИНХРОННЫЙ УЗЕЛ МОДЕЛИ (NODES) ---
async def call_model(state: AgentState):
    """Асинхронный узел вызова локальной LLM с поддержкой формата инструментов"""
    chat_url, model_name = get_ollama_chat_config()
    
    # 1. Извлекаем базовый системный промпт из MinIO (через сохраненный стейт в main)
    from main import app_config
    from database.storage import load_prompt_from_minio
    
    system_base = await load_prompt_from_minio("system_prompt.md")
    if not system_base:
        system_base = "Ты — продвинутый локальный ИИ-помощник по имени MarmAI."

    # Формируем жесткую инструкцию для локальной модели, как вызывать инструменты
    tool_instructions = (
        f"{system_base}\n\n"
        "Ты имеешь доступ к инструментам. Если пользователю нужна погода или время, "
        "ты ОБЯЗАН ответить СТРОГО в формате JSON без лишнего текста:\n"
        "{\"tool_call\": {\"name\": \"имя_инструмента\", \"arguments\": {\"аргумент\": \"значение\"}}}\n\n"
        "ВАЖНОЕ ПРАВИЛО: Если в истории диалога тебе УЖЕ пришел результат выполнения инструмента "
        "(строка вида 'Результат выполнения инструмента: ...'), ты ОБЯЗАН прочитать эти данные "
        "и развернуто передать их пользователю человеческим языком! Не пиши технические подтверждения."
        "\nДоступные инструменты:\n"
        "- get_weather_forecast (аргумент: location)\n"
        "- get_system_time (без аргументов)\n"
    )
    
    ollama_messages = [{"role": "system", "content": tool_instructions}]
    
    # 2. Переносим историю сообщений из графа LangGraph в Ollama формат
    for msg in state.get("messages", []):
        if msg.type == "system":
            continue
        elif msg.type == "human":
            ollama_messages.append({"role": "user", "content": msg.content})
        elif msg.type == "ai":
            ollama_messages.append({"role": "assistant", "content": msg.content})
        elif msg.type == "tool":
            ollama_messages.append({"role": "user", "content": f"Результат выполнения инструмента: {msg.content}"})
            
    try:
        log_event(body=f"Agent graph routing via model: {model_name}", event_name="graph_llm_start")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                chat_url,
                json={"model": model_name, "messages": ollama_messages, "stream": False},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
        content = result.get("message", {}).get("content", "")
        ai_message = AIMessage(content=content)
        
        # УМНЫЙ ПРОМЫШЛЕННЫЙ ПАРСЕР JSON ИЗ ТЕКСТА ОТВЕТА
        try:
            # Ищем любые фигурные скобки { ... } в ответе модели, игнорируя текст вокруг
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                json_str = match.group(0)
                parsed = json.loads(json_str)
                
                if "tool_call" in parsed:
                    call_info = parsed["tool_call"]
                    # Формируем нативный LangChain tool call
                    ai_message.tool_calls = [{
                        "name": call_info["name"],
                        "args": call_info.get("arguments", {}),
                        "id": f"call_{int(time.time())}"
                    }]
        except Exception as parse_err:
            print(f"⚠️ [LangGraph Парсер] Не удалось извлечь JSON вызова: {parse_err}")
            
        return {"messages": [ai_message]}
        
    except Exception as exc:
        # ВЫВОДИМ ТОЧНЫЙ ТЕКСТ ОШИБКИ В КОНСОЛЬ И В ОТВЕТ
        import traceback
        traceback.print_exc() # Выведет полный стек вызовов в консоль uvicorn
        
        log_event(body=f"Error inside graph node: {str(exc)}", event_name="graph_node_error", attributes={"status": "error"})
        return {"messages": [AIMessage(content=f"Ошибка внутри графа: {str(exc)}")]}


# --- 5. ОПРЕДЕЛЕНИЕ УСЛОВНЫХ ПЕРЕХОДОВ (ROUTING) ---
def should_continue(state: AgentState):
    """Анализирует последнее сообщение и решает: вызвать инструмент или завершить работу."""
    last_message = state["messages"][-1]
    
    # Если в узле call_model мы успешно распарсили tool_calls, переходим в узел инструментов
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return END


# --- 6. СБОРКА И КОМПИЛЯЦИЯ ГРАФА ---
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END
    }
)
workflow.add_edge("tools", "agent")

memory_checkpointer = MemorySaver()
agent_app = workflow.compile(checkpointer=memory_checkpointer)
