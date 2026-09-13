from datetime import datetime
from metrics.telemetry import log_event

def get_system_time() -> str:
    """Возвращает точное текущее локальное системное время бэкенда."""
    log_event(body="Executing tool: get_system_time", event_name="tool_system_time")
    now = datetime.now()
    return f"⏰ [System Clock] Точное системное время на сервере: {now.strftime('%Y-%m-%d %H:%M:%S')} (Локальное время хоста)"
