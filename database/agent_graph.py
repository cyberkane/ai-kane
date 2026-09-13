import os
import re
import json
import time
import httpx
from typing import Annotated, Sequence, TypedDict 
from typing_extensions import TypedDict as ExtTypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver 
from metrics.telemetry import log_event

from tools.registry import TOOLS_REGISTRY

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

tools = list(TOOLS_REGISTRY.values())
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
    """Асинхронный узел вызова локальной LLM с защитой от бесконечных циклов фоллбэка"""
    chat_url, model_name = get_ollama_chat_config()
    
    # 1. Проверяем, выполнялся ли уже инструмент на ПРЕДЫДУЩЕМ шаге в этой сессии
    has_tool_ran = any(msg.type == "tool" for msg in state.get("messages", []))
    
    # Сразу извлекаем текст запроса пользователя
    user_query = ""
    for msg in reversed(state.get("messages", [])):
        if msg.type == "human":
            user_query = msg.content
            break

    # 2. Если инструмент уже выполнился (круг замкнулся), мы просто отдаем результат пользователю
    if has_tool_ran:
        print("🔄 [LangGraph] Второй круг: инструмент выполнен. Формируем финальный ответ...")
        # Берем самый последний ToolMessage из истории, чтобы показать его содержимое
        last_tool_msg = [msg for msg in state["messages"] if msg.type == "tool"][-1]
        
        # Заставляем модель просто вернуть результат утилиты без повторных вызовов
        final_content = (
            f"Операция успешно завершена бэкендом.\n\n"
            f"Результат работы системы автотестов:\n{last_tool_msg.content}"
        )
        return {"messages": [AIMessage(content=final_content)]}

    # --- ПЕРВЫЙ КРУГ: Готовим запрос в Ollama ---
    from database.storage import load_prompt_from_minio
    system_base = await load_prompt_from_minio("system_prompt.md")
    if not system_base:
        system_base = "Ты — продвинутый локальный ИИ-помощник по имени MarmAI."

    tool_instructions = (
        f"{system_base}\n\n"
        "Ты имеешь доступ к инструментам. Если пользователю нужна погода, время или генерация тестов, "
        "ты ОБЯЗАН ответить СТРОГО в формате JSON без лишнего текста:\n"
        "{\"tool_call\": {\"name\": \"имя_инструмента\", \"arguments\": {\"аргумент\": \"значение\"}}}\n"
        "Доступные инструменты:\n"
        "- get_weather_forecast (аргумент: location)\n"
        "- get_system_time (без аргументов)\n"
        "- check_infrastructure_status (без аргументов)\n"
        "- generate_autotest_for_file (аргумент: file_path)\n"
    )
    
    ollama_messages = [{"role": "system", "content": tool_instructions}]
    for msg in state.get("messages", []):
        if msg.type == "system": continue
        elif msg.type == "human": ollama_messages.append({"role": "user", "content": msg.content})
        elif msg.type == "ai": ollama_messages.append({"role": "assistant", "content": msg.content})

    try:
        log_event(body=f"Agent graph execution step", event_name="graph_llm_start")
        
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
        
        # Умный парсинг JSON вызова инструмента
        is_tool_parsed = False
        try:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if "tool_call" in parsed:
                    call_info = parsed["tool_call"]
                    ai_message.tool_calls = [{
                        "name": call_info["name"],
                        "args": call_info.get("arguments", {}),
                        "id": f"call_{int(time.time())}"
                    }]
                    is_tool_parsed = True
                    print(f"🎯 [LangGraph] Модель успешно вызвала инструмент: {call_info['name']}")
        except:
            pass

        # Надежный фоллбэк: если JSON не сгенерирован, но пользователь просит автотесты
        if not is_tool_parsed and user_query:
            if "автотест" in user_query.lower() or "тест" in user_query.lower():
                file_match = re.search(r"([\w\-/]+\.py)", user_query)
                target_file = file_match.group(1) if file_match else "functions/chat.py"
                
                ai_message.tool_calls = [{
                    "name": "generate_autotest_for_file",
                    "args": {"file_path": target_file},
                    "id": f"call_forced_{int(time.time())}"
                }]
                print(f"⚡ [LangGraph ФОЛЛБЭК] Принудительный запуск генератора тестов для {target_file}")

        return {"messages": [AIMessage(content=content) if not hasattr(ai_message, 'tool_calls') else ai_message]}
        
    except Exception as exc:
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
