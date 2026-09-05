import sys
import json
import time
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
print(" AI-Kane Core Server v3.6 [Sync Thread Pool] Starting...")
print(f" Proxying requests to Ollama Core -> {MODEL_NAME}")
print("="*50 + "\n")

# УБРАЛИ async: теперь FastAPI автоматически выполняет этот метод в отдельном потоке
@app.post("/v1/chat/completions")
def chat_completions(request: Request):
    # Получаем JSON-тело синхронно
    import asyncio
    body = asyncio.run(request.json())
    incoming_messages = body.get("messages", [])
    
    if incoming_messages:
        last_user_msg = incoming_messages[-1].get("content", "").strip()
        
        # --- БЛОК ОБРАБОТКИ СИСТЕМНЫХ КОМАНД ---
        if last_user_msg.startswith("/"):
            command_parts = last_user_msg.split(maxsplit=1)
            cmd = command_parts[0].lower()
            
            if cmd == "/load":
                if len(command_parts) > 1:
                    target_file = command_parts[1].strip()
                    success = context.load_history_from_disk(target_file)
                else:
                    target_file = ""
                    success = False
                
                def cmd_stream_load():
                    msg = f"[Система]: Контекст сессии `{target_file}` успешно загружен!" if success else f"[Ошибка]: Не удалось загрузить файл `{target_file}`."
                    chunk = {
                        "id": "chatcmpl-cmd", "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_NAME,
                        "choices": [{"index": 0, "delta": {"content": msg}, "finish_reason": None}]
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
                        "choices": [{"index": 0, "delta": {"content": "[Система]: Память диалога полностью очищена."}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(cmd_stream_clear(), media_type="text/event-stream")
        
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
    
    # Полностью синхронный генератор потока данных
    def ollama_stream_generator():
        full_ai_response = ""
        token_count = 0
        first_token_time = None
        
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
                                delta = data["choices"].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    if first_token_time is None:
                                        first_token_time = time.perf_counter() - start_time
                                    full_ai_response += token
                                    token_count += 1
                        except Exception:
                            pass
                        yield f"{decoded_line}\n\n"
                        
            end_time = time.perf_counter()
            total_generation_time = end_time - (start_time + (first_token_time or 0))
            
            print("-" * 40)
            print(f" [AI-Kane Metrics] Session Active Logged")
            if token_count > 0 and total_generation_time > 0:
                tokens_per_sec = token_count / total_generation_time
                print(f" [GPU Speed]: {tokens_per_sec:.2f} tokens/sec")
                print(f" [Response Latency]: {first_token_time:.3f} sec")
            print("-" * 40 + "\n")
            
            context.add_message("assistant", full_ai_response)
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
    # Запускаем uvicorn с явным выделением нескольких воркеров для многопоточности
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=4, log_level="info")
