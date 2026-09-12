import os
import json
import time
import httpx
import uuid
import subprocess
import socket
from datetime import datetime
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from metrics.telemetry import logger
from analytics import log_agent_telemetry

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ai_ollama_core:11435")
MODEL_NAME = os.getenv("CHAT_MODEL", "llama3.1:8b")

# --- 🛠️ 1. ОПРЕДЕЛЕНИЕ СИСТЕМНЫХ ИНСТРУМЕНТОВ MARMAI ---

def get_system_time() -> str:
    now = datetime.now()
    return f"⏰ [System Clock] Точное системное время на сервере: {now.strftime('%Y-%m-%d %H:%M:%S')} (Локальное время хоста)"


def run_project_tests(module_path: str = "") -> str:
    """Запускает pytest для проверки работоспособности модулей ИИ-агента."""
    print(f"🧪 [MarmAI Agent] Запуск тестирования для пути: {module_path or 'root'}...")
    try:
        # Формируем команду запуска тестов
        cmd = ["pytest", "-v"]
        if module_path:
            cmd.append(module_path)
            
        # Запускаем pytest внутри контейнера
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15.0)
        
        status_line = "✅ Тесты успешно пройдены!" if result.returncode == 0 else "❌ Обнаружены упавшие тесты!"
        return f"📋 [Test Runner] Статус: {status_line}\n\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except FileNotFoundError:
        return "⚠️ [Test Runner] Утилита pytest не установлена в текущем окружении контейнера."
    except Exception as e:
        return f"❌ [Test Runner] Ошибка при выполнении тестов: {str(e)}"


def check_infrastructure_status() -> str:
    """Проверяет доступность портов всех ключевых контейнеров в сети docker-net."""
    print("🌐 [MarmAI Agent] Сканирование портов инфраструктуры...")
    
    # Список критических сервисов нашей мармеладной архитектуры
    services = {
        "ai_vault_core (HashiCorp Vault)": ("ai_vault_core", 8200),
        "minio_core (MinIO Object S3)": ("minio_core", 9000),
        "influxdb3_core (InfluxDB 3.0)": ("influxdb3_core", 8181),
        "qdrant_core (Qdrant Vector DB)": ("qdrant_core", 6333),
        "ai_dragonfly (Dragonfly Cache)": ("ai_dragonfly", 6379)
    }
    
    report = ["📊 [Infra Status] Результаты сканирования кристаллической решётки портов:"]
    
    for name, (host, port) in services.items():
        try:
            # Пытаемся открыть сокет-соединение с таймаутом 2 секунды
            with socket.create_connection((host, port), timeout=2.0):
                report.append(f"  🟢 {name} -> Доступен (Порт {port})")
        except (socket.timeout, ConnectionRefusedError, socket.gaierror):
            report.append(f"  🔴 {name} -> НЕДОСТУПЕН! (Порт {port})")
            
    return "\n".join(report)


# Реестр функций для выполнения графом
TOOLS_REGISTRY = {
    "get_system_time": get_system_time,
    "run_project_tests": run_project_tests,
    "check_infrastructure_status": check_infrastructure_status
}

# Описания инструментов (Схемы) для Ollama
TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_time",
            "description": "Возвращает точное текущее локальное системное время бэкенда.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_project_tests",
            "description": "Запускает pytest тесты ИИ-агента для проверки работоспособности кода и ассертов.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module_path": {"type": "string", "description": "Опциональный путь к конкретному файлу тестов (например, tests/test_main.py)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_infrastructure_status",
            "description": "Сканирует порты и проверяет статус здоровья контейнеров Vault, MinIO, InfluxDB, Qdrant и Dragonfly.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

# --- 2. СОСТОЯНИЕ И УЗЛЫ ГРАФА ---

class ToolsAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    start_time: float
    current_tool: str
    tool_input: str
    tool_output: str
    tool_call_id: str


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
        
        has_tool_reply = any(m.__class__.__name__ == "ToolMessage" for m in state["messages"])
        
        if tool_calls and not has_tool_reply:
            call = tool_calls if isinstance(tool_calls, list) else tool_calls
            if isinstance(call, list) and len(call) > 0:
                call = call[0]
            function_data = call.get("function", {})
            tool_name = function_data.get("name")
            tool_args = function_data.get("arguments", {})
            generated_id = str(uuid.uuid4())
            
            print(f"🎯 [MarmAI Agent] Модель инициировала вызов: {tool_name}")
            
            return {
                "messages": [AIMessage(content=f"📝 Активирую системную утилиту {tool_name}...")],
                "current_tool": tool_name,
                "tool_input": json.dumps(tool_args, ensure_ascii=False),
                "tool_call_id": generated_id
            }
            
        return {"messages": [AIMessage(content=content)], "current_tool": "", "tool_input": "", "tool_output": ""}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Мрр-сбой генерации инструментов: {str(e)}")]}


async def execute_tool_node(state: ToolsAgentState):
    tool_name = state.get("current_tool")
    tool_call_id = state.get("tool_call_id", "call_123")
    tool_args_str = state.get("tool_input", "{}")
    
    print(f"🛠️ [MarmAI Agent] Выполнение утилиты {tool_name} на бэкенде...")
    tool_func = TOOLS_REGISTRY.get(tool_name)
    
    if not tool_func:
        output = "Инструмент не зарегистрирован."
    else:
        # Разбираем аргументы
        try:
            args = json.loads(tool_args_str) if tool_args_str else {}
        except:
            args = {}
            
        if tool_name == "run_project_tests":
            path_arg = args.get("module_path", "")
            # 🎯 Направляем pytest строго в твою созданную папку ./test !
            if not path_arg or path_arg == "None" or path_arg == "{}":
                path_arg = "tests"
            output = tool_func(module_path=path_arg)
            
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
            prompt_tokens=100, completion_tokens=len(last_msg) // 4,
            latency_ms=latency_ms,
            tool_called=state.get("current_tool", ""),
            input_payload=state.get("tool_input", ""),
            output_payload=state.get("tool_output", last_msg)
        )
    )
    print(f"📊 [Telemetry] Шаг автономного инструмента залогирован. Latency: {latency_ms}ms")
    return state

def should_continue_routing(state: ToolsAgentState):
    has_tool_reply = any(m.__class__.__name__ == "ToolMessage" for m in state["messages"])
    if state.get("current_tool") and not has_tool_reply:
        return "execute_tool"
    return "trace_telemetry"

# --- СБОРКА ГРАФА ---
workflow = StateGraph(ToolsAgentState)
workflow.add_node("call_model", call_ollama_with_tools)
workflow.add_node("execute_tool", execute_tool_node)
workflow.add_node("trace_telemetry", trace_telemetry_node)

workflow.set_entry_point("call_model")
workflow.add_conditional_edges("call_model", should_continue_routing, {"execute_tool": "execute_tool", "trace_telemetry": "trace_telemetry"})
workflow.add_edge("execute_tool", "call_model")
workflow.add_edge("trace_telemetry", END)

tools_agent_app = workflow.compile()