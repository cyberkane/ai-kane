import os
import asyncio
import httpx
from fastapi import APIRouter
from metrics.telemetry import log_event

router = APIRouter()

async def check_service(client: httpx.AsyncClient, name: str, url: str, expected_status: int = 200) -> dict:
    """Асинхронный хелпер для проверки одного сервиса"""
    try:
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

    # ИСПРАВЛЕНО: Используем нативные эндпоинты для локального окружения
    vault_url = f"{get_local_host('vault', '8200')}/v1/sys/seal-status"
    qdrant_url = get_local_host('vectors', '6333') + "/"

    async with httpx.AsyncClient() as client:
        # Запускаем проверки параллельно
        tasks = [
            check_service(client, "HashiCorp Vault", vault_url, expected_status=200),
            check_service(client, "Qdrant Vector DB", qdrant_url, expected_status=200),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
    # Формируем корректную карту статусов
    vault_res = results[0] if isinstance(results[0], dict) else {"status": "unhealthy", "details": str(results[0])}
    qdrant_res = results[1] if isinstance(results[1], dict) else {"status": "unhealthy", "details": str(results[1])}
    
    health_status = {
        "vault": vault_res,
        "qdrant": qdrant_res
    }
    
    # Определяем общий статус системы
    is_all_healthy = vault_res.get("status") == "healthy" and qdrant_res.get("status") == "healthy"
    global_status = "ok" if is_all_healthy else "degraded"

    log_event(
        body=f"Global infrastructure healthcheck executed. Status: {global_status}",
        event_name="healthcheck_run",
        attributes={"global_status": global_status}
    )

    return {"status": global_status, "services": health_status}
