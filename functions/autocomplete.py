import os
import time
import httpx
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from metrics.telemetry import log_event

router = APIRouter()

def get_autocomplete_url(app_config: dict) -> str:
    """Функция для настройки адреса модели автодополнения (Qwen)"""
    cfg = app_config.get("autocomplete", {})
    host = cfg.get("host", "http://localhost")
    port = cfg.get("port", "11435")
    
    # Если запуск локальный на Windows, подменяем имя контейнера на localhost
    if "qwen_core" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    return f"{host}:{port}"

@router.post("/completions")
async def proxy_autocomplete(request: Request):
    from main import app_config

    body = await request.json()
    model_name = body.get('model', 'qwen2.5-coder:1.5b')
    
    log_event(
        body=f"Received Autocomplete request for model: {model_name}",
        event_name="autocomplete_request_start",
        attributes={"model": model_name, "status": "info"}
    )
    
    base_url = get_autocomplete_url(app_config)
    autocomplete_url = f"{base_url}/v1/completions"
    start_time = time.perf_counter()
    
    # Быстрая асинхронная проверка доступности контейнера перед стримингом
    async with httpx.AsyncClient() as client:
        try:
            await client.get(base_url, timeout=1.5)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            log_event(
                body=f"Failed to connect to Autocomplete model at {base_url}: {str(e)}",
                event_name="autocomplete_request_error",
                attributes={"model": model_name, "status": "error", "error_type": "ConnectError"}
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Autocomplete core container is unavailable."
            )

    # Асингулятор генерации токенов кода
    async def stream_generator():
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", autocomplete_url, json=body) as response:
                    if response.status_code != 200:
                        yield f"data: {{\"error\": \"Ollama error {response.status_code}\"}}\n\n".encode('utf-8')
                        return

                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk
                            
            end_time = time.perf_counter()
            generation_time = round(end_time - start_time, 3)
            
            log_event(
                body=f"Autocomplete generated successfully in {generation_time}s",
                event_name="autocomplete_request_end",
                attributes={
                    "model": model_name,
                    "generation_time_seconds": generation_time,
                    "status": "success"
                }
            )
        except httpx.RemoteProtocolError as e:
            log_event(
                body=f"Connection with Autocomplete container lost: {str(e)}",
                event_name="autocomplete_request_error",
                attributes={"model": model_name, "status": "error", "error_type": "ProtocolError"}
            )
            yield f"Data: {{\"error\": \"Autocomplete stream interrupted\"}}\n\n"

    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Отключает буферизацию на прокси-серверах
        }
    )