import os
import httpx
import asyncio
from fastapi import APIRouter
from metrics.telemetry import log_event

router = APIRouter()

async def check_service(client: httpx.AsyncClient, name: str, url: str, expected_status: int = 200) -> dict:
    """Асинхронный хелпер для проверки одного сервиса"""
    try:
        # Делаем быстрый запрос с таймаутом 1.5 секунды
        response = await client.get(url, timeout=1.5)
        if response.status_code == expected_status:
            return {"status": "healthy", "details": f"Connected to {name}"}
        return {"status": "unhealthy", "details": f"Status code {response.status_code}"}
    except Exception as e:
        return {"status": "unhealthy", "details": str(e)}

@router.get("/health")
async def health_check():
    from main import app_config

    # Умная подмена хостов для локального запуска на Windows
    def get_local_host(cfg_name, default_port):
        cfg = app_config.get(cfg_name, {})
        host = cfg.get("host", "http://localhost")
        port = cfg.get("port", default_port)
        if not os.path.exists("/.dockerenv"):
            host = "http://localhost"
        return f"{host}:{port}"

    # Собираем URL для проверок
    vault_url = f"{get_local_host('vault', '8200')}/v1/sys/health"
    qdrant_url = f"{get_local_host('vectors', '6333')}/"
    # Для Dragonfly/Redis используем HTTP пинг, если у него включен http-порт, 
    # либо просто проверяем доступность порта
    dragonfly_url = f"{get_local_host('cache', '6379')}/" 

    async with httpx.AsyncClient() as client:
        # Создаем список асинхронных задач
        tasks = [
            check_service(client, "HashiCorp Vault", vault_url, expected_status=200),
            check_service(client, "Qdrant Vector DB", qdrant_url, expected_status=200),
        ]
        
        # Запускаем ВСЕ проверки ОДНОВРЕМЕННО
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
    health_status = {
        "vault": results[0],
        "qdrant": results[1]
    }
    
    # Определяем общий статус системы
    is_all_healthy = all(res.get("status") == "healthy" for res in results if isinstance(res, dict))
    global_status = "ok" if is_all_healthy else "degraded"

    log_event(
        body=f"Healthcheck executed. Status: {global_status}",
        event_name="healthcheck_run",
        attributes={"global_status": global_status}
    )

    return {"status": global_status, "services": health_status}
