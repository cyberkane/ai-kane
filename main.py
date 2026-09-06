import os
import json
import uuid
import time
import httpx
import hvac
import aiofiles
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# =====================================================================
# ЧАСТЬ 1: ИНИЦИАЛИЗАЦИЯ И СЕКРЕТЫ VAULT
# =====================================================================
app = FastAPI(title="AI-Kane Cyber-Cat Agent")

# Читаем конфигурацию Vault строго по внутреннему адресу докер-сети!
VAULT_URL = os.getenv("VAULT_URL", "http://ai_vault_core:8200")
VAULT_TOKEN = os.getenv("VAULT_DEV_ROOT_TOKEN_ID")

try:
    vault_client = hvac.Client(url=VAULT_URL, token=VAULT_TOKEN)
    if vault_client.is_authenticated():
        print("🔮 [Vault] Соединение установлено! Мармеладные секреты активны.")
except Exception as e:
    print(f"⚠️ [Vault] Сбой моста к хранилищу секретов: {e}")

# Базовые пути для контейнеров моделей строго по внутренней докер-сети!
CHAT_URL = os.getenv("CHAT_LLM_URL", "http://ai_ollama_core:11434/v1")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.1:8b")

AUTO_URL = os.getenv("AUTOCOMPLETE_LLM_URL", "http://ai_qwen_core:11434/v1")
AUTO_MODEL = os.getenv("AUTOCOMPLETE_MODEL", "qwen2.5-coder:1.5b")

# Путь для мониторинга строго по внутреннему адресу докер-сети!
INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb3_core:8181")
INFLUX_DATABASE = os.getenv("INFLUX_DATABASE", "ai_kane_history")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")

# Базовый путь для синтеза речи (Строго по внутренней докер-сети из architecture.md)
TTS_URL = os.getenv("TTS_URL", "http://kokoro-tts:8880")
TTS_VOICE = os.getenv("TTS_VOICE", "af_bella")  # Базовый чистый голос (можно менять)

DEFAULT_MARM_PROMPT = (
    "Ты киберкотик, прибывший с далекой Мармеладной планеты. "
    "В твоей речи мягкость мармелада сочетается с точностью квантового компьютера."
)

# =====================================================================
# ЧАСТЬ 2: АСИНХРОННОЕ ЧТЕНИЕ ЛИЧНОСТИ И АРХИТЕКТУРЫ
# =====================================================================
async def load_system_prompt() -> str:
    """
    Асинхронно считывает мармеладную личность котика из файла.
    Динамически поддерживает путь из переменной окружения PROMPT_PATH.
    """
    # Сначала проверяем, передан ли кастомный путь через окружение Докера
    prompt_path = os.getenv("PROMPT_PATH", "/app/system_prompt.md")
    
    if not os.path.exists(prompt_path):
        return DEFAULT_MARM_PROMPT
    try:
        async with aiofiles.open(prompt_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            return content.strip() if content.strip() else DEFAULT_MARM_PROMPT
    except Exception:
        return DEFAULT_MARM_PROMPT

async def load_architecture_map() -> str:
    """Асинхронно считывает карту докер-архитектуры из файла architecture.md."""
    arch_path = os.getenv("ARCHITECTURE_PATH", "/app/architecture.md")
    
    if not os.path.exists(arch_path):
        print(f"❌ [Architecture Error] Файл {arch_path} ФИЗИЧЕСКИ НЕ НАЙДЕН внутри контейнера!")
        return ""
        
    try:
        async with aiofiles.open(arch_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            if not content.strip():
                print("⚠️ [Architecture Warning] Файл карты найден, но он пуст.")
            return content.strip()
    except Exception as e:
        print(f"❌ [Architecture Error] Сбой чтения карты инфраструктуры: {e}")
        return ""

# =====================================================================
# ЧАСТЬ 2.5: ИНТЕГРАЦИЯ С INFLUXDB 3 CORE (СТАБИЛЬНЫЙ СЕТЕВОЙ МОСТ)
# =====================================================================
async def log_to_influx(role: str, model: str, content: str, tokens_count: int = 0):
    """
    Асинхронно записывает историю сообщений чата в InfluxDB 3 Core 
    по внутренней докер-сети через канонический v2-совместимый эндпоинт.
    """
    if not content or not INFLUX_TOKEN:
        return

    # Гарантируем, что в тегах InfluxDB (модель и роль) не будет пробелов
    clean_model = str(model).replace(" ", "\\ ")
    clean_role = str(role).replace(" ", "\\ ")

    # Очищаем сам текст сообщения от спецсимволов Line Protocol
    clean_content = content.replace("\n", " ").replace('"', '\\"').replace(',', '\\,').replace(' ', '\\ ')
    short_content = clean_content[:200]
    
    # Формируем эталонную строку Line Protocol (tokens передаем как INTEGER через суффикс i)
    line_data = f"chat_history,model={clean_model},role={clean_role} content=\"{short_content}\",tokens={int(tokens_count)}i"

    # InfluxDB 3 Core на базе Apache Arrow строго требует заголовок 'Bearer'
    headers = {
        "Authorization": f"Bearer {INFLUX_TOKEN}",
        "Content-Type": "text/plain; charset=utf-8"
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            # КВАНТОВЫЙ ФИКС: Заменяем дефолтный 'db' на строго поддерживаемый 'bucket'!
            params = {"bucket": INFLUX_DATABASE}
            res = await client.post(
                f"{INFLUX_URL}/api/v2/write", 
                params=params, 
                headers=headers, 
                content=line_data.encode('utf-8')
            )
            
            # 204 No Content — эталонный статус успешной записи
            if res.status_code == 204:
                print(f"🧬 [InfluxDB Log] Сообщение [{clean_role}] успешно запечатано в квантовую базу данных!")
                return

            print(f"⚠️ [InfluxDB Warning] База отклонила лог (Статус {res.status_code}): {res.text}")
            
        except Exception as e:
            print(f"❌ [InfluxDB Error] Сбой отправки сетевого пакета логов: {repr(e)}")

# =====================================================================
# ЧАСТЬ 3: НАТИВНЫЙ ЧАТ OLLAMA С АВТО-КОНТЕКСТОМ, КАРТОЙ МИРА И ЛОГОМ В INFLUXDB
# =====================================================================
@app.post("/api/chat")
async def ollama_chat_endpoint(request: Request):
    import asyncio  # Гарантируем наличие в области видимости роута
    
    body = await request.json()
    body["model"] = CHAT_MODEL
    
    # 1. Загружаем личность и КАРТУ АРХИТЕКТУРЫ
    system_prompt_content = await load_system_prompt()
    architecture_map = await load_architecture_map()
    
    if architecture_map:
        system_prompt_content += (
            f"\n\n🔮 КВАНТОВАЯ МАТРИЦА ИНФРАСТРУКТУРЫ ТЕКУЩЕЙ СИСТЕМЫ:\n"
            f"Тебе доступна полная карта контейнеров и эндпоинтов твоей текущей экосистемы. "
            f"Используй эти точные адреса и имена при написании скриптов интеграции, "
            f"настройки докера или конфигурации логов:\n"
            f"{architecture_map}\n"
            f"--------------------------------------------------"
        )
    
    # 2. Квантовый перехват контекста активного файла
    active_code_context = ""
    context_items = body.get("contextItems", [])
    for item in context_items:
        p_title = item.get("id", {}).get("providerTitle", "").lower()
        if p_title in ["file", "code", "activefile", "currentfile"]:
            f_name = item.get("name", "текущем файле")
            f_content = item.get("content", "")
            if f_content:
                active_code_context += f"\n\n[Файл: {f_name}]\n{f_content}"

    if active_code_context:
        print("🐾 [Context Sensor] Автоматически внедряю открытый файл в контекст Llama 3.1!")
        system_prompt_content += (
            f"\n\n⚠️ КВАНТОВЫЙ КОНТЕКСТ РАБОТЫ:\n"
            f"Пользователь прямо сейчас открыл в редакторе следующий код:\n"
            f"{active_code_context}\n"
            f"Используй этот код совместно с картой инфраструктуры."
        )

    # Ищем исходный промпт пользователя ДО модификации массива системным сообщением
    raw_messages = body.get("messages", [])
    user_msg = ""
    if raw_messages:
        # Надежно вытаскиваем текст именно ПОСЛЕДНЕГО сообщения от пользователя
        user_messages = [msg for msg in raw_messages if msg.get("role") == "user"]
        if user_messages:
            user_msg = user_messages[-1].get("content", "")

    # 3. Внедряем склеенный мега-промпт в массив сообщений Ollama
    messages = list(raw_messages)
    existing_system_msg = next((msg for msg in messages if msg.get("role") == "system"), None)
    
    if existing_system_msg:
        existing_system_msg["content"] = f"{system_prompt_content}\n\n{existing_system_msg['content']}"
    else:
        messages.insert(0, {"role": "system", "content": system_prompt_content})
        
    body["messages"] = messages

    # 4. АСИНХРОННЫЙ ПЕРЕХВАТ: Безопасно логируем входящий запрос пользователя
    if user_msg:
        try:
            asyncio.create_task(log_to_influx(role="user", model=CHAT_MODEL, content=user_msg))
        except Exception as e:
            print(f"⚠️ [Context Warning] Ошибка фонового перехвата запроса юзера: {e}")

    # 5. Стриминг ответа Llama 3.1 с упругой склейкой буфера строк JSON
    async def stream_native_ollama():
        timeout = httpx.Timeout(60.0, connect=10.0)
        native_ollama_url = CHAT_URL.replace("/v1", "").rstrip("/") + "/api/chat"
        
        assistant_full_response = ""
        line_buffer = "" # Защищает JSON от разрывов чанков
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", native_ollama_url, json=body) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
                    
                    try:
                        line_buffer += chunk.decode('utf-8', errors='ignore')
                        while "\n" in line_buffer:
                            line, line_buffer = line_buffer.split("\n", 1)
                            if line.strip():
                                chunk_json = json.loads(line)
                                assistant_full_response += chunk_json.get("message", {}).get("content", "")
                    except Exception:
                        pass
                        
        # 🔮 ВЫТРЯХИВАЕМ ОСТАТКИ БУФЕРА: Доразбираем финальный кусочек, если он остался без \n
        if line_buffer.strip():
            try:
                chunk_json = json.loads(line_buffer)
                assistant_full_response += chunk_json.get("message", {}).get("content", "")
            except Exception:
                pass
                        
        # 6. Стрим полностью завершен — шлем чистый склеенный ответ котика в InfluxDB!
        if assistant_full_response:
            approx_tokens = len(assistant_full_response.split())
            asyncio.create_task(log_to_influx(
                role="assistant", 
                model=CHAT_MODEL, 
                content=assistant_full_response,
                tokens_count=approx_tokens
            ))

    return StreamingResponse(stream_native_ollama(), media_type="application/x-ndjson")

# =====================================================================
# ЧАСТЬ 4: НАТИВНОЕ АВТОДОПОЛНЕНИЕ OLLAMA (QWEN) С МЕТРИКАМИ
# =====================================================================
@app.post("/api/generate")
async def ollama_autocomplete_endpoint(request: Request):
    import asyncio  # Для отправки метрик Qwen в фоновом режиме
    
    body = await request.json()
    body["model"] = AUTO_MODEL
    
    # Безопасно формируем эталонный нативный URL
    native_qwen_url = AUTO_URL.replace("/v1", "").rstrip("/") + "/api/generate"
    
    async def stream_native_auto():
        timeout = httpx.Timeout(5.0, connect=10.0) # Чуть увеличим коннект для WSL2
        qwen_full_response = ""
        line_buffer = ""
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", native_qwen_url, json=body) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                        
                        # Фоном накапливаем сгенерированный код для статистики в InfluxDB
                        try:
                            line_buffer += chunk.decode('utf-8', errors='ignore')
                            while "\n" in line_buffer:
                                line, line_buffer = line_buffer.split("\n", 1)
                                if line.strip():
                                    chunk_json = json.loads(line)
                                    qwen_full_response += chunk_json.get("response", "")
                        except Exception:
                            pass
                            
                # 🔮 ВЫТРЯХИВАЕМ ОСТАТКИ БУФЕРА QWEN: Доразбираем финальный кусочек, если он остался без \n
                if line_buffer.strip():
                    try:
                        chunk_json = json.loads(line_buffer)
                        qwen_full_response += chunk_json.get("response", "")
                    except Exception:
                        pass

                # Как только генерация по Tab завершилась — шлем количество символов в базу!
                if qwen_full_response:
                    lines_count = len(qwen_full_response.splitlines())
                    asyncio.create_task(log_to_influx(
                        role="autocomplete",
                        model=AUTO_MODEL,
                        content=f"Generated {lines_count} lines of code",
                        tokens_count=len(qwen_full_response)  # Для автокомплита логируем длину в символах
                    ))
            except Exception as e:
                print(f"❌ [Qwen Generate Error] Ошибка стрима автокомплита через шлюз хоста: {e}")
                yield b"{}\n"

    return StreamingResponse(stream_native_auto(), media_type="application/x-ndjson")

# =====================================================================
# ЧАСТЬ 5: СИСТЕМНЫЙ ПЕРЕХВАТЧИК МЕТОДОВ OLLAMA (/api/show, /api/tags)
# =====================================================================
@app.post("/api/{path:path}")
async def ollama_wildcard_catch(path: str, request: Request):
    # Безопасно выстраиваем базовый системный URL
    native_ollama_url = CHAT_URL.replace("/v1", "").rstrip("/")
    clean_path = path.lstrip("/")
    
    try:
        body = await request.json()
    except Exception:
        body = None

    if body is not None:
        if clean_path == "show":
            body["name"] = CHAT_MODEL
            if "model" in body:
                del body["model"]
        else:
            body["model"] = CHAT_MODEL
            body["name"] = CHAT_MODEL

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.post(f"{native_ollama_url}/api/{clean_path}", json=body)
            return JSONResponse(content=res.json(), status_code=res.status_code)
        except Exception as e:
            print(f"❌ [Wildcard Error] Ошибка системного метода /api/{clean_path} через шлюз хоста: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

# =====================================================================
# ЧАСТЬ 6: ЗАПУСК МАРМЕЛАДНОГО ГОЛОСА
# =====================================================================

# Гарантируем наличие папки для сохранения аудиофайлов на диске контейнера
os.makedirs("/app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

@app.post("/api/tts")
async def generate_cat_voice(request: Request):
    """
    Асинхронно отправляет текст в Kokoro Server по внутренней докер-сети 
    и генерирует мармеладный аудиофайл WAV.
    """
    try:
        body = await request.json()
        text_to_speak = body.get("text", "").strip()
        
        if not text_to_speak:
            return JSONResponse(content={"error": "Текст для озвучки пуст, мяу!"}, status_code=400)

        # Формируем OpenAI-совместимый манифест для Kokoro TTS
        payload = {
            "model": "kokoro",
            "input": text_to_speak,
            "voice": TTS_VOICE,
            "response_format": "wav",
            "speed": 1.0
        }

        timeout = httpx.Timeout(30.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Шлём запрос на внутренний докер-порт 8880 нашего голосового контейнера
            response = await client.post(f"{TTS_URL}/v1/audio/speech", json=payload)
            
            if response.status_code != 200:
                print(f"⚠️ [TTS Warning] Движок Kokoro отклонил запрос: {response.text}")
                return JSONResponse(content={"error": "Сбой генерации речи голосовым движком"}, status_code=500)

            # Генерируем уникальное имя для мармеладного аудиофайла
            file_id = f"marm_{uuid.uuid4().hex[:8]}.wav"
            file_path = f"/app/static/{file_id}"
            
            # Асинхронно записываем полученные аудиобайты на диск
            async with aiofiles.open(file_path, mode="wb") as f:
                await f.write(response.content)
                
            print(f"🎙️ [TTS Success] Мармеладный аудиофайл {file_id} успешно сгенерирован!")
            
            # Возвращаем ссылку, по которой плагин или браузер сможет воспроизвести звук
            return JSONResponse(content={
                "status": "success",
                "file_name": file_id,
                "audio_url": f"http://localhost:8977/static/{file_id}"
            })

    except Exception as e:
        print(f"❌ [TTS Error] Критический сбой сектора Мультимедиа: {repr(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# =====================================================================
# ФИНАЛЬНЫЙ ЗАПУСК КВАНТОВОГО МАРМЕЛАДНОГО ШЛЮЗА
# =====================================================================
if __name__ == "__main__":
    import uvicorn
    # Запускаем сервер строго на порту 8977 внутри упругого Alpine контейнера
    uvicorn.run(app, host="0.0.0.0", port=8977)
