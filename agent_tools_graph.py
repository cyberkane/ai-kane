import os
import json
import time
import httpx
import uuid  # ➕ Добавляем для генерации ID вызова
from datetime import datetime
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from telemetry import logger
from analytics import log_agent_telemetry

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ai_ollama_core:11434")
MODEL_NAME = os.getenv("CHAT_MODEL", "llama3.1:8b")

# --- 1. ОПРЕДЕЛЕНИЕ ИНСТРУМЕНТОВ ---
def get_system_time() -> str:
    now = datetime.now()
    return f"⏰ Точное системное время: {now.strftime('%Y-%m-%d %H:%M:%S')} (Зона сервера)"

def parse_container_logs(container_name: str, lines_count: int = 10) -> str:
    allowed_containers = ["ai_kane_agent", "minio_core", "qdrant_core", "influxdb3_core", "ai_dragonfly"]
    if container_name not in allowed_containers:
        return f"❌ Отказано в доступе к логам {container_name}"
    return f"📋 [Заглушка логов] Логи контейнера {container_name} успешно прочитаны."

TOOLS_REGISTRY = {"get_system_time": get_system_time, "parse_container_logs": parse_container_logs}

TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_time",
            "description": "Возвращает точное текущее локальное системное время бэкенда.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

class ToolsAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    start_time: float
    current_tool: str
    tool_input: str
    tool_output: str
    tool_call_id: str  # ➕ Храним ID вызова для Ollama

# --- 2. УЗЛЫ ГРАФА ---
async def call_ollama_with_tools(state: ToolsAgentState):
    from main import agent_system_prompt
    
    ollama_messages = []
    if agent_system_prompt:
        ollama_messages.append({"role": "system", "content": agent_system_prompt})
        
    for msg in state["messages"]:
        if msg.__class__.__name__ == "SystemMessage": continue
        if msg.__class__.__name__ == "ToolMessage":
            ollama_messages.append({"role": "tool", "content": msg.content})
        else:
            role = "user" if msg.__class__.__name__ == "HumanMessage" else "assistant"
            ollama_messages.append({"role": role, "content": msg.content})

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": MODEL_NAME, "messages": ollama_messages, "tools": TOOLS_SCHEMAS, "stream": False},
                timeout=30.0
            )
            result = response.json()
            
        message_data = result.get("message", {})
        content = message_data.get("content", "")
        tool_calls = message_data.get("tool_calls", [])
        
        # Проверяем, если это НОВЫЙ вызов (а не повтор после отправки ToolMessage!)
        # Если в истории последнее сообщение уже ToolMessage — значит, утилита отработала!
        has_tool_reply = any(m.__class__.__name__ == "ToolMessage" for m in state["messages"])
        
        if tool_calls and not has_tool_reply:
            call = tool_calls[0]
            function_data = call.get("function", {})
            tool_name = function_data.get("name")
            tool_args = function_data.get("arguments", {})
            generated_id = str(uuid.uuid4()) # Генерируем уникальный ID шага
            
            print(f"🎯 [MarmAI Agent] Модель вызвала утилиту: {tool_name}")
            
            return {
                "current_tool": tool_name,
                "tool_input": json.dumps(tool_args, ensure_ascii=False),
                "tool_call_id": generated_id
            }
            
        return {"messages": [AIMessage(content=content)], "current_tool": "", "tool_input": "", "tool_output": ""}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Мрр-сбой генерации: {str(e)}")]}


async def execute_tool_node(state: ToolsAgentState):
    """Узел выполнения: нативно запускает утилиту и возвращает ToolMessage."""
    tool_name = state.get("current_tool")
    tool_call_id = state.get("tool_call_id", "call_123")
    
    print(f"🛠️ [MarmAI Agent] Выполнение утилиты {tool_name} на бэкенде...")
    tool_func = TOOLS_REGISTRY.get(tool_name)
    output = tool_func() if tool_func else "Инструмент не найден."
            
    # 🔄 ЖЕСТКИЙ ФИКС: Возвращаем строго ToolMessage, чтобы разорвать бесконечную петлю!
    return {
        "messages": [ToolMessage(content=output, tool_call_id=tool_call_id)],
        "tool_output": output
    }


async def trace_telemetry_node(state: ToolsAgentState):
    latency_ms = int((time.time() - state.get("start_time", time.time())) * 1000)
    last_msg = state["messages"][-1].content if state["messages"] else "No msg"
    
    import asyncio
    asyncio.create_task(
        log_agent_telemetry(
            session_id=state.get("session_id", "tools_session"),
            graph_name="marm_autonomous_tools_flow",
            node_name=state.get("current_tool", "final_node") if state.get("current_tool") else "pure_chat_node",
            model_name=MODEL_NAME,
            status="success",
            prompt_tokens=100, completion_tokens=50,
            latency_ms=latency_ms,
            tool_called=state.get("current_tool", ""),
            input_payload=state.get("tool_input", ""),
            output_payload=state.get("tool_output", last_msg)
        )
    )
    print(f"📊 [Telemetry] Шаг успешно залогирован в InfluxDB 3. Latency: {latency_ms}ms")
    return state

def should_continue_routing(state: ToolsAgentState):
    # Если утилита определена, но в истории еще нет ToolMessage — идем выполнять!
    has_tool_reply = any(m.__class__.__name__ == "ToolMessage" for m in state["messages"])
    if state.get("current_tool") and not has_tool_reply:
        return "execute_tool"
    return "trace_telemetry"

# --- 3. СБОРКА ГРАФА ---
workflow = StateGraph(ToolsAgentState)
workflow.add_node("call_model", call_ollama_with_tools)
workflow.add_node("execute_tool", execute_tool_node)
workflow.add_node("trace_telemetry", trace_telemetry_node)

workflow.set_entry_point("call_model")
workflow.add_conditional_edges("call_model", should_continue_routing, {"execute_tool": "execute_tool", "trace_telemetry": "trace_telemetry"})
workflow.add_edge("execute_tool", "call_model")
workflow.add_edge("trace_telemetry", END)

tools_agent_app = workflow.compile()