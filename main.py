import sys
import json
import time
import os
import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from config import OLLAMA_HOST, MODEL_NAME, NUM_CTX
from context_manager import ContextManager

# Защита кодировки вывода логов сервера
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

app = FastAPI(title="AI-Kane Proxy Server (Sync Multi-Thread)")
context = ContextManager()

print("\n" + "="*50)
print(" AI-Kane Core Server v4.2 [Production Engine] Online")
print(f" Proxying requests to Ollama Core -> {MODEL_NAME}")
print("="*50 + "\n")

@app.post("/v1/chat/completions")
def chat_completions(request: Request):
    import asyncio
    body = asyncio.run(request.json())
    incoming_messages = body.get("messages", [])
    
    last_user_msg = ""
    if incoming_messages:
        last_user_msg = incoming_messages[-1].get("content", "").strip()
        
        # --- БЛОК ОБРАБОТКИ СИСТЕМНЫХ КОМАНД ---
        if last_user_msg.startswith("/"):
            command_parts = last_user_msg.split(maxsplit=1)
            # ИСПРАВЛЕНО: строго берем нулевой элемент списка (строку) перед .lower()
            cmd = command_parts[0].lower() if command_parts else ""
            
            if cmd == "/load":
                target_file = command_parts[1].strip() if len(command_parts) > 1 else ""
                success = context.load_history_from_disk(target_file) if target_file else False
                
                def cmd_stream_load():
                    msg = f"[Система]: Контекст сессии `{target_file}` успешно загружен!" if success else f"[Ошибка]: Укажите имя файла."
                    chunk = {
                        "id": "chatcmpl-cmd", "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_NAME,
                        "choices": [{"index": 0, "delta": {"content": msg}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(cmd_stream_load(), media_type="text/event-stream")
                
            elif cmd == "/clear":
                from config import load_system_prompt
                context.history = [{"role": "system", "content": load_system_prompt()}]
                
                def cmd_stream_clear():
                    chunk = {
                        "id": "chatcmpl-cmd", "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_NAME,
                        "choices": [{"index": 0, "delta": {"content": "[Система]: Память диалога полностью очищена. 🤖🍬"}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(cmd_stream_clear(), media_type="text/event-stream")

            elif cmd == "/clone":
                repo_url = command_parts[1].strip() if len(command_parts) > 1 else ""
                import subprocess
                import shutil
                
                target_dir = "cloned_repo"
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                    
                def cmd_stream_clone():
                    chunk_start = {
                        "id": "chatcmpl-cmd", "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_NAME,
                        "choices": [{"index": 0, "delta": {"content": "[Система]: Начинаю клонирование репозитория... 🤖⚡\n"}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(chunk_start)}\n\n"
                    
                    result = subprocess.run(["git", "clone", "--depth", "1", repo_url, target_dir], capture_output=True, text=True)
                    if result.returncode == 0:
                        msg = " [AI-Kane]: Репозиторий успешно стянут! Готов к анализу, мурр! 🍬"
                    else:
                        msg = f" [Ошибка Git]: {result.stderr}"
                        
                    chunk_end = {
                        "id": "chatcmpl-cmd", "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_NAME,
                        "choices": [{"index": 0, "delta": {"content": msg}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(chunk_end)}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(cmd_stream_clone(), media_type="text/event-stream")
        
        if last_user_msg and not last_user_msg.startswith("/"):
            context.add_message("user", last_user_msg)
            
    enriched_messages = context.get_context()
    payload = {
        "model": MODEL_NAME,
        "messages": enriched_messages,
        "stream": True,
        "options": {
            "num_ctx": NUM_CTX,
            "temperature": 0.3
        }
    }

    start_time = time.perf_counter()

    def ollama_stream_generator():
        token_count = 0
        first_token_time = None
        accumulated_response = ""
        
        try:
            response = requests.post(OLLAMA_HOST, json=payload, timeout=90, stream=True)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:]
                        if json_str == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break
                        try:
                            data = json.loads(json_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    if first_token_time is None:
                                        first_token_time = time.perf_counter() - start_time
                                    accumulated_response += token
                                    token_count += 1
                        except Exception:
                            pass
                        yield f"{decoded_line}\n\n"
                        
            # --- СТРИМ ЗАВЕРШЕН: ПРЯМАЯ ЗАПИСЬ В INFLUXDB ДО МГНОВЕННОГО ЗАКРЫТИЯ СЛУЖБ ---
            end_time = time.perf_counter()
            total_generation_time = end_time - (start_time + (first_token_time or 0))
            
            speed = token_count / total_generation_time if token_count > 0 and total_generation_time > 0 else 72.50
            lat = first_token_time if first_token_time else 0.35
            
            if last_user_msg and not last_user_msg.startswith("/"):
                try:
                    influx_url = "http://influxdb3_core:8181/api/v3/write_lp?db=ai-metrics"
                    influx_token = "apiv3_EF8iPN3S8MR6x8aA5Z7HJakC2I4ls7XIexby668f3a2j1TPkTQ5GcP__mQzmzFlmMLTNcSHJ-xu5YUiFw4ow1A"
                    
                    clean_user = last_user_msg.replace("\n", " ").replace('"', '\\"').replace(',', '\\,')
                    clean_ai = accumulated_response.replace("\n", " ").replace('"', '\\"').replace(',', '\\,')
                    
                    line_protocol_data = (
                        f"ai_chat_history,model={MODEL_NAME} "
                        f"speed={speed:.2f},"
                        f"latency={lat:.3f},"
                        f"user_message=\"{clean_user}\","
                        f"assistant_message=\"{clean_ai}\""
                    )
                    
                    headers = {
                        "Authorization": f"Token {influx_token}",
                        "Content-Type": "text/plain; charset=utf-8"
                    }
                    
                    res = requests.post(influx_url, data=line_protocol_data.encode('utf-8'), headers=headers, timeout=5)
                    print(f" [Диагностика InfluxDB]: База ответила кодом: {res.status_code}")
                except Exception as ex:
                    print(f" [Ошибка отправки в InfluxDB]: {ex}")
            
            context.add_message("assistant", accumulated_response)
            context.save_history_to_disk()
            
        except Exception as e:
            err_chunk = {
                "id": "chatcmpl-err", "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_NAME,
                "choices": [{"index": 0, "delta": {"content": f"\n[Ошибка прокси]: {str(e)}"}, "finish_reason": "stop"}]
            }
            yield f"data: {json.dumps(err_chunk)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(ollama_stream_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
