import os
import time
import httpx
from fastapi import APIRouter, Request, HTTPException, status
from metrics.telemetry import log_event

router = APIRouter()

def get_embedder_url(app_config: dict) -> str:
    cfg = app_config.get("embeder", {})
    host = cfg.get("host", "http://localhost")
    port = cfg.get("port", "11436")
    
    # Если запуск локальный на Windows, подменяем имя контейнера на localhost
    if "nomic_core" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    return f"{host}:{port}"

@router.post("/embeddings")
async def proxy_embeddings(request: Request):
    from main import app_config

    body = await request.json()
    model_name = body.get('model', 'nomic-embed-text')
    
    log_event(
        body=f"Received Embeddings request for model: {model_name}",
        event_name="embeddings_request_start",
        attributes={"model": model_name, "status": "info"}
    )
    
    base_url = get_embedder_url(app_config)
    embeddings_url = f"{base_url}/v1/embeddings"
    start_time = time.perf_counter()
    
    # Асингулярный запрос к контейнеру эмбеддера
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Перенаправляем запрос в Ollama Nomic Embedder
            response = await client.post(embeddings_url, json=body)
            
            if response.status_code != 200:
                log_event(
                    body=f"Ollama embedder returned error status: {response.status_code}",
                    event_name="embeddings_request_error",
                    attributes={"model": model_name, "status": "error", "code": response.status_code}
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Ollama embedder service error"
                )
                
            end_time = time.perf_counter()
            generation_time = round(end_time - start_time, 3)
            
            log_event(
                body=f"Embeddings generated successfully in {generation_time}s",
                event_name="embeddings_request_end",
                attributes={
                    "model": model_name,
                    "generation_time_seconds": generation_time,
                    "status": "success"
                }
            )
            
            # Возвращаем JSON с векторами обратно в Continue
            return response.json()
            
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            log_event(
                body=f"Failed to connect to Embedder container at {base_url}: {str(e)}",
                event_name="embeddings_request_error",
                attributes={"model": model_name, "status": "error", "error_type": "ConnectError"}
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Embedder core container is unavailable."
            )