import os
import httpx
import json
import time
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from telemetry import logger, logger_provider 

from memory import save_chat_history, get_chat_history, clear_chat_history
from agent_graph import agent_app
from storage import init_prompt_storage, load_prompt_from_minio
from analytics import log_agent_telemetry, log_agent_configuration
from agent_tools_graph import tools_agent_app
import autocomplete

vault_secrets = {}
agent_system_prompt = ""  

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vault_secrets, agent_system_prompt
    print("🚀 [System] Старт lifespan-контекста FastAPI приложения ai_kane_agent...")
    
    try:
        from authorization import get_vault_secrets
        vault_secrets = get_vault_secrets(logger)
        print("🔑 [System] Vault успешно вернул секреты.")
    except Exception as err:
        print(f"❌ [System] Critical Vault error: {err}")
        raise err
        
    try:
        print("📦 [System] Инициализация хранилища MinIO...")
        init_prompt_storage()  
        agent_system_prompt = load_prompt_from_minio("system_prompt.md")
        print(f"✅ [System] Промпт успешно загружен. Длина: {len(agent_system_prompt)} симв.")
        
        # ➕ Логируем текущий срез личности в таблицу agent_configuration!
        import asyncio
        from analytics import log_agent_configuration
        asyncio.create_task(
            log_agent_configuration(
                project_id="marmai-backend",
                config_type="persona",
                priority_level="1_base",
                sub_category="identity",
                version="latest",
                title="Базовая квантово-мармеладная личность киберкотика",
                content_text=agent_system_prompt,
                author="minio_sync_job"
            )
        )
        print("📊 [System] Актуальный срез личности залогирован в таблицу agent_configuration.")
    except Exception as s3_err:
        print(f"⚠️ [System] Ошибка MinIO, локальный режим: {s3_err}")

    yield
    print("🛑 [System] Остановка FastAPI приложения...")
    logger_provider.shutdown()

app = FastAPI(title="AI Kane Agent Service & Ollama Gateway", lifespan=lifespan)

# --- СХЕМЫ PYDANTIC ---
class PromptRequest(BaseModel):
    prompt: str
    session_id: str = None
    model: str = None

class FileActivityRequest(BaseModel):
    project_id: str
    file_path: str
    event_type: str  # open, save, edit, focus
    language: str
    cursor_line: int = 0
    cursor_column: int = 0
    lines_changed: int = 0
    file_size_bytes: int = 0

class VCSHistoryRequest(BaseModel):
    project_id: str
    commit_hash: str
    author: str
    branch: str
    commit_message: str
    files_added: str = ""
    files_modified: str = ""
    insertions: int = 0
    deletions: int = 0

# --- 🔮 ЭМУЛЯЦИЯ OLLAMA API ДЛЯ ПЛАГИНА CONTINUE (VS CODE) ---

@app.get("/api/tags")
async def get_ollama_tags():
    logger.info("Continue запросил список доступных локальных моделей")
    return {
        "models": [
            {"name": "llama3.1:8b", "details": {"family": "llama"}},
            {"name": "qwen2.5-coder:1.5b", "details": {"family": "qwen2"}}
        ]
    }

# Параметры моделей
@app.post("/api/show")
async def ollama_show_model(request: dict):
    model_name = request.get("name", "llama3.1:8b")
    logger.info(f"Continue запросил параметры модели через /api/show для: {model_name}")
    return {
        "modelfile": f"FROM {model_name}\nSYSTEM {agent_system_prompt}",
        "parameters": "stop                           [\\n]",
        "template": "{{ if .System }}<|start_header_id|>system<|end_header_id|>\n\n{{ .System }}<|eot_id|>{{ end }}{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>\n\n{{ .Prompt }}<|eot_id|>{{ end }}<|start_header_id|>assistant<|end_header_id|>\n\n{{ .Response }}<|eot_id|>",
        "details": {
            "parent_model": "",
            "format": "gguf",
            "family": "llama" if "llama" in model_name else "qwen2",
            "families": ["llama" if "llama" in model_name else "qwen2"],
            "parameter_size": "8B" if "llama" in model_name else "1.5B",
            "quantization_level": "Q4_K_M"
        }
    }

# ЭНДПОИНТ ДЛЯ АВТОДОПОЛНЕНИЯ СТРОК
app.include_router(autocomplete.router)

# ЭНДПОИНТ ДЛЯ ЧАТА
@app.post("/api/chat")
async def ollama_chat_gateway(request: dict):
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ai_ollama_core:11435")
    
    session_id = request.get("session_id", "vs_code_session")
    
    model_name = request.get("model", "llama3.1:8b")
    incoming_messages = request.get("messages", [])
    should_stream = request.get("stream", True)
    
    options = request.get("options", {})
    options["temperature"] = 0.75
    options["top_p"] = 0.9
    options["presence_penalty"] = 0.6  
    
    final_messages = []
    if agent_system_prompt:
        final_messages.append({"role": "system", "content": agent_system_prompt})
        
    prompt_characters = 0
    for msg in incoming_messages:
        if msg.get("role") != "system":
            final_messages.append(msg)
            prompt_characters += len(msg.get("content", ""))
            
    prompt_tokens = max(1, prompt_characters // 4)
    
    # Вытаскиваем текущую реплику пользователя для RAG-анализа
    user_text = ""
    for msg in reversed(incoming_messages):
        if msg.get("role") == "user":
            user_text = msg.get("content", "").lower()
            break

    # 🚀 АВТОНОМНЫЙ ПЕРЕХВАТ ИНСТРУМЕНТОВ С ЭМУЛЯЦИЕЙ МАРМЕЛАДНОГО СТРИМИНГА
    if any(word in user_text for word in ["время", "дата", "часы", "лог", "контейнер"]):
        from langchain_core.messages import HumanMessage
        from datetime import datetime
        print("🤖 [MarmAI Gateway] Перенаправление запроса в автономный граф инструментов...")
        
        inputs = {
            "messages": [HumanMessage(content=user_text)],
            "session_id": session_id,
            "start_time": time.time(),
            "current_tool": "", "tool_input": "", "tool_output": "", "tool_call_id": ""
        }
        
        # Выполняем наш многошаговый граф (вызов -> системная утилита -> ответ)
        output = await tools_agent_app.ainvoke(inputs)
        final_bot_response = output["messages"][-1].content
        
        current_iso_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        # 🔄 СОЗДАЕМ ПОТОКОВЫЙ ГЕНЕРАТОР: разбиваем готовый текст на слова/токены для Continue
        async def tools_stream_chunk_generator():
            words = final_bot_response.split(" ")
            for i, word in enumerate(words):
                display_content = word if i == 0 else " " + word
                
                chunk_payload = {
                    "model": model_name,
                    "created_at": current_iso_time,
                    "message": {"role": "assistant", "content": display_content},
                    "done": False
                }
                yield json.dumps(chunk_payload, ensure_ascii=False) + "\n"
                await asyncio.sleep(0.02)
                
            # 🎯 ФИКС: Обязательно передаем объект message в закрывающий чанк!
            final_payload = {
                "model": model_name,
                "created_at": current_iso_time,
                "message": {"role": "assistant", "content": ""}, # <-- Заглушка для предотвращения TypeError
                "done": True
            }
            yield json.dumps(final_payload, ensure_ascii=False) + "\n"

        # 🎯 Возвращаем легальный StreamingResponse, который Continue примет с радостью!
        return StreamingResponse(tools_stream_chunk_generator(), media_type="application/x-ndjson")

    start_time = time.time()
    
    # СЕМАНТИЧЕСКИЙ ПОИСК КОНТЕКСТА В QDRANT
    rag_context = ""
    if user_query:
        try:
            from vector_storage import search_similar_knowledge
            # Ищем топ-2 релевантных документа в базе знаний
            rag_context = await search_similar_knowledge(user_query, limit=2)
        except Exception as rag_err:
            print(f"⚠️ [System] Ошибка RAG извлечения: {rag_err}")

    # Склеиваем базовую личность из MinIO и найденный в Qdrant контекст!
    full_system_context = agent_system_prompt
    if rag_context:
        full_system_context += (
            "\n\n# 📚 ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ QDRANT:\n"
            "Используй эти точные инженерные данные при формировании ответа:\n"
            f"{rag_context}"
        )

    # Добавляем итоговый обогащенный системный промпт на первое место
    if full_system_context:
        final_messages.append({"role": "system", "content": full_system_context})
    
    if agent_system_prompt:
        final_messages.append({"role": "system", "content": agent_system_prompt})
        
    prompt_characters = 0
    for msg in incoming_messages:
        if msg.get("role") != "system":
            final_messages.append(msg)
            prompt_characters += len(msg.get("content", ""))
            
    prompt_tokens = max(1, prompt_characters // 4)
    session_id = request.get("session_id", "vs_code_session")
    
    start_time = time.time()
    ollama_payload = {
        "model": model_name, 
        "messages": final_messages, 
        "stream": True,
        "options": options 
    }
    input_json_str = json.dumps(incoming_messages, ensure_ascii=False)

    async def stream_generator():
        response_characters = 0
        status = "success"
        full_response_text = ""
        error_msg = ""
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", 
                    f"{OLLAMA_URL}/api/chat", 
                    json=ollama_payload,
                    timeout=60.0
                ) as response:
                    async for chunk in response.aiter_lines():
                        if chunk:
                            try:
                                chunk_data = json.loads(chunk)
                                content_chunk = chunk_data.get("message", {}).get("content", "")
                                response_characters += len(content_chunk)
                                full_response_text += content_chunk
                            except:
                                pass
                            yield chunk + "\n"
        except Exception as e:
            status = "error"
            error_msg = str(e)
            raise e
        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            completion_tokens = response_characters // 4
            
            from analytics import log_agent_telemetry
            import asyncio
            asyncio.create_task(
                log_agent_telemetry(
                    session_id=session_id,
                    graph_name="vs_code_gateway_flow",
                    node_name="ollama_chat_node",
                    model_name=model_name,
                    status=status,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    input_payload=input_json_str,
                    output_payload=full_response_text,
                    error_message=error_msg
                )
            )

    if should_stream:
        return StreamingResponse(stream_generator(), media_type="application/x-ndjson")
        
    ollama_payload["stream"] = False
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{OLLAMA_URL}/api/chat", json=ollama_payload, timeout=60.0)
        result_json = res.json()
        
        latency_ms = int((time.time() - start_time) * 1000)
        response_text = result_json.get("message", {}).get("content", "")
        completion_tokens = len(response_text) // 4
        
        from analytics import log_agent_telemetry
        await log_agent_telemetry(
            session_id=session_id,
            graph_name="vs_code_gateway_flow",
            node_name="ollama_chat_node",
            model_name=model_name,
            status="success",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            input_payload=input_json_str,
            output_payload=response_text
        )
        return result_json

@app.post("/api/v1/ide/event")
async def receive_ide_event(payload: FileActivityRequest):
    # Логируем событие в консоль для отладки
    logger.info(
        f"IDE Event: {payload.event_type} на файле {payload.file_path}", 
        extra={"project_id": payload.project_id, "event": payload.event_type}
    )
    
    try:
        # Импортируем нашу функцию из модуля аналитики
        from analytics import log_file_activity
        import asyncio
        
        # Асинхронно отправляем метрику в InfluxDB 3 в таблицу file_activity
        asyncio.create_task(
            log_file_activity(
                project_id=payload.project_id,
                file_path=payload.file_path,
                event_type=payload.event_type,
                language=payload.language,
                cursor_line=payload.cursor_line,
                cursor_column=payload.cursor_column,
                lines_changed=payload.lines_changed,
                file_size_bytes=payload.file_size_bytes
            )
        )
        return {"status": "success", "message": "Метрика file_activity успешно принята шлюзом"}
        
    except Exception as e:
        logger.error(f"Ошибка обработки метрики IDE: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/session/{session_id}")
async def delete_session(session_id: str):
    clear_chat_history(session_id)
    return {"status": "success", "message": f"Сессия {session_id} удалена"}

# ЭНДПОИНТ ДЛЯ ИСТОРИИ КОММИТОВ
@app.post("/api/v1/vcs/commit")
async def receive_vcs_commit(payload: VCSHistoryRequest):
    logger.info(
        f"Git Commit Hook: {payload.commit_hash} в ветке {payload.branch}", 
        extra={"project_id": payload.project_id, "author": payload.author}
    )
    print(f"📦 [System] Принят лог коммита {payload.commit_hash} от {payload.author}...")
    
    try:
        from analytics import log_vcs_history
        import asyncio
        
        # Асинхронно перенаправляем данные коммита в InfluxDB 3 на порт 8181
        asyncio.create_task(
            log_vcs_history(
                project_id=payload.project_id,
                commit_hash=payload.commit_hash,
                author=payload.author,
                branch=payload.branch,
                commit_message=payload.commit_message,
                files_added=payload.files_added,
                files_modified=payload.files_modified,
                insertions=payload.insertions,
                deletions=payload.deletions
            )
        )
        return {"status": "success", "message": "Данные VCS успешно зафиксированы в InfluxDB 3"}
    except Exception as e:
        logger.error(f"Ошибка обработки Git-метрики: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "vault_connected": bool(vault_secrets)}

@app.get("/api/version")
async def get_ollama_version():
    logger.info("Continue запросил версию Ollama API")
    return {"version": "0.1.48"} # Эмулируем актуальную версию Ollama
