# -*- coding: utf-8 -*-
import os
import time
import httpx

def get_influx_config() -> tuple[str, str, str]:
    """
    Динамически извлекает параметры подключения к InfluxDB 3.0.
    Жестко форсирует использование базы marmai_observability.
    """
    from main import app_config
    
    db_cfg = app_config.get("database", {})
    host = db_cfg.get("host", "http://localhost")
    port = db_cfg.get("port", "8181")
    
    # Извлекаем токен напрямую из .env, чтобы избежать задержек инициализации
    token = os.getenv("INFLUXDB_BOOTSTRAP_TOKEN", "").strip()
    config_token = db_cfg.get("token", "").strip()
    if len(config_token) > 30:
        token = config_token
        
    # ЖЕСТКАЯ ФИКСАЦИЯ: Имя базы данных для InfluxDB 3.0 Core
    database = "marmai_observability"
    
    # Адаптивная маршрутизация хоста: локальная Windows против Docker-сети
    if ("influxdb" in host or "localhost" in host) and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    return f"{host}:{port}", token, database


async def write_to_influx(measurement: str, tags: dict, fields: dict) -> bool:
    """
    Полностью асинхронно записывает точку данных в InfluxDB 3.0 через HTTP API v2.
    Автоматически сериализует теги и филды в стандарт Line Protocol.
    """
    host_url, token, database = get_influx_config()
    
    if not token:
        print("⚠️ [InfluxDB] Пропущен токен авторизации. Запись невозможна.")
        return False

    # Сборка Line Protocol
    tag_str = ",".join([f"{k}={v}" for k, v in tags.items() if v is not None])
    
    field_list = []
    for k, v in fields.items():
        if isinstance(v, int):
            field_list.append(f"{k}={v}i")
        elif isinstance(v, float):
            field_list.append(f"{k}={v}")
        elif isinstance(v, str):
            safe_str = v.replace('"', '\\"')
            field_list.append(f'{k}="{safe_str}"')
        elif isinstance(v, bool):
            field_list.append(f"{k}={str(v).upper()}")
            
    field_str = ",".join(field_list)
    timestamp_ns = int(time.time_ns())
    
    # Строка Line Protocol обязательно должна заканчиваться переносом строки \n
    line_protocol_payload = f"{measurement},{tag_str} {field_str} {timestamp_ns}\n"
    
    # ИСПРАВЛЕНО: Официальный эндпоинт записи для InfluxDB 3.0 v3-core.
    # В v3-core параметры bucket и org маппятся напрямую на имя твоей базы данных.
    url = f"{host_url}/api/v2/write?bucket={database}&org={database}"
    
    headers = {
        "Authorization": f"Token {token}", # ИСПРАВЛЕНО: Формат 'Token <key>' для API v2
        "Content-Type": "text/plain; charset=utf-8"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, content=line_protocol_payload, headers=headers, timeout=3.0)
            
        if response.status_code in (200, 204):
            return True
                
        print(f"❌ [InfluxDB] Ошибка записи! Статус: {response.status_code}, Ответ: {response.text}")
        return False
            
    except Exception as e:
        print(f"❌ [InfluxDB] Критическая ошибка асинхронной отправки метрик: {e}")
        return False


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
