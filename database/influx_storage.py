# -*- coding: utf-8 -*-
import os
import time
import httpx
from metrics.telemetry import log_event

async def track_agent_telemetry(session_id: str, graph_name: str, node_name: str, model_name: str, 
                               status: str, prompt_tokens: int, completion_tokens: int, 
                               latency_ms: int, tool_called: str = "none") -> bool:
    """Хелпер для асинхронной записи телеметрии работы ИИ-агента"""
    tags = {
        "session_id": session_id,
        "graph_name": graph_name,
        "node_name": node_name,
        "model_name": model_name,
        "status": status
    }
    fields = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "tool_called": tool_called
    }
    return await write_to_influx("agent_telemetry", tags, fields)

def get_influx_config() -> tuple[str, str, str]:
    """
    Извлекает параметры подключения к InfluxDB 3.0 из глобального app_config.
    Учитывает запуск вне Docker-сети (на локальном хосте Windows).
    """
    from main import app_config
    
    db_cfg = app_config.get("database", {})
    host = db_cfg.get("host", "http://localhost")
    port = db_cfg.get("port", "8181")
    token = db_cfg.get("token", "")
    database = db_cfg.get("database", "marmai_observability")
    
    # Умная подмена хоста для локальной Windows-машины
    if "influxdb" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    return f"{host}:{port}", token, database


async def write_to_influx(measurement: str, tags: dict, fields: dict) -> bool:
    """
    Полностью асинхронно записывает точку данных в InfluxDB 3.0 через HTTP API.
    Автоматически сериализует теги и филды в стандарт Line Protocol.
    """
    host_url, token, database = get_influx_config()
    
    if not token:
        print("⚠️ [InfluxDB] Пропущен токен авторизации. Запись невозможна.")
        return False

    # 1. Формируем строку в формате Line Protocol:
    # measurement,tag1=val1,tag2=val2 field1=val1,field2=val2i timestamp
    tag_str = ",".join([f"{k}={v}" for k, v in tags.items() if v is not None])
    
    field_list = []
    for k, v in fields.items():
        if isinstance(v, int):
            field_list.append(f"{k}={v}i")  # Influx требует суффикс 'i' для целых чисел
        elif isinstance(v, float):
            field_list.append(f"{k}={v}")
        elif isinstance(v, str):
            # Строковые филды (строки) обязательно экранируются двойными кавычками
            safe_str = v.replace('"', '\\"')
            field_list.append(f'{k}="{safe_str}"')
        elif isinstance(v, bool):
            field_list.append(f"{k}={str(v).upper()}")
            
    field_str = ",".join(field_list)
    
    # Временная метка в наносекундах (стандарт InfluxDB)
    timestamp_ns = int(time.time_ns())
    
    line_protocol_payload = f"{measurement},{tag_str} {field_str} {timestamp_ns}\n"
    
    # URL для записи в InfluxDB 3.0 Core по HTTP
    url = f"{host_url}/v1/write?db={database}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain; charset=utf-8"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, content=line_protocol_payload, headers=headers, timeout=3.0)
            
        # Теперь список кодов (200 и 204) железно на месте!
        if response.status_code in (200, 204):
            return True
                
        print(f"❌ [InfluxDB] Ошибка записи! Статус: {response.status_code}, Ответ: {response.text}")
        return False
            
    except Exception as e:
        print(f"❌ [InfluxDB] Критическая ошибка асинхронной отправки метрик: {e}")
        return False