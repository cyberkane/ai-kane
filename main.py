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

app = FastAPI(title="AI-Kane Proxy Server")
# Инициализируем наш менеджер контекста глобально для сервера
context = ContextManager()

print("\n" + "="*50)
# Текущая дата автоматизирована под контекст системы
print(" AI-Kane Core Server v3.0 [FastAPI Engine] Starting...")
print(f" Proxying requests to Ollama Core -> {MODEL_NAME}")
print("="*50 + "\n")

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Получаем тело запроса от плагина Continue (VS Code)
    body = await request.json()
    incoming_messages = body.get("messages", [])
    
    # Извлекаем последнее сообщение пользователя и добавляем в наш менеджер контекста
    if incoming_messages:
        last_user_msg = incoming_messages[-1].get("content", "")
        if last_user_msg:
            context.add_message("user", last_user_msg)
            
    # Собираем обогащенный контекст (с нашим системным промптом и обрезкой истории)
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

    # Начинаем замер времени инференса RTX 3070
    start_time = time.perf_counter()
    
    def ollama_stream_generator():
        full_ai_response = ""
        token_count = 0
        first_token_time = None
        
        try:
            # Отправляем запрос в фоновую Ollama
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
                                        
                                    full_ai_response += token
                                    token_count += 1
                                    
                        except Exception:
                            pass
                        
                        # Пробрасываем чанк данных обратно в Continue в реальном времени
                        yield f"{decoded_line}\n\n"
                        
            # Генерация завершена, считаем метрики скорости GPU
            end_time = time.perf_counter()
            total_generation_time = end_time - (start_time + (first_token_time or 0))
            
            print("-" * 40)
            print(f" [AI-Kane Metrics] Session Active Logged")
            if token_count > 0 and total_generation_time > 0:
                tokens_per_sec = token_count / total_generation_time
                print(f" [GPU Speed]: {tokens_per_sec:.2f} tokens/sec")
                print(f" [Response Latency]: {first_token_time:.3f} sec")
            print("-" * 40 + "\n")
            
            # Сохраняем ответ ИИ в память нашего контекста и пишем лог на NVMe
            context.add_message("assistant", full_ai_response)
            context.save_history_to_disk()
            
        except Exception as e:
            yield f"data: {{\"error\": \"Proxy error: {str(e)}\"}}\n\n"
            yield "data: [DONE]\n\n"

    # Возвращаем стриминг-ответ в VS Code в формате SSE (Server-Sent Events)
    return StreamingResponse(ollama_stream_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    # Запускаем веб-сервер внутри Alpine на порту 8000
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
# Запускаем веб-сервер внутри Alpine на порту 8000
# uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
