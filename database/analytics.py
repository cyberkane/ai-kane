import os
from influxdb_client_3 import InfluxDBClient3, Point
from metrics.telemetry import logger

INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb3_core:8181")
INFLUX_TOKEN = os.getenv("INFLUX_BOOTSTRAP_TOKEN", "apiv3_wyuoazW6_gobjHm2EzI-4HD7syNABkG6gWOw4p3loAlGjlK1uzbMVYDdx-44_ZLzKf_JK0Ro6zkOHbgOo8RNHw")
INFLUX_DATABASE = "marmai_observability"

client = None

try:
    if INFLUX_TOKEN:
        print(f"📊 [Analytics] Переключение на новую архитектуру MarmAI на хост {INFLUX_URL}...")
        client = InfluxDBClient3(
            host=INFLUX_URL,
            token=INFLUX_TOKEN,
            database=INFLUX_DATABASE
        )
        print("📊 [Analytics] Клиент InfluxDB 3 успешно настроен под новые таблицы.")
except Exception as e:
    print(f"❌ [Analytics] Ошибка инициализации клиента: {e}")
    client = None


async def log_agent_telemetry(session_id: str, graph_name: str, node_name: str, model_name: str, status: str, 
                              prompt_tokens: int, completion_tokens: int, latency_ms: int, 
                              tool_called: str = "", input_payload: str = "", output_payload: str = "", error_message: str = ""):
    """Таблица 3: Трейсинг и аудит каждого шага графа LangGraph / Ollama чата."""
    if not client:
        return
    try:
        point = (
            Point("agent_telemetry")
            .tag("session_id", str(session_id))
            .tag("graph_name", str(graph_name))
            .tag("node_name", str(node_name))
            .tag("model_name", str(model_name))
            .tag("status", str(status))
            .field("prompt_tokens", int(prompt_tokens))
            .field("completion_tokens", int(completion_tokens))
            .field("latency_ms", int(latency_ms))
            .field("tool_called", str(tool_called))
            .field("input_payload", str(input_payload))
            .field("output_payload", str(output_payload))
            .field("error_message", str(error_message))
        )
        client.write(point)
    except Exception as err:
        logger.error(f"Ошибка записи в agent_telemetry: {err}")


async def log_file_activity(project_id: str, file_path: str, event_type: str, language: str, 
                            cursor_line: int = 0, cursor_column: int = 0, lines_changed: int = 0, file_size_bytes: int = 0):
    """Таблица 2: Логирование активности фокуса и редактирования файлов в IDE."""
    if not client:
        return
    try:
        point = (
            Point("file_activity")
            .tag("project_id", str(project_id))
            .tag("file_path", str(file_path))
            .tag("event_type", str(event_type))
            .tag("language", str(language))
            .field("cursor_line", int(cursor_line))
            .field("cursor_column", int(cursor_column))
            .field("lines_changed", int(lines_changed))
            .field("file_size_bytes", int(file_size_bytes))
        )
        client.write(point)
    except Exception as err:
        logger.error(f"Ошибка записи в file_activity: {err}")


async def log_agent_configuration(project_id: str, config_type: str, priority_level: str, sub_category: str, version: str,
                                  title: str, content_text: str, author: str = "system"):
    """Таблица 1: Логирование слоев личности, правил и системных инструкций."""
    if not client:
        return
    try:
        point = (
            Point("agent_configuration")
            .tag("project_id", str(project_id))
            .tag("config_type", str(config_type))
            .tag("priority_level", str(priority_level))
            .tag("sub_category", str(sub_category))
            .tag("version", str(version))
            .field("title", str(title))
            .field("content_text", str(content_text))
            .field("author", str(author))
        )
        client.write(point)
    except Exception as err:
        logger.error(f"Ошибка записи в agent_configuration: {err}")


async def log_vcs_history(project_id: str, commit_hash: str, author: str, branch: str,
                          commit_message: str, files_added: str = "", files_modified: str = "", insertions: int = 0, deletions: int = 0):
    """Таблица 4: Хронология коммитов в Git для контекста ИИ."""
    if not client:
        return
    try:
        point = (
            Point("vcs_history")
            .tag("project_id", str(project_id))
            .tag("commit_hash", str(commit_hash))
            .tag("author", str(author))
            .tag("branch", str(branch))
            .field("commit_message", str(commit_message))
            .field("files_added", str(files_added))
            .field("files_modified", str(files_modified))
            .field("insertions", int(insertions))
            .field("deletions", int(deletions))
        )
        client.write(point)
    except Exception as err:
        logger.error(f"Ошибка записи в vcs_history: {err}")
