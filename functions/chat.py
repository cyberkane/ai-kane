# -*- coding: utf-8 -*-
import os
import re
import time
import json
import httpx
import inspect
import asyncio
from pydantic import BaseModel
from fastapi import APIRouter, Request, HTTPException, status, Body
from fastapi.responses import StreamingResponse
from metrics.telemetry import log_event

# Импортируем наши асинхронные методы баз данных и хранилища
from database.vector_storage import search_similar_knowledge
from database.storage import load_prompt_from_minio
from database.influx_storage import track_agent_telemetry
from tools.registry import TOOLS_SCHEMAS, TOOLS_REGISTRY

router = APIRouter()

class CommitPayload(BaseModel):
    hash: str
    message: str

def get_ollama_url(app_config: dict) -> str:
    chat_cfg = app_config.get("chat", {})
    host = chat_cfg.get("host", "http://localhost")
    port = chat_cfg.get("port", "11434")
    if "ollama_core" in host and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
    return f"{host}:{port}"

@router.post("/chat/completions")
async def proxy_chat(request: Request):
    from main import app_config

    print("\n🚀🚀🚀 [FASTAPI ШЛЮЗ] ВЫЗВАН RAG ПАЙПЛАЙН ЧАТА! 🚀🚀🚀")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        log_event(
            body="Failed to parse incoming request JSON body",
            event_name="invalid_json_payload",
            attributes={"status": "error"}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload provided."
        )

    model_name = body.get('model', 'unknown')
    messages = body.get('messages', [])
    
    # Извлекаем запрос пользователя
    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_query = msg.get("content", "")
            break

    print(f"🔎 [RAG ТЕСТ] Запрос пользователя: '{user_query}'")
    start_time = time.perf_counter()

    # 1. Скачиваем базовый промпт из MinIO S3 / Локального диска
    system_base = await load_prompt_from_minio("system_prompt.md")
    print(f"📦 [RAG ТЕСТ] Длина системного промпта из MinIO: {len(system_base)} символов")
    
    # 2. Ищем контекст в Qdrant
    rag_context = ""
    if user_query:
        rag_context = await search_similar_knowledge(query_text=user_query, limit=2)
    
    print(f"🔍 [RAG ТЕСТ] Найденный контекст в Qdrant:\n{rag_context if rag_context else '⚠️ НИЧЕГО НЕ НАЙДЕНО!'}\n")
    
    # 3. Собираем обогащенный промпт
    enriched_system_content = f"{system_base}\n\n"
    
    if rag_context:
        enriched_system_content += (
            f"=== ВАЖНАЯ ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ ===\n"
            f"Используй эти данные для ответа пользователю:\n{rag_context}\n"
            f"========================================\n"
        )
    
    try:
        from database.storage import redis_client
        project_arch = await redis_client.get("project:architecture")
        if project_arch:
            enriched_system_content += (
                f"=== ГЛОБАЛЬНАЯ АРХИТЕКТУРА И СТРУКТУРА ТЕКУЩЕГО ПРОЕКТА ===\n"
                f"{project_arch}\n"
                f"===========================================================\n\n"
            )
    except Exception as arch_cache_err:
        print(f"⚠️ Ошибка извлечения глобальной архитектуры: {arch_cache_err}")

    active_file_context = ""
    try:
        from database.storage import redis_client
        # Получаем все ключи исходного кода из Dragonfly
        all_keys = await redis_client.keys("project:code:*")
        if all_keys:
            enriched_system_content += "=== ИСХОДНЫЙ КОД СУЩЕСТВУЮЩИХ МОДУЛЕЙ В РЕПОЗИТОРИИ ===\n"
            for k in all_keys:
                file_name = k.replace("project:code:", "")
                # Расшифровываем байты в строку, если Redis вернул их в байтах
                if isinstance(file_name, bytes):
                    file_name = file_name.decode('utf-8')
                # Добавляем в промпт список файлов, чтобы модель знала, какие модули РЕАЛЬНО существуют
                enriched_system_content += f"- Доступный модуль: `{file_name}`\n"
            enriched_system_content += (
                "Если пользователь просит добавить задачу для файла, которого НЕТ в этом списке, "
                "значит этого модуля еще не существует на диске. В этом случае вызывай ТОЛЬКО manage_tasks.\n"
                "=======================================================\n\n"
            )
    except Exception as code_cache_err:
        print(f"⚠️ Ошибка извлечения карты исходного кода: {code_cache_err}")


    # =========================================================================
    # 4. СОБИРАЕМ ФИНАЛЬНЫЙ ОБОГАЩЕННЫЙ СИСТЕМНЫЙ ПРОМПТ (ИСПРАВЛЕНО)
    # =========================================================================
    enriched_system_content = f"{system_base}\n\n"
    
    # Сначала инжектируем то, что открыто на экране в VS Code (наивысший приоритет)
    if active_file_context:
        enriched_system_content += active_file_context
        
    # Затем добавляем долгосрочную память RAG из Qdrant
    if rag_context:
        enriched_system_content += (
            f"=== ВАЖНАЯ ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ (RAG) ===\n"
            f"Используй эти данные при необходимости:\n{rag_context}\n"
            f"==============================================\n"
        )
    # =========================================================================

    # 5. Модифицируем входящий массив сообщений: инжектируем или подменяем system prompt
    system_msg_found = False
    for msg in messages:
        if msg.get("role") == "system":
            msg["content"] = enriched_system_content
            system_msg_found = True
            break
            
    if not system_msg_found:
        messages.insert(0, {"role": "system", "content": enriched_system_content})
        
    body["messages"] = messages
    
    # 6. Умный ИИ-Фильтр и подготовка финального payload инструментов под API Ollama
    user_query_lower = user_query.lower()
    infrastructure_triggers = [
        "время", "time", "часы", "дата", "date", 
        "статус", "контейнер", "инфраструктур", "health", "систем",
        "тест", "pytest", "протестируй", "автотест", "сгенерируй",
        "задачу", "задач", "таск", "task", "трекер", "tracker", "бэклог", "backlog"
    ]
    
    is_tool_request = any(trigger in user_query_lower for trigger in infrastructure_triggers)
    
    if TOOLS_SCHEMAS and is_tool_request:
        body["tools"] = TOOLS_SCHEMAS
        body["tool_choice"] = "auto"
        print(f"🔧 [MarmAI ШЛЮЗ] Запрос признан техническим. Подключаю схемы инструментов.")
        
        # Строковое форсирование конкретных функций для Ollama при жестких совпадениях
        if "время" in user_query_lower or "time" in user_query_lower:
            body["tool_choice"] = "get_system_time"
        elif "статус" in user_query_lower or "инфраструктур" in user_query_lower:
            body["tool_choice"] = "check_infrastructure_status"
        # ИСПРАВЛЕНО: Принудительно направляем модель в таск-трекер, если она пытается управлять бэклогом
        elif any(w in user_query_lower for w in ["задач", "таск", "task", "трекер", "tracker", "бэклог", "backlog"]):
            body["tool_choice"] = "manage_tasks"
            print("🎯 [MarmAI ШЛЮЗ] Обнаружен запрос бэклога. Форсирую string tool_choice: manage_tasks")

    else:
        if "tools" in body:
            del body["tools"]
        if "tool_choice" in body:
            del body["tool_choice"]
        print(f"💬 [MarmAI ШЛЮЗ] Бытовой запрос. Слой инструментов изолирован.")
    # =========================================================================
    ollama_url = f"{get_ollama_url(app_config)}/v1/chat/completions"
    
    # Проверка доступности LLM
    async with httpx.AsyncClient() as client:
        try:
            await client.get(get_ollama_url(app_config), timeout=2.0)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise HTTPException(status_code=503, detail="Ollama container offline")

    def count_tokens_fallback(text: str) -> int:
        if not text:
            return 0
        return len(re.findall(r'\w+|[^\w\s]', text))

    # --- ПЕРЕХВАТ ВЫЗОВА ИНСТРУМЕНТОВ (Pre-flight Tool Check) ---
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            check_body = dict(body)
            check_body["stream"] = False
            
            response = await client.post(ollama_url, json=check_body)
            if response.status_code == 200:
                res_json = response.json()
                choices = res_json.get("choices", [])
                
                print(f"📦 [Ollama Debug Response]: {json.dumps(res_json, ensure_ascii=False)[:200]}...")
                
                if choices and isinstance(choices, list) and len(choices) > 0:
                    first_choice = choices[0]
                    message_payload = first_choice.get("message", {})
                    tool_calls = message_payload.get("tool_calls", [])
                    
                    if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
                        first_tool_call = tool_calls[0]
                        func_call = first_tool_call.get("function", {})
                        func_name = func_call.get("name")
                        args = func_call.get("arguments", {})
                        
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}
                            
                        print(f"🎯 [MarmAI ШЛЮЗ] СРАБОТАЛ ПЕРЕХВАТ! Вызов инструмента: '{func_name}'")
                        
                        if func_name in TOOLS_REGISTRY:
                            func = TOOLS_REGISTRY[func_name]
                            if inspect.iscoroutinefunction(func):
                                result_data = await func(**args)
                            else:
                                result_data = func(**args)
                        else:
                            result_data = f"Ошибка: Инструмент '{func_name}' отсутствует в TOOLS_REGISTRY."
                            
                        generation_time_ms = int((time.perf_counter() - start_time) * 1000)
                        
                        # Отправляем телеметрию вызова инструмента в InfluxDB 3.0
                        asyncio.create_task(
                            track_agent_telemetry(
                                session_id=body.get("session_id", "web_session"),
                                graph_name="marm_ai_v1",
                                node_name="proxy_chat_router",
                                model_name=model_name,
                                status="success",
                                prompt_tokens=count_tokens_fallback(user_query),
                                completion_tokens=count_tokens_fallback(str(result_data)),
                                latency_ms=generation_time_ms,
                                tool_called=func_name
                            )
                        )
                        
                        # Безопасная кодировка структуры через json.dumps
                        clean_content = f"🤖 [MarmAI Вызов] {result_data}"
                        chunk_dict = {
                            "choices": [{
                                "delta": {"content": clean_content},
                                "finish_reason": "stop",
                                "index": 0
                            }],
                            "model": model_name
                        }
                        safe_json_str = json.dumps(chunk_dict, ensure_ascii=False)
                        fake_stream_chunk = f"data: {safe_json_str}\n\ndata: [DONE]\n\n"
                        
                        return StreamingResponse(
                            iter([fake_stream_chunk.encode('utf-8')]),
                            media_type="text/event-stream"
                        )
                    else:
                        print("⚠️ [MarmAI ШЛЮЗ] Модель предпочла ответить текстом (массив tool_calls пуст).")
    except Exception as e:
        print(f"❌ [MarmAI ШЛЮЗ] Критическая ошибка проверки Tool Call: {e}. Откат на стандартный стрим.")

    # --- СТАНДАРТНЫЙ СТРИМИНГ ОТВЕТА (Если модель выдала обычный текст) ---
    async def stream_generator():
        full_completion_text = ""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", ollama_url, json=body) as response:
                    if response.status_code != 200:
                        yield f"data: {{\"error\": \"Ollama error {response.status_code}\"}}\n\n".encode('utf-8')
                        return
                    
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            try:
                                chunk_str = chunk.decode('utf-8', errors='ignore')
                                if chunk_str.startswith("data:"):
                                    for line in chunk_str.split("\n"):
                                        if line.startswith("data: ") and "[DONE]" not in line:
                                            clean_json = line[6:].strip()
                                            if clean_json:
                                                data_payload = json.loads(clean_json)
                                                delta_content = data_payload.get("choices", [{}]).get("delta", {}).get("content", "")
                                                full_completion_text += delta_content
                            except Exception:
                                pass
                            yield chunk
            
            generation_time_ms = int((time.perf_counter() - start_time) * 1000)
            
            log_event(
                body=f"RAG Chat success in {generation_time_ms / 1000:.3f}s",
                event_name="rag_chat_success",
                attributes={"status": "success", "context_injected": bool(rag_context)}
            )

            full_prompt_text = "".join([m.get("content", "") for m in body.get("messages", [])])
            prompt_tokens = count_tokens_fallback(full_prompt_text)
            completion_tokens = count_tokens_fallback(full_completion_text)

            asyncio.create_task(
                track_agent_telemetry(
                    session_id=body.get("session_id", "web_session"),
                    graph_name="marm_ai_v1",
                    node_name="proxy_chat_router",
                    model_name=model_name,
                    status="success",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=generation_time_ms,
                    tool_called="none"
                )
            )

        except Exception as e:
            generation_time_ms = int((time.perf_counter() - start_time) * 1000)
            asyncio.create_task(
                track_agent_telemetry(
                    session_id=body.get("session_id", "web_session"),
                    graph_name="marm_ai_v1",
                    node_name="proxy_chat_router",
                    model_name=model_name,
                    status="failed",
                    prompt_tokens=0,
                    completion_tokens=0,
                    latency_ms=generation_time_ms,
                    tool_called="none"
                )
            )
            
            # ИСПРАВЛЕНО: Безопасное экранирование ошибок генератора и исправление имени переменной
            error_msg = f"Stream interrupted: {str(e)}"
            error_dict = {
                "choices": [{
                    "delta": {"content": f"❌ [MarmAI Error] {error_msg}"},
                    "finish_reason": "stop",
                    "index": 0
                }],
                "model": model_name
            }
            safe_error_str = json.dumps(error_dict, ensure_ascii=False)
            yield f"data: {safe_error_str}\n\n".encode('utf-8')
            yield b"data: [DONE]\n\n"

    # ИСПРАВЛЕНО: Этот return теперь находится на уровне основной функции proxy_chat, а не внутри генератора!
    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )

@router.post("/telemetry/git-commit")
async def git_commit_trigger(payload: CommitPayload):
    """Эндпоинт-триггер. Вызывается локальным Git-хуком post-commit при каждом коммите."""
    import re
    from database.task_storage import update_task_status_db, get_all_tasks_db
    
    print(f"📦 [Git Trigger] Перехвачен коммит {payload.hash[:7]}: {payload.message}")
    
    # Регулярным выражением ищем упоминание ID задачи (например: #12, close #7, fix #1)
    task_ids = re.findall(r'#(\d+)', payload.message)
    
    if not task_ids:
        return {"status": "ignored", "reason": "No task ID found in commit message (e.g. #12)"}
        
    closed_tasks = []
    for t_id in task_ids:
        task_id_int = int(t_id)
        # Переводим задачу в DONE и привязываем хеш коммита
        success = update_task_status_db(task_id_int, "done", commit_hash=payload.hash)
        if success:
            closed_tasks.append(task_id_int)
            print(f"🎉 [Git Trigger] Задача #{task_id_int} АВТОМАТИЧЕСКИ переведена в статус DONE!")
            
    return {"status": "success", "closed_tasks": closed_tasks}