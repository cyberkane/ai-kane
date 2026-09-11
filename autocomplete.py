import os
import httpx
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

# Создаем роутер вместо app
router = APIRouter()

@router.post("/api/generate")
async def ollama_generate_gateway(request: dict):
    QWEN_URL = os.getenv("QWEN_URL", "http://ai_qwen_core:11435")
    model_name = request.get("model", "qwen2.5-coder:1.5b")
    prompt_text = request.get("prompt", "")
    should_stream = request.get("stream", True)
    request["stream"] = should_stream
    
    # 📊 АВТОМАТИЧЕСКИЙ ТРЕКИНГ АКТИВНОСТИ В ТАБЛИЦУ file_activity
    try:
        from analytics import log_file_activity
        
        asyncio.create_task(
            log_file_activity(
                project_id="marmai-backend",
                file_path="vs_code_inline_buffer",
                event_type="edit" if prompt_text else "focus",
                language="python" if "qwen" in model_name else "unknown",
                file_size_bytes=len(prompt_text)
            )
        )
    except Exception as ide_err:
        print(f"⚠️ Ошибка автотрекинга file_activity: {ide_err}")

    # Перенаправляем запрос автодополнения в реальную Ollama
    async def generate_stream_generator():
        # Увеличиваем таймаут, так как генерация больших блоков кода требует времени
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST", 
                f"{QWEN_URL}/api/generate", 
                json=request
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        yield line + "\n"

    if should_stream:
        return StreamingResponse(
            generate_stream_generator(), 
            media_type="application/x-ndjson"
        )
        
    # На случай, если вы где-то явно отключите стрим в конфигах Continue
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(f"{QWEN_URL}/api/generate", json=request)
        # Если Ollama вернула ошибку или не-JSON строку, не падаем
        try:
            return res.json()
        except Exception:
            from fastapi.responses import Response
            return Response(content=res.text, media_type="application/json")