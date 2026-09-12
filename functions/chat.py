import os
import time
import httpx
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from metrics.telemetry import log_event

router = APIRouter()

def get_ollama_url(app_config: dict) -> str:
    """Функция для умной настройки адреса Ollama при локальном запуске"""
    chat_cfg = app_config.get("chat", {})
    host = chat_cfg.get("host", "http://localhost")
    port = chat_cfg.get("port", "11434")
    
    if "ollama_core" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    return f"{host}:{port}"

@router.post("/chat/completions")
async def proxy_chat(request: Request):
    from main import app_config

    body = await request.json()
    model_name = body.get('model', 'unknown')
    
    log_event(
        body=f"Received LLM generation request for model: {model_name}",
        event_name="llm_request_start",
        attributes={"model": model_name, "status": "info"}
    )
    
    ollama_url = f"{get_ollama_url(app_config)}/v1/chat/completions"
    start_time = time.perf_counter()
    
    # Быстрая проверка доступности
    async with httpx.AsyncClient() as client:
        try:
            base_url = get_ollama_url(app_config)
            await client.get(base_url, timeout=2.0)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            log_event(
                body=f"Failed to connect to Ollama at {base_url}: {str(e)}",
                event_name="llm_request_error",
                attributes={"model": model_name, "status": "error", "error_type": "ConnectError"}
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama core container is unavailable."
            )

    # Асинхронный генератор байтового потока
    async def stream_generator():
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Отправляем EXACTLY тот же body, что прислал Continue
                async with client.stream("POST", ollama_url, json=body) as response:
                    if response.status_code != 200:
                        yield f"data: {{\"error\": \"Ollama error {response.status_code}\"}}\n\n".encode('utf-8')
                        return

                    # Читаем АСИНХРОННО сырые куски байт, которые шлет Ollama
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk # Отдаем байты напрямую без изменений
                            
            end_time = time.perf_counter()
            generation_time = round(end_time - start_time, 3)
            
            log_event(
                body=f"LLM generation successfully completed in {generation_time}s",
                event_name="llm_request_end",
                attributes={
                    "model": model_name,
                    "generation_time_seconds": generation_time,
                    "status": "success"
                }
            )
        except Exception as e:
            log_event(
                body=f"Connection error during streaming: {str(e)}",
                event_name="llm_request_error",
                attributes={"model": model_name, "status": "error", "error_type": "StreamError"}
            )
            yield f"data: {{\"error\": \"Stream interrupted\"}}\n\n".encode('utf-8')

    # Возвращаем StreamingResponse с заголовками, отключающими буферизацию
    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
