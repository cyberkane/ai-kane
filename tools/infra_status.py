import os
import asyncio
from metrics.telemetry import log_event

async def check_service_port(host: str, port: int, name: str) -> str:
    """Асинхронная проверка доступности одного порта"""
    # Умная подмена имен Docker-контейнеров на localhost для локальной Windows машины
    if not os.path.exists("/.dockerenv"):
        if any(x in host for x in ["vault", "minio", "influxdb", "qdrant", "dragonfly"]):
            host = "localhost"

    try:
        # Пробуем открыть асинхронное сетевое соединение с коротким таймаутом
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, int(port)), 
            timeout=1.5
        )
        writer.close()
        await writer.wait_closed()
        return f"  🟢 {name} -> Доступен ({host}:{port})"
    except:
        return f"  🔴 {name} -> НЕДОСТУПЕН! ({host}:{port})"

async def check_infrastructure_status() -> str:
    """Динамически сканирует порты всей инфраструктуры MarmAI на основе config.ini"""
    from main import app_config
    log_event(body="Executing tool: check_infrastructure_status", event_name="tool_infra_status_start")

    # Собираем конфигурационную карту на основе живых данных из config.ini
    services = {
        "HashiCorp Vault": (app_config.get("vault", {}).get("host", "localhost").replace("http://", ""), app_config.get("vault", {}).get("port", 8200)),
        "MinIO S3": (app_config.get("minio", {}).get("host", "localhost").replace("http://", ""), app_config.get("minio", {}).get("port", 9000)),
        "InfluxDB 3.0": (app_config.get("database", {}).get("host", "localhost").replace("http://", ""), app_config.get("database", {}).get("port", 8181)),
        "Qdrant DB": (app_config.get("vectors", {}).get("host", "localhost").replace("http://", ""), app_config.get("vectors", {}).get("port", 6333)),
        "Dragonfly Cache": (app_config.get("cache", {}).get("host", "localhost").replace("http://", ""), app_config.get("cache", {}).get("port", 6379))
    }

    # Запускаем ВСЕ сетевые проверки параллельно через asyncio.gather
    tasks = [check_service_port(host, port, name) for name, (host, port) in services.items()]
    results = await asyncio.gather(*tasks)

    report = ["📊 [Infra Status] Результаты сканирования кристаллической решётки портов:"]
    report.extend(results)
    
    log_event(body="Infrastructure status scan completed", event_name="tool_infra_status_end")
    return "\n".join(report)
