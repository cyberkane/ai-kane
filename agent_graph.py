import os
import httpx
from typing import Annotated, Sequence
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
# Используем стабильный in-memory чекпоинтер для сохранения состояний графа
from langgraph.checkpoint.memory import MemorySaver 
from telemetry import logger

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

# Регистрируем инструменты в специальном узле LangGraph
tools = [get_weather_forecast, get_system_time]
tool_node = ToolNode(tools)


# --- 2. ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ (STATE) ---
class AgentState(TypedDict):
    # Поле messages накапливает историю реплик и шагов рассуждения
    messages: Annotated[Sequence[BaseMessage], add_messages]


# --- 3. АСИНХРОННЫЙ УЗЕЛ МОДЕЛИ (NODES) ---
async def call_model(state: AgentState):
    """Асинхронный узел, который гарантированно внедряет актуальный промпт из MinIO."""
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ai_ollama_core:11434")
    MODEL_NAME = os.getenv("CHAT_MODEL", "llama3.1:8b")
    
    # 1. Инициализируем массив сообщений для Ollama
    ollama_messages = []
    
    # ➕ 2. ЖЕСТКО внедряем системный промпт из MinIO на САМОЕ ПЕРВОЕ МЕСТО
    from main import agent_system_prompt
    if agent_system_prompt:
        ollama_messages.append({"role": "system", "content": agent_system_prompt})
    else:
        # Резервный промпт на случай, если MinIO упадет
        ollama_messages.append({
            "role": "system", 
            "content": "Ты — продвинутый локальный ИИ-помощник по имени MarmAI."
        })
    
    # 3. Добавляем всю остальную историю диалога из состояния графа
    from langchain_core.messages import HumanMessage, AIMessage
    
    for msg in state.get("messages", []):
        # Игнорируем SystemMessage, если они случайно попали в историю графа, 
        # так как мы уже добавили главный промпт выше
        if msg.__class__.__name__ == "SystemMessage":
            continue
        elif isinstance(msg, HumanMessage) or msg.__class__.__name__ == "HumanMessage":
            ollama_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage) or msg.__class__.__name__ == "AIMessage":
            ollama_messages.append({"role": "assistant", "content": msg.content})
            
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": MODEL_NAME,
                    "messages": ollama_messages,
                    "stream": False
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
        content = result.get("message", {}).get("content", "")
        return {"messages": [AIMessage(content=content)]}
        
    except Exception as exc:
        logger.error(f"Ошибка внутри асинхронного узла call_model: {exc}")
        return {"messages": [AIMessage(content=f"Ошибка генерации: {str(exc)}")]}


# --- 4. ОПРЕДЕЛЕНИЕ УСЛОВНЫХ ПЕРЕХОДОВ (ROUTING) ---
def should_continue(state: AgentState):
    """Анализирует последнее сообщение и решает: вызвать инструмент или завершить работу."""
    last_message = state["messages"][-1]
    
    # Если модель сгенерировала нативный вызов инструмента (tool_calls), идем в узел инструментов
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # Если вызовов нет — завершаем выполнение графа и отдаем ответ пользователю
    return END


# --- 5. СБОРКА И КОМПИЛЯЦИЯ ГРАФА ---
workflow = StateGraph(AgentState)

# Добавляем узлы в граф состояний
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

# Настраиваем связи (ребра графа)
workflow.add_edge(START, "agent")

# Задаем условный переход: после узла 'agent' вызывается функция should_continue
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END
    }
)

# После выполнения любого инструмента граф всегда возвращается к модели для анализа результатов
workflow.add_edge("tools", "agent")

# Компилируем граф с чекпоинтером памяти процессов
memory_checkpointer = MemorySaver()
agent_app = workflow.compile(checkpointer=memory_checkpointer)

logger.info("Граф LangGraph успешно скомпилирован с MemorySaver чепоинтером")
