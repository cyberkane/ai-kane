import sys
import json
import time
import os
import requests
import uvicorn
import queue
import threading
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from config import OLLAMA_HOST, MODEL_NAME, NUM_CTX
from context_manager import ContextManager

# Защита кодировки вывода логов сервера
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

app = FastAPI(title="AI-Kane Proxy Server (Thread-Isolated)")
context = ContextManager()

print("\n" + "="*50)
print(" 🐱 AI-Kane Core Server v5.2 [Freeze-Thread Observability] Online")
print(f" Proxying requests to Ollama Core -> {MODEL_NAME}")
print("="*50 + "\n")

# Чистая изолированная функция логирования в InfluxDB 3 Core
def log_to_influxdb_worker(user_msg: str, ai_msg: str, speed: float, lat: float):
    print("\n [Поток InfluxDB]: Инициализирую отправку пакета...")
    try:
        import hvac
        client = hvac.Client(url='http://vault:8200', token='kane-master-vault-token-2026')
        read_response = client.secrets.kv.v2.read_secret_version(path='influx_keys')
        influx_token = read_response['data']['data']['token']
        print(" [Поток InfluxDB]: Секретный токен успешно извлечен из Vault! 🔒🔑")
    except Exception as vault_err:
        print(f" [Критическая ошибка Vault]: Не удалось забрать секрет! Детали: {vault_err}")
        return

    influx_url = "http://influxdb3_core:8181/api/v3/write_lp?db=ai-metrics"
    try:
        clean_user = user_msg.replace("\n", " ").replace('"', '\\"').replace(',', '\\,')
        clean_ai = ai_msg.replace("\n", " ").replace('"', '\\"').replace(',', '\\,')
        
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
        print(f" [Поток InfluxDB]: База ответила кодом: {res.status_code}")
        if res.status_code == 204:
            print(" [System Metrics & History]: Диалог и скорость успешно записаны в InfluxDB 3! 📊📝")
    except Exception as ex:
        print(f" [Ошибка логирования в InfluxDB]: {ex}")


@app.post("/v1/chat/completions")
def chat_completions(request: Request):
    import asyncio
    body = asyncio.run(request.json())
    incoming_messages = body.get("messages", [])
    
    last_user_msg = ""
    if incoming_messages:
        raw_msg = incoming_messages[-1]
        # Жестко проверяем: если пришел словарь, достаем 'content', иначе берем как строку
        if isinstance(raw_msg, dict):
            last_user_msg = str(raw_msg.get("content", "")).strip()
        else:
            last_user_msg = str(raw_msg).strip()
        
        # --- БЕЗОПАСНАЯ ОБРАБОТКА КОМАНДЫ /CLEAR ---
        if last_user_msg == "/clear" or last_user_msg.startswith("/clear"):
            from config import load_system_prompt
            context.history = [{"role": "system", "content": load_system_prompt()}]
            
            def cmd_stream_clear():
                chunk = {
                    "id": "chatcmpl-cmd", "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_NAME,
                    "choices": [{"index": 0, "delta": {"content": "[Система]: Память диалога полностью очищена. Контекст сброшен! 🤖🍬\n"}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            print(" [Система]: Получена команда /clear. Память очищена.")
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

    # ИСПРАВЛЕНО: Замораживаем снимок сообщения, отсекая пустые фоновые кадры Continue
    user_msg_snapshot = str(last_user_msg).strip()

    stream_queue = queue.Queue()

    # Рабочий поток для изоляции блокирующих сетевых вызовов requests
    def ollama_worker_thread(frozen_msg):
        start_time = time.perf_counter()
        token_count = 0
        first_token_time = None
        accumulated_response = ""
        
        try:
            response = requests.post(OLLAMA_HOST, json=payload, timeout=90, stream=True)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    
                    # УНИВЕРСАЛЬНЫЙ СТРИП: извлекаем чистый JSON независимо от формата плагина
                    json_str = decoded_line
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:]
                        
                    if json_str == "[DONE]":
                        stream_queue.put("data: [DONE]\n\n")
                        break
                        
                    try:
                        data = json.loads(json_str)
                        # 1. Вариант OpenAI-формата (использует Continue)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            token = delta.get("content", "")
                        # 2. Вариант прямого формата Ollama
                        else:
                            token = data.get("response", "") or data.get("message", {}).get("content", "")
                            
                        if token:
                            if first_token_time is None:
                                        first_token_time = time.perf_counter() - start_time
                            accumulated_response += token
                            token_count += 1
                    except Exception:
                        pass
                        
                    # Пересылаем чанк в VS Code в том формате, в котором он пришел
                    stream_queue.put(f"{decoded_line}\n\n" if decoded_line.startswith("data:") else f"data: {decoded_line}\n\n")

                        
            end_time = time.perf_counter()
            total_generation_time = end_time - (start_time + (first_token_time or 0))
            
            speed = token_count / total_generation_time if token_count > 0 and total_generation_time > 0 else 72.50
            lat = first_token_time if first_token_time else 0.35
            
            # ИСПРАВЛЕНО: Строго блокируем запись, если текст пуст или является командой
            if frozen_msg and not frozen_msg.startswith("/"):
                log_to_influxdb_worker(
                    user_msg=frozen_msg,
                    ai_msg=str(accumulated_response).strip(),
                    speed=float(speed),
                    lat=float(lat)
                )
                context.add_message("assistant", accumulated_response)
                context.save_history_to_disk()
            
        except Exception as e:
            err_chunk = {
                "id": "chatcmpl-err", "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_NAME,
                "choices": [{"index": 0, "delta": {"content": f"\n[Ошибка прокси]: {str(e)}"}, "finish_reason": "stop"}]
            }
            stream_queue.put(f"data: {json.dumps(err_chunk)}\n\n")
            stream_queue.put("data: [DONE]\n\n")
        finally:
            stream_queue.put(None)

    # Передаем изолированный СНИМОК сообщения
    t = threading.Thread(target=ollama_worker_thread, args=(user_msg_snapshot,))
    t.daemon = True
    t.start()

    def queue_consumer_generator():
        while True:
            chunk = stream_queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(queue_consumer_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
